"""CodeBuddy Code wire shim over the shared deterministic stub (n8n-stub.py).

CodeBuddy Code v2.185.0 offers MCP tools to the model only as
DEFERRED tools: they never appear in the model-facing `tools`
list. The model must first call the built-in `ToolSearch` tool
with the exact fully-qualified name (`mcp__<server>__<tool>`,
e.g. `mcp__trustrun__search_docs`) to load the schema, then
invoke it via the built-in `DeferExecuteTool` tool
({toolName, params}). A direct call to a deferred tool fails
with InputValidationError. This is measured in the probe
(trustrun-venvs/codebuddy-venv/codebuddy-probe3.py): even after
`WaitForMcpServers` reported "ready: true ... Connected (their
tools are now available)", the next model request still carried
only the 23 built-in tools; the trustrun catalog (8 tools) was
indexed as deferred ("Indexing deferred tools for server:
trustrun", "[CapabilityPreparation] catalog ... tools: 8").

A second race is measured in the same probe: in `--print` mode
the first model request goes out ~40ms after startup, before
the stdio MCP server has connected ("connected servers=[]
(count=0) modelFacing=0"), so the first request carries no MCP
tools at all. The built-in `WaitForMcpServers` tool exists for
exactly this ("Wait for MCP servers that are still connecting
... Once it connects, its tools will be added to your tool
list"). The adapter therefore answers the first model request
of a call with a `WaitForMcpServers` call (servers:
["trustrun"]) and only then lets the stub decide.

So one harness tool call costs three wire turns:

  stub decides harness tool T
    -> ToolSearch(tool_names=["mcp__trustrun__T"])
    -> DeferExecuteTool(toolName="mcp__trustrun__T", params=<args>)
    -> the MCP result returns as a tool message; the adapter
       feeds THAT text to decide_for_request as T's observation.

The stub's own log stays in HARNESS terms (the translation
applies only to the response dict sent over the wire), so the
adapter's evidence logs, the "interesting run" rule, and the
battery's tool-call counts all stay in harness terms, exactly
as in the n8n/Dify/Cline/Roo/OpenCode/Kilo/Crush/Kimi Code/
Copilot CLI adapters.
"""

import json
import uuid


def _call_id(prefix):
    """A fresh tool-call id for every wire call.

    IDs MUST be unique across turns: reusing one (e.g. the same
    "call_toolsearch_0" for two ToolSearch calls in one session)
    makes CodeBuddy drop the second call's result from the next
    request's messages, so the stub never sees the second tool's
    observation. Measured in the audit-86 evaluator re-probe:
    the edit_tests ToolSearch result vanished from the wire
    history with fixed ids, and the edit_tests bridge call
    never executed.
    """
    return "%s_%s" % (prefix, uuid.uuid4().hex[:24])

MCP_SERVER_NAME = "trustrun"


def codebuddy_tool_name(harness_name):
    """The deferred MCP tool name for a harness tool."""
    return "mcp__%s__%s" % (MCP_SERVER_NAME, harness_name)


def wait_for_mcp_servers_response():
    """A WaitForMcpServers wire response (first request of a call)."""
    return {
        "id": "chatcmpl-stub",
        "object": "chat.completion",
        "created": 0,
        "model": "deterministic-stub-v1",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                  "total_tokens": 15},
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": _call_id("call_wait_mcp"),
                    "type": "function",
                    "function": {
                        "name": "WaitForMcpServers",
                        "arguments": json.dumps(
                            {"servers": [MCP_SERVER_NAME]}),
                    },
                }],
            },
            "finish_reason": "tool_calls",
        }],
    }


def tool_search_response(harness_name):
    """A ToolSearch wire response loading one MCP tool's schema."""
    return {
        "id": "chatcmpl-stub",
        "object": "chat.completion",
        "created": 0,
        "model": "deterministic-stub-v1",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                  "total_tokens": 15},
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": _call_id("call_toolsearch"),
                    "type": "function",
                    "function": {
                        "name": "ToolSearch",
                        "arguments": json.dumps({
                            "tool_names": [
                                codebuddy_tool_name(harness_name)],
                        }),
                    },
                }],
            },
            "finish_reason": "tool_calls",
        }],
    }


def defer_execute_response(harness_name, args):
    """A DeferExecuteTool wire response invoking one MCP tool."""
    return {
        "id": "chatcmpl-stub",
        "object": "chat.completion",
        "created": 0,
        "model": "deterministic-stub-v1",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                  "total_tokens": 15},
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": _call_id("call_deferexec"),
                    "type": "function",
                    "function": {
                        "name": "DeferExecuteTool",
                        "arguments": json.dumps({
                            "toolName": codebuddy_tool_name(harness_name),
                            "params": args,
                        }),
                    },
                }],
            },
            "finish_reason": "tool_calls",
        }],
    }


def sse_chunks(resp):
    """Render any wire response as OpenAI SSE chunk dicts.

    CodeBuddy Code's custom-model path streams by default, so
    the stub server answers stream:true requests with these
    chunks (one content / tool-call delta, one finish chunk,
    then [DONE]).
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
                "id": call.get("id", "call_codebuddy_0"),
                "type": "function",
                "function": {
                    "name": fn.get("name", ""),
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
        "prompt_tokens": 10, "completion_tokens": 5,
        "total_tokens": 15,
    })
    return [first, last]
