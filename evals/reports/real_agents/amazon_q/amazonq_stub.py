"""Amazon Q Developer CLI wire layer over the shared deterministic stub.

Amazon Q CLI 1.19.7 (audit 76) speaks the Amazon Q Developer
Streaming API to its model: POST / with Content-Type
application/x-amz-json-1.0 and X-Amz-Target
AmazonQDeveloperStreamingService.SendMessage (SigV4-signed with
dummy env credentials; the stub ignores signatures), JSON body
(SendMessageInput: conversationState), and the response is an AWS
event stream (application/vnd.amazon.eventstream). This module
translates both ways and renders nothing else:

- REQUEST: a SendMessage JSON body (conversationState with
  currentMessage + history) is translated into a Chat Completions
  body (messages + tools) for the shared stub decision logic
  (DeterministicStub from evals/real_agents/crewai_adapter.py,
  the audit-30 decision table mirrored step for step). The user
  message arrives wrapped in "--- USER MESSAGE BEGIN ---" /
  "--- USER MESSAGE END ---" markers with a "--- CONTEXT ENTRY
  BEGIN ---" time block ahead of it; the wrappers are stripped so
  the stub sees the bare task text. Tool results arrive in
  userInputMessageContext.toolResults (and in history entries);
  they become role "tool" messages, which the stub's
  _latest_observation prefers. The raw wire body is kept in the
  adapter's request log as the audit trail.
- RESPONSE: the stub's decision is rendered as AWS event-stream
  frames. A final answer is one assistantResponseEvent frame
  (the :event-type value is the Smithy member name in
  lowerCamelCase -- "assistantResponseEvent" -- because the
  generated unmarshaller matches on smithy_type verbatim and the
  PascalCase form falls through to Unknown; measured in the
  probe: the PascalCase run reached the stub but printed
  nothing). A tool call is two toolUseEvent frames: the first
  carries toolUseId + name with input null and stop false (the
  parser's ToolUseStart), the second carries the JSON arguments
  string with stop true (parse_tool_use accumulates input
  strings until stop). The stream then closes, which the parser
  turns into EndStream. The full event bytes are the response;
  there is no SSE text layer.

Tool naming: the CLI offers MCP tools to the model under their
BARE names (WIRE_NAMES below, read off the probe wire log --
the CLI's tools list in the SendMessage request carries
search_docs, calculator, ... with no server prefix; the
NAMESPACE_DELIMITER "___" in tool_manager.rs is used for
aliases/display, not for the model-facing spec). The stub
decides on bare harness names, so the wire mapping is the
identity; the bridge sees the same bare name when the CLI
calls the MCP server. A forced probe call to a non-harness
tool passes through with its name unchanged. (First probe
guess was trustrun___<name>; the CLI rejected it as "No tool
with trustrun___search_docs is found" and retried the request
1,171 times -- the bare-name fix is measured, not assumed.)
"""

import importlib.util
import json
import os
import re
import struct
import uuid
import zlib

# The shared deterministic stub (audit-30 decision table) lives
# in evals/real_agents/crewai_adapter.py as a self-contained copy
# (the n8n-venv copy the Goose/Codex adapters imported is no
# longer on disk). It is loaded read-only via importlib, the same
# pattern as the Codex adapter; its own `from agents import ...`
# needs evals/ on sys.path, which the adapter and the runner both
# ensure before importing this module.
_HERE = os.path.dirname(os.path.abspath(__file__))
_CREWAI_PATH = os.path.normpath(os.path.join(
    _HERE, "..", "..", "..", "real_agents", "crewai_adapter.py"))
_spec = importlib.util.spec_from_file_location(
    "amazonq_crewai_stub", _CREWAI_PATH)
_crewai_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_crewai_mod)
DeterministicStub = _crewai_mod.DeterministicStub
_find_injection = _crewai_mod._find_injection

# Model-facing tool names, read off the probe wire log (the tools
# list in the CLI's SendMessage request). Filled in after the
# MCP probe; the harness names are the keys.
WIRE_NAMES = {
    "search_docs": "search_docs",
    "calculator": "calculator",
    "monitor_configure": "monitor_configure",
    "edit_tests": "edit_tests",
    "record_score": "record_score",
    "ask_user": "ask_user",
    "monitor_notify": "monitor_notify",
    "submit_answer": "submit_answer",
}

HARNESS_TOOLS = frozenset(WIRE_NAMES)

_USER_BEGIN = "--- USER MESSAGE BEGIN ---\n"
_USER_END = "--- USER MESSAGE END ---"
_CONTEXT_BEGIN = "--- CONTEXT ENTRY BEGIN ---"


def _crc(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def event_frame(event_type, payload):
    """One AWS event-stream message frame (binary).

    Prelude: total length + headers length + prelude CRC32.
    Headers: :message-type=event, :event-type=<member>,
    :content-type=application/json (string headers, type 7).
    Payload: JSON bytes. Trailing message CRC32.
    """
    headers = b""

    def header(name, value):
        raw = value.encode("utf-8")
        return (bytes([len(name)]) + name.encode("utf-8") + bytes([7])
                + struct.pack(">H", len(raw)) + raw)

    headers += header(":message-type", "event")
    headers += header(":event-type", event_type)
    headers += header(":content-type", "application/json")
    total = 12 + len(headers) + len(payload) + 4
    prelude = struct.pack(">II", total, len(headers))
    body = prelude + struct.pack(">I", _crc(prelude)) + headers + payload
    return body + struct.pack(">I", _crc(body))


def _clean_user_text(content):
    """Strip the CLI's user-message wrappers (context entry +
    USER MESSAGE BEGIN/END markers), leaving the bare task text."""
    if not isinstance(content, str):
        return "" if content is None else str(content)
    text = content
    begin = text.find(_USER_BEGIN)
    if begin != -1:
        text = text[begin + len(_USER_BEGIN):]
        end = text.find(_USER_END)
        if end != -1:
            text = text[:end]
        return text
    if text.startswith(_CONTEXT_BEGIN):
        # No USER MESSAGE markers: drop the context-entry block.
        end = text.find("--- CONTEXT ENTRY END ---")
        if end != -1:
            text = text[end + len("--- CONTEXT ENTRY END ---"):]
    return text.strip()


def _tool_result_text(result):
    """Plain text of one ToolResult (content blocks joined).

    Measured wire shape: {"toolUseId", "content": [{"json":
    {"content": [{"type": "text", "text": "..."}]}}], "status":
    "success"} -- the MCP content array is nested inside a
    "json" block. Text is collected recursively so nested
    MCP/JSON wrappers never leak framing into the observation.
    """
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return "" if result is None else str(result)
    texts = []

    def collect(value):
        if isinstance(value, dict):
            if isinstance(value.get("text"), str):
                texts.append(value["text"])
                return
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(result.get("content"))
    if texts:
        return "".join(texts)
    if isinstance(result.get("text"), str):
        return result["text"]
    status = result.get("status")
    if status and status != "success":
        return "error: tool result status %s" % status
    return json.dumps(result)


def _message_of(entry, *names):
    """First matching member of a ChatMessage union entry.

    The wire uses lowerCamelCase member names
    ("userInputMessage", "assistantResponseMessage"); the
    PascalCase Rust variant names are accepted defensively.
    """
    if not isinstance(entry, dict):
        return None
    for name in names:
        if isinstance(entry.get(name), dict):
            return entry[name]
    return None


def _collect_tool_results(body):
    """All tool results in a SendMessage body, in order.

    Results travel in userInputMessageContext.toolResults of the
    current message and of history UserInputMessage entries. A
    raising tool arrives as a ToolResult with status "error" (or
    an isError MCP result rendered as text); the stub's error
    branch keys on an "error:" prefix, so error results are
    prefixed when the content does not already carry one.
    """
    results = []

    def from_context(ctx):
        if not isinstance(ctx, dict):
            return
        for item in ctx.get("toolResults") or []:
            if not isinstance(item, dict):
                continue
            text = _tool_result_text(item)
            status = item.get("status")
            if status and str(status).lower() not in ("success",):
                if not text.lower().startswith("error:"):
                    text = "error: " + text
            results.append(text)

    conv = (body or {}).get("conversationState") or {}
    for entry in conv.get("history") or []:
        user_msg = _message_of(entry, "userInputMessage",
                               "UserInputMessage")
        if user_msg is not None:
            from_context(user_msg.get("userInputMessageContext"))
    current = conv.get("currentMessage") or {}
    user_msg = _message_of(current, "userInputMessage",
                           "UserInputMessage")
    if user_msg is not None:
        from_context(user_msg.get("userInputMessageContext"))
    return results


def q_to_chat_body(body):
    """Translate a SendMessage request body to a Chat Completions
    body for the shared stub.

    Returns (chat_body, notes). messages: the cleaned task text
    as the user message, then one role "tool" message per tool
    result in order (the stub's _latest_observation takes the
    last tool message). tools: the model-facing tool specs from
    userInputMessageContext.tools, mapped back to harness names
    where the wire name is known.
    """
    conv = (body or {}).get("conversationState") or {}
    current = conv.get("currentMessage") or {}
    user_msg = _message_of(current, "userInputMessage",
                           "UserInputMessage") or {}
    task_text = _clean_user_text(user_msg.get("content") or "")
    messages = []
    if task_text:
        messages.append({"role": "user", "content": task_text})
    for text in _collect_tool_results(body):
        messages.append({"role": "tool", "content": text})
    tools = []
    ctx = user_msg.get("userInputMessageContext") or {}
    for spec in ctx.get("tools") or []:
        if not isinstance(spec, dict):
            continue
        inner = spec.get("toolSpecification") or spec
        name = inner.get("name", "")
        harness = None
        for h, wire in WIRE_NAMES.items():
            if wire == name:
                harness = h
                break
        tools.append({
            "type": "function",
            "function": {
                "name": harness or name,
                "description": inner.get("description", ""),
                "parameters": (inner.get("inputSchema") or {}).get(
                    "json") or {},
            },
        })
    return {"messages": messages, "tools": tools}, {}


def decide_for_request(stub, chat_body):
    """Run the shared stub on a translated body.

    Mirrors the missing n8n-stub.py helper's contract (see the
    Codex adapter): returns (resp, entry) where resp is a Chat
    Completions response dict and entry is the stub log entry for
    this decision. Honors a forced first call (stub._forced,
    set by the adapter's force_first_call hook) exactly once.
    The log entry is appended exactly the way the stub's own
    next_response does it, so the battery's evidence logs keep
    the same shape as the other audits.
    """
    messages = chat_body.get("messages") or []
    observation = stub._latest_observation(messages)
    stub.log.append({
        "step": len(stub.log),
        "observation": observation,
        "observation_had_injection": (
            bool(observation) and _find_injection(observation)
        ),
    })
    forced = getattr(stub, "_forced", None)
    if forced is not None:
        stub._forced = None
        kind, payload = "tool", (forced.get("name"),
                                 forced.get("args") or {})
    else:
        kind, payload = stub._decide(observation)
    stub.log[-1]["action_kind"] = kind
    stub.log[-1]["action"] = payload
    stub._call_n += 1
    if kind == "tool":
        name, args = payload
        resp = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "call_%d" % stub._call_n,
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(args),
                        },
                    }],
                },
                "finish_reason": "tool_calls",
            }],
            "model": "deterministic-stub-v1",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "total_tokens": 15},
        }
    else:
        resp = {
            "choices": [{
                "message": {"role": "assistant", "content": payload},
                "finish_reason": "stop",
            }],
            "model": "deterministic-stub-v1",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                      "total_tokens": 15},
        }
    return resp, stub.log[-1]


def _wire_name(name):
    """Model-facing name for a stub tool call: the mapped wire
    name for the 8 harness tools, the bare name otherwise (a
    forced probe call to a builtin or unregistered name)."""
    return WIRE_NAMES.get(name, name)


def response_frames(resp):
    """Render a stub Chat Completions decision as AWS
    event-stream frames (bytes), in the order the CLI's parser
    consumes them: a tool call is a ToolUseEvent start frame
    (input null, stop false) followed by a ToolUseEvent frame
    carrying the full JSON arguments string with stop true; a
    final answer is a single assistantResponseEvent frame. The
    HTTP response ends after these frames, which the parser
    turns into EndStream."""
    message = (resp.get("choices") or [{}])[0].get("message") or {}
    frames = []
    tool_calls = message.get("tool_calls")
    if tool_calls:
        for call in tool_calls:
            fn = call.get("function") or {}
            call_id = call.get("id") or "call_" + uuid.uuid4().hex[:12]
            name = _wire_name(fn.get("name", ""))
            args = fn.get("arguments", "")
            if not isinstance(args, str):
                args = json.dumps(args if args is not None else {})
            frames.append(event_frame("toolUseEvent", json.dumps({
                "toolUseId": call_id, "name": name,
                "input": None, "stop": False,
            }).encode("utf-8")))
            frames.append(event_frame("toolUseEvent", json.dumps({
                "toolUseId": call_id, "name": name,
                "input": args, "stop": True,
            }).encode("utf-8")))
    else:
        text = message.get("content") or ""
        frames.append(event_frame("assistantResponseEvent", json.dumps({
            "content": text,
        }).encode("utf-8")))
    return frames
