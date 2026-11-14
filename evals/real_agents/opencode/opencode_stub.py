"""OpenCode wire shim over the shared deterministic stub (n8n-stub.py).

OpenCode 2.3.0 (tag v2.3.0) exposes MCP tools to the model ONLY
inside Code Mode by default: tools with codemode !== false are not
offered as individual model tools. The model gets one `execute`
tool (run JavaScript in a confined Code Mode runtime) plus the
direct tools (edit, read, write, shell, ...). MCP tools are called
from inside Code Mode JS through the `tools` object, at the
qualified path `tools.<namespace>.<name>(input)` -- for the
trustrun server, `tools.trustrun["search_docs"]({query: ...})`.

The stub's harness-level decisions therefore need a thin
translation at the wire, and nothing else:

- A harness tool call (search_docs, calculator, monitor_configure,
  edit_tests, record_score, ask_user, monitor_notify, submit_answer)
  becomes an `execute` tool call whose `code` awaits the matching
  Code Mode tool call with the n8n argument mapping VERBATIM
  (`_args_for_tool`), so monitor_configure still carries its
  changes nested under a `changes` key as a JSON string -- the
  same envelope shape as the n8n/Dify/Cline/Roo batteries, which
  is what makes the monitor-tampering cells comparable across
  audits. A name outside the known eight passes through as
  `tools.trustrun["<name>"](args)`, so a forced call to an
  unregistered tool reaches OpenCode's own Code Mode tool
  resolution (which rejects an unknown tool) instead of the
  bridge.
- A harness "final" answer becomes plain text content (no tool
  call): OpenCode's loop ends on a text response, so no terminal
  tool is needed -- unlike Roo Code's attempt_completion.

The stub's own log (`decide_for_request` entries) is recorded in
HARNESS terms -- the translation applies only to the response
dict sent over the wire -- so the adapter's evidence logs, the
"interesting run" rule, and the battery's tool-call counts all
stay in harness terms, exactly as in the n8n/Dify/Cline/Roo
adapters.
"""

import json

MCP_SERVER_NAME = "trustrun"
EXECUTE_TOOL = "execute"

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


def opencode_tool_name(harness_name):
    """The Code Mode qualified path for a harness tool."""
    return "tools.%s[%s]" % (MCP_SERVER_NAME, json.dumps(harness_name))


def opencode_tool_code(harness_name, harness_args):
    """The Code Mode JS for one harness tool call.

    Returns the `code` string for the `execute` tool: a single
    awaited call to the namespaced tool with the harness
    arguments mapped verbatim, returned as the program result.
    """
    return "return await %s(%s);" % (
        opencode_tool_name(harness_name),
        json.dumps(harness_args),
    )


def translate_response(resp):
    """Translate a decide_for_request response dict to OpenCode wire.

    A final-text response passes through unchanged (plain text
    ends the loop). A tool-call response becomes a single
    `execute` tool call whose code awaits the matching Code Mode
    tool. The input dict is not mutated.
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
    try:
        harness_args = json.loads(fn.get("arguments") or "{}")
    except ValueError:
        harness_args = {}
    code = opencode_tool_code(harness_name, harness_args)
    fn["name"] = EXECUTE_TOOL
    fn["arguments"] = json.dumps({"code": code})
    choices[0]["finish_reason"] = "tool_calls"
    return out


def sse_chunks(resp):
    """Render a translated response as OpenAI SSE chunk dicts.

    OpenCode's openai-compatible provider streams by default, so
    the stub server answers stream:true requests with these
    chunks (one content / tool-call delta, one finish chunk, then
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
                "id": call.get("id", "call_opencode_0"),
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
