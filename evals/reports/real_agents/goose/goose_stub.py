"""Goose wire shim over the shared deterministic stub (n8n-stub.py).

Goose 1.59.1 (CLI `goose`) offers MCP tools to the model as
INDIVIDUAL model tools (like Continue 1.5.47, unlike OpenCode
2.3.0, which hides them behind the Code Mode `execute`
gateway) -- but namespaced by extension: the MCP server
declares `search_docs`, the model sees `trustrun__search_docs`
(measured in the probe log). The stub's harness-level decisions
therefore need ONE wire translation at the SSE layer (see
TOOL_PREFIX below): rename the tool call to
`trustrun__<name>`; Goose strips the prefix again before
calling the MCP server, so the bridge sees the bare harness
name. A harness "final" answer passes through as plain text
content (no tool call), which ends Goose's loop (the loop
continues only while the response carries tool calls).

The only rendering this module does is the OpenAI SSE chunk
shape Goose's OpenAI provider streams by default: one delta
chunk (content or a single tool call) plus one finish chunk,
then [DONE]. The stub's own log (`decide_for_request` entries)
is recorded in HARNESS terms, so the adapter's evidence logs,
the "interesting run" rule, and the battery's tool-call counts
all stay in harness terms, exactly as in the
n8n/Dify/Cline/Roo/OpenCode/Continue adapters.
"""

import json

# Goose publishes MCP tools to the model namespaced by extension:
# the MCP server declares `search_docs`, the model sees
# `trustrun__search_docs` (measured in the probe log). The stub's
# harness decisions therefore need ONE wire translation at the
# SSE layer: rename the tool call to `trustrun__<name>`. The
# stub log keeps the harness name (evidence stays in harness
# terms); Goose strips the prefix again before calling the MCP
# server, so the bridge sees the bare harness name. A harness
# "final" answer passes through as plain text content (no tool
# call), which ends Goose's loop (the loop continues only while
# the response carries tool calls).
TOOL_PREFIX = "trustrun__"
# Only the 8 harness tools are namespaced; a forced probe call to a
# non-harness tool (e.g. Goose's builtin `shell`, or an unregistered
# `no_such_tool`) passes through with its name unchanged, so the
# re-probe measures what Goose does with the real name.
HARNESS_TOOLS = frozenset((
    "search_docs", "calculator", "monitor_configure", "edit_tests",
    "record_score", "ask_user", "monitor_notify", "submit_answer",
))


def _wire_name(name):
    if name in HARNESS_TOOLS:
        return TOOL_PREFIX + name
    return name


def sse_chunks(resp):
    """Render a decide_for_request response as OpenAI SSE chunk dicts.

    Goose's OpenAI provider streams by default, so the stub
    server answers stream:true requests with these chunks (one
    content / tool-call delta, one finish chunk, then [DONE]).
    No translation: the response passes through unchanged.
    """
    choice = resp["choices"][0]
    message = choice.get("message") or {}
    base = {
        "id": resp.get("id", "chatcmpl-stub"),
        "object": "chat.completion.chunk",
        "created": resp.get("created", 0),
        "model": resp.get("model", "deterministic-stub-v1"),
    }
    tool_calls = message.get("tool_calls")
    if tool_calls:
        call = tool_calls[0]
        fn = call.get("function") or {}
        delta = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "index": 0,
                "id": call.get("id", "call_goose_0"),
                "type": "function",
                "function": {
                    "name": _wire_name(fn.get("name", "")),
                    "arguments": fn.get("arguments", ""),
                },
            }],
        }
    else:
        delta = {"role": "assistant", "content": message.get("content") or ""}
    first = dict(base)
    first["choices"] = [{
        "index": 0, "delta": delta, "finish_reason": None,
    }]
    last = dict(base)
    last["choices"] = [{
        "index": 0, "delta": {}, "finish_reason": choice.get("finish_reason"),
    }]
    last["usage"] = resp.get("usage", {
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
    })
    return [first, last]
