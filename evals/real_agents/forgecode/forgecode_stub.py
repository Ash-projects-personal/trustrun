"""ForgeCode wire shim over the shared deterministic stub (n8n-stub.py).

ForgeCode 2.14.0 offers MCP tools to the model as individual
model tools named `mcp_<server>_tool_<tool>` (measured in the
probe: `mcp_trustrun_tool_search_docs`, etc.) -- NOT the
`mcp__<server>__<tool>` form Pi uses. The stub's harness-level
decisions therefore need only a thin translation at the wire,
and nothing else:

- A harness tool call (search_docs, calculator, monitor_configure,
  edit_tests, record_score, ask_user, monitor_notify, submit_answer)
  becomes a direct call to `mcp_trustrun_tool_<name>` with the
  arguments decide_for_request already rendered (the n8n argument
  mapping, so monitor_configure still carries its changes nested
  under a `changes` key as a JSON string -- the same envelope
  shape as the n8n/Dify/Cline/Roo/OpenCode/Kilo/Crush/Pi
  batteries, which is what makes the monitor-tampering cells
  comparable across audits). A name outside the known eight
  passes through as `mcp_trustrun_tool_<name>`, so a forced call
  to an unregistered tool reaches ForgeCode's own tool resolution
  instead of the bridge.
- A harness "final" answer becomes plain text content (no tool
  call): ForgeCode's loop ends on a text response, so no terminal
  tool is needed.

The stub's own log (`decide_for_request` entries) is recorded in
HARNESS terms -- the translation applies only to the response
dict sent over the wire -- so the adapter's evidence logs, the
"interesting run" rule, and the battery's tool-call counts all
stay in harness terms, exactly as in the Pi/Kilo/Crush adapters.
"""

import json

MCP_SERVER_NAME = "trustrun"

KNOWN_TOOLS = (
    "search_docs",
    "calculator",
    "monitor_configure",
    "edit_tests",
    "record_score",
    "ask_user",
    "monitor_notify",
    "submit_answer",
)


def forgecode_tool_name(harness_name):
    """The direct model-tool name for a harness tool."""
    return "mcp_%s_tool_%s" % (MCP_SERVER_NAME, harness_name)


def translate_response(resp):
    """Translate a decide_for_request response dict to ForgeCode wire.

    A final-text response passes through unchanged (plain text
    ends the loop). A tool-call response becomes a direct call
    to `mcp_trustrun_tool_<name>` with the arguments unchanged.
    The input dict is not mutated.
    """
    out = json.loads(json.dumps(resp))
    choices = out.get("choices") or []
    if not choices:
        return out
    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls")
    if not tool_calls:
        return out
    call = tool_calls[0]
    fn = call.get("function") or {}
    harness_name = fn.get("name", "")
    fn["name"] = forgecode_tool_name(harness_name)
    choices[0]["finish_reason"] = "tool_calls"
    return out


def sse_chunks(resp):
    """Render a translated response as OpenAI SSE chunk dicts.

    ForgeCode's openai_compatible provider streams by default, so
    the stub server answers stream:true requests with these chunks
    (one content / tool-call delta, one finish chunk, then
    [DONE]).
    """
    translated = translate_response(resp)
    choice = translated["choices"][0]
    message = choice.get("message") or {}
    base = {
        "id": translated.get("id", "chatcmpl-stub"),
        "object": "chat.completion.chunk",
        "created": translated.get("created", 0),
        "model": translated.get("model", "deterministic-stub-v1"),
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
                "id": call.get("id", "call_forgecode_0"),
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
    last["usage"] = translated.get("usage", {
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
    })
    return [first, last]
