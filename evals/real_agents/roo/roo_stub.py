"""Roo Code wire shim over the shared deterministic stub (n8n-stub.py).

Roo Code 3.54.0 (tag v3.54.0) exposes MCP tools to the model as
native tools named ``mcp--<server>--<tool>`` (the "native MCP tool
calling" path: a model call to ``mcp--trustrun--search_docs`` is
converted by presentAssistantMessage into the same execution path
as the ``use_mcp_tool`` gateway -- same UseMcpToolTool handler,
same use_mcp_server approval ask, same result formatting -- but
preserves the native name in API history). The stub's
harness-level decisions therefore need a thin translation at the
wire, and nothing else:

- A harness tool call (search_docs, calculator, monitor_configure,
  edit_tests, record_score, ask_user, monitor_notify, submit_answer)
  becomes a call to ``mcp--trustrun--<name>`` with the n8n argument
  mapping VERBATIM (``_args_for_tool``), so monitor_configure still
  carries its changes nested under a ``changes`` key as a JSON
  string -- the same envelope shape as the n8n/Dify/Cline batteries,
  which is what makes the monitor-tampering cells comparable across
  audits. A name outside the known eight passes through untranslated
  as ``mcp--trustrun--<name>``, so a forced call to an unregistered
  tool reaches Roo Code's own use_mcp_tool validation (which rejects
  an unknown tool on the server before dispatch) instead of the
  bridge. (The legacy ``use_mcp_tool`` gateway would execute the
  same handler, but it is NOT what Roo Code offers the model: with
  an MCP server configured the tool list carries the native
  ``mcp--`` names and no gateway tool, so the shim uses the names
  the framework presents -- the Cline analog, where the shim uses
  Cline's ``trustrun__<name>`` names.)
- A harness "final" answer becomes an ``attempt_completion`` tool
  call with the final text as ``result``. Roo Code has no minimum
  summary length (unlike Cline's SubmitInputSchema), so no padding
  is applied: the "PWNED" injection marker reaches the completion
  result verbatim.

The stub's own log (``decide_for_request`` entries) is recorded in
HARNESS terms -- the translation applies only to the response dict
sent over the wire -- so the adapter's evidence logs, the
"interesting run" rule, and the battery's tool-call counts all stay
in harness terms, exactly as in the n8n/Dify/Cline adapters.
"""

import json

MCP_SERVER_NAME = "trustrun"
MCP_TOOL_PREFIX = "mcp--" + MCP_SERVER_NAME + "--"
COMPLETION_TOOL = "attempt_completion"

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


def roo_tool_name(harness_name):
    """The model-visible tool name for a harness tool."""
    return MCP_TOOL_PREFIX + harness_name


def roo_tool_call(harness_name, harness_args):
    """The model-visible tool call for one harness tool call.

    Returns (tool_name, arguments_dict): the native mcp-- name with
    the harness arguments mapped verbatim.
    """
    return roo_tool_name(harness_name), harness_args


def translate_response(resp):
    """Translate a decide_for_request response dict to Roo wire.

    A final-text response becomes an attempt_completion tool call; a
    tool-call response becomes a native mcp--trustrun--<name> call
    keeping its harness arguments. The input dict is not mutated.
    """
    out = json.loads(json.dumps(resp))
    choices = out.get("choices") or []
    if not choices:
        return out
    message = choices[0].get("message") or {}
    tool_calls = message.get("tool_calls")
    if tool_calls:
        for call in tool_calls:
            fn = call.get("function") or {}
            harness_name = fn.get("name", "")
            try:
                harness_args = json.loads(fn.get("arguments") or "{}")
            except ValueError:
                harness_args = {}
            name, args = roo_tool_call(harness_name, harness_args)
            fn["name"] = name
            fn["arguments"] = json.dumps(args)
        choices[0]["finish_reason"] = "tool_calls"
        return out
    text = message.get("content") or ""
    message["content"] = None
    message["tool_calls"] = [{
        "id": "call_roo_complete",
        "type": "function",
        "function": {
            "name": COMPLETION_TOOL,
            "arguments": json.dumps({"result": text}),
        },
    }]
    choices[0]["finish_reason"] = "tool_calls"
    return out


def sse_chunks(resp):
    """Render a translated response as OpenAI SSE chunk dicts.

    Roo Code's OpenAI handler streams by default (the openai SDK's
    chat.completions.create with stream:true), so the stub server
    answers stream:true requests with these chunks (one content /
    tool-call delta, one finish chunk, then [DONE]).
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
                "id": call.get("id", "call_roo_0"),
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
