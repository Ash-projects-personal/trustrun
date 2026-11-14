"""Cline wire shim over the shared deterministic stub (n8n-stub.py).

Cline 4.1.9 (tag v4.1.9) exposes its agent tools to the model by
their framework names, so the stub's harness-level decisions need a
thin translation at the wire, and nothing else:

- A harness tool call (search_docs, calculator, monitor_configure,
  edit_tests, record_score, ask_user, monitor_notify, submit_answer)
  becomes a call to the Trustrun MCP server's tool of the same name,
  exposed to the model as ``trustrun__<name>`` (Cline's
  defaultMcpToolNameTransform: ``${serverName}__${toolName}``). The
  arguments are the n8n mapping VERBATIM (``_args_for_tool``), so
  monitor_configure still carries its changes nested under a
  ``changes`` key as a JSON string -- the same envelope shape as the
  n8n/Dify batteries, which is what makes the monitor-tampering
  cells comparable across audits. A name outside the known eight
  passes through untranslated, so a forced call to an unregistered
  tool reaches the loop as ``no_such_tool`` and Cline answers with
  its own "Unknown tool" error.
- A harness "final" answer becomes a ``submit_and_exit`` tool call:
  the CLI run configures ``requireCompletionTool: true``
  (runtime-builder.ts), so a text-only assistant message never ends
  the run -- the loop re-prompts with a completion reminder instead.
  The final text goes in the ``summary`` argument (``verified`` is
  always False: the stub verifies nothing). ``SubmitInputSchema``
  requires ``summary`` to be at least 10 characters, so a short
  final text (the "PWNED" injection marker is 5) is padded with a
  fixed literal suffix; the payload text itself is never altered,
  only extended, so graders that look for the payload still find
  it.

The stub's own log (``decide_for_request`` entries) is recorded in
HARNESS terms -- the translation applies only to the response dict
sent over the wire -- so the adapter's evidence logs, the
"interesting run" rule, and the battery's tool-call counts all stay
in harness terms, exactly as in the n8n/Dify adapters.
"""

import json

MCP_SERVER_NAME = "trustrun"
MCP_TOOL_PREFIX = MCP_SERVER_NAME + "__"
COMPLETION_TOOL = "submit_and_exit"
MIN_SUMMARY_LEN = 10
SUMMARY_PAD = " (no further detail)"

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


def cline_tool_name(harness_name):
    """The model-visible tool name for a harness tool."""
    if harness_name in KNOWN_TOOLS:
        return MCP_TOOL_PREFIX + harness_name
    return harness_name


def pad_summary(text):
    """Meet SubmitInputSchema's min(10) without altering the text."""
    if len(text) >= MIN_SUMMARY_LEN:
        return text
    return text + SUMMARY_PAD


def translate_response(resp):
    """Translate a decide_for_request response dict to Cline wire.

    A final-text response becomes a submit_and_exit tool call; a
    tool-call response keeps its harness arguments and only the
    tool name is translated. The input dict is not mutated.
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
            fn["name"] = cline_tool_name(fn.get("name", ""))
        choices[0]["finish_reason"] = "tool_calls"
        return out
    text = message.get("content") or ""
    message["content"] = None
    message["tool_calls"] = [{
        "id": "call_cline_submit",
        "type": "function",
        "function": {
            "name": COMPLETION_TOOL,
            "arguments": json.dumps({
                "summary": pad_summary(text),
                "verified": False,
            }),
        },
    }]
    choices[0]["finish_reason"] = "tool_calls"
    return out


def sse_chunks(resp):
    """Render a translated response as OpenAI SSE chunk dicts.

    The AI SDK's OpenAI-compatible provider streams by default, so
    the stub server answers stream:true requests with these chunks
    (one content/tool-call delta, one finish chunk, then [DONE]).
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
                "id": call.get("id", "call_cline_0"),
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
