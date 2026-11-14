"""Continue wire shim over the shared deterministic stub (n8n-stub.py).

Continue 1.5.47 (CLI `cn`) offers MCP tools to the model as
INDIVIDUAL model tools (unlike OpenCode 2.3.0, which hides them
behind the Code Mode `execute` gateway): the model gets a
`search_docs` function tool, a `calculator` function tool, and so
on, plus Continue's built-ins. The stub's harness-level decisions
therefore need NO translation at the wire: a harness tool call
passes through with its name and arguments exactly as
`decide_for_request` rendered them, and a harness "final" answer
passes through as plain text content (no tool call), which ends
Continue's loop (the loop continues only while the response
carries tool calls).

The only rendering this module does is the OpenAI SSE chunk
shape Continue's OpenAI provider streams by default: one delta
chunk (content or a single tool call) plus one finish chunk, then
[DONE]. The stub's own log (`decide_for_request` entries) is
recorded in HARNESS terms, so the adapter's evidence logs, the
"interesting run" rule, and the battery's tool-call counts all
stay in harness terms, exactly as in the n8n/Dify/Cline/Roo/
OpenCode adapters.
"""

import json


def sse_chunks(resp):
    """Render a decide_for_request response as OpenAI SSE chunk dicts.

    Continue's OpenAI provider streams by default, so the stub
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
                "id": call.get("id", "call_continue_0"),
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
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
    })
    return [first, last]
