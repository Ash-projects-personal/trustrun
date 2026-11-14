"""Codex Responses-API wire layer over the shared deterministic stub.

Codex CLI 0.169.0 speaks ONLY the OpenAI Responses API to its model
provider (`wire_api`: "`responses` is the only supported value", per
the audited version's config reference) -- there is no Chat
Completions wire option. The shared stub (n8n-stub.py) decides on
OpenAI Chat Completions request bodies, so this module translates
both ways and renders nothing else:

- REQUEST: a Responses API `POST /v1/responses` body (`instructions`
  + `input` items + `tools`) is translated into a Chat Completions
  body (`messages` + `tools`) for `decide_for_request`. Message items
  become user/assistant messages, `function_call` items become
  assistant messages carrying tool_calls, `function_call_output`
  items become role "tool" messages, `reasoning` items are skipped
  (they carry no decision content). The stub's own log
  (`decide_for_request` entries) is recorded in HARNESS terms, so
  the adapter's evidence logs and the battery's tool-call counts
  all stay in harness terms, exactly as in the Goose adapter.
- RESPONSE: the stub's Chat Completions decision is rendered as
  Responses API SSE events (`response.created`,
  `response.output_item.added`, `response.output_text.delta` /
  `response.output_text.done`, `response.output_item.done`,
  `response.completed`) or, for non-streaming requests, as a full
  response object. The full function-call arguments ride in the
  `response.output_item.done` item: Codex's SSE parser
  (codex-rs/codex-api/src/sse/responses.rs, audited commit) leaves
  `response.function_call_arguments.delta` / `.done` UNHANDLED
  (traced and dropped), so streaming the arguments in deltas would
  lose them; the done item is what Codex parses into a
  `ResponseItem::FunctionCall`.

Tool naming: Codex offers MCP tools to the model as a Responses
API NAMESPACE (`{"type": "namespace", "name": "mcp__trustrun",
"tools": [...]}` -- the legacy `mcp__` prefix applies unless the
NonPrefixedMcpToolNames feature is enabled; see
codex-rs/codex-mcp/src/tools.rs, audited commit), with the
individual tools inside the namespace named BARE (`search_docs`,
`calculator`, ...). A model call to one of them is a
`function_call` item carrying the BARE name plus
`"namespace": "mcp__trustrun"`: the session's router builds
`ToolName::new(namespace, name)` from exactly those two fields
(codex-rs/core/src/tools/router.rs, `build_tool_call`, audited
commit), and a flat `mcp__trustrun__search_docs` name is rejected
as "unsupported call" (measured in the probe). The stub's
harness-level decisions therefore need ONE wire translation at the
render layer (see WIRE_NAMESPACE below): bare name + namespace;
Codex strips the namespace again before calling the MCP server,
so the bridge sees the bare harness name. A harness "final" answer
passes through as plain text content (no tool call), which ends
Codex's loop (the loop continues only while the response carries
tool calls). Non-harness names (a forced probe call to a builtin
or an unregistered name) pass through with no namespace, so the
re-probe measures what Codex does with the real name.
"""

import json
import re
import uuid

# Codex renders each MCP tool result as TWO input_text parts in the
# function_call_output item: "Wall time: <seconds> seconds\nOutput:"
# then the bare result string. The decimal seconds are wire framing,
# not tool content -- but the stub decides on the joined string, and
# its year regex (\b(1|2)\d{3}\b) matches the digits inside the
# decimal: "0.1154" reads as year 1154, so t4_multistep ("find the
# year Virgin Australia started operating, then add 24") computed
# 1154 + 24 = 1178 instead of 2000 + 24 = 2024 (audit 75, t1 slice).
# The translator therefore strips the framing prefix before the stub
# sees the result; the raw wire value is still kept in the adapter's
# observation_raw log field.
_WALL_TIME_PREFIX = re.compile(
    r"^Wall time: [0-9.]+ seconds\nOutput:")


def _strip_wall_time_prefix(text):
    """Drop Codex's "Wall time: ...\nOutput:" framing from a tool
    result, leaving the bare result the stub decides on."""
    if not isinstance(text, str):
        return text
    return _WALL_TIME_PREFIX.sub("", text, count=1)

# Codex 0.169.0 offers MCP tools to the model as a Responses API
# namespace named `mcp__trustrun` (see the module docstring). The
# stub's harness decisions therefore need ONE wire translation at
# the render layer: the function_call item carries the BARE harness
# name plus this namespace. The probe log confirms the offered
# names (see codex-requests.jsonl).
WIRE_NAMESPACE = "mcp__trustrun"
# Only the 8 harness tools are namespaced; a forced probe call to a
# non-harness tool passes through with its name unchanged and no
# namespace.
HARNESS_TOOLS = frozenset((
    "search_docs", "calculator", "monitor_configure", "edit_tests",
    "record_score", "ask_user", "monitor_notify", "submit_answer",
))

# Item types seen in Responses API `input` that carry no decision
# content for the stub; recorded by the translator for the probe
# log so an unexpected shape is visible, not silently dropped.
SKIPPED_ITEM_TYPES = set()


def _wire_item(name, arguments, call_id):
    """Render one stub tool call as a Responses API function_call
    item: bare harness name + the `mcp__trustrun` namespace for the
    8 harness tools, plain name with no namespace otherwise."""
    item = {
        "type": "function_call",
        "id": call_id,
        "call_id": call_id,
        "name": name,
        "arguments": arguments,
        "status": "completed",
    }
    if name in HARNESS_TOOLS:
        item["namespace"] = WIRE_NAMESPACE
    return item


def _item_text(content):
    """Plain text of a Responses API message content list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if isinstance(block.get("text"), str):
                    parts.append(block["text"])
                elif block.get("type") == "input_image":
                    parts.append("[image]")
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return "" if content is None else str(content)


def _output_text(output):
    """Plain text of a function_call_output `output` value.

    Codex sends the MCP tool result as the output string; the MCP
    content-array shape ([{"type":"text","text":"..."}]) and the n8n
    list shapes ([{output|response|error}]) are handled too, so the
    shared stub logic sees the bare tool-result string.
    """
    if isinstance(output, str):
        text = output.strip()
        if not text.startswith("[") and not text.startswith("{"):
            return output
        try:
            parsed = json.loads(text)
        except ValueError:
            return output
        if isinstance(parsed, dict):
            content = parsed.get("content")
            if isinstance(content, list) and content:
                parts = []
                for item in content:
                    if isinstance(item, dict) and isinstance(
                            item.get("text"), str):
                        parts.append(item["text"])
                    elif isinstance(item, str):
                        parts.append(item)
                if parts:
                    return "".join(parts)
            if "error" in parsed:
                err = parsed["error"]
                err = err if isinstance(err, str) else json.dumps(err)
                return "error:" + err
            return output
        if isinstance(parsed, list) and parsed and isinstance(
                parsed[0], dict):
            item = parsed[0]
            if isinstance(item.get("text"), str):
                return item["text"]
            for key in ("output", "response"):
                if key in item:
                    out = item[key]
                    return out if isinstance(out, str) else json.dumps(out)
            if "error" in item:
                err = item["error"]
                err = err if isinstance(err, str) else json.dumps(err)
                return "error:" + err
        return output
    if isinstance(output, list):
        return _item_text(output)
    return "" if output is None else str(output)


def responses_to_chat_body(body):
    """Translate a Responses API request body to a Chat Completions
    body for decide_for_request.

    Returns (chat_body, skipped_types). `instructions` becomes the
    system message; the first user message is the task text the stub
    keys on. Function-call items become assistant tool_call messages
    (wire names, as Codex sent them); function_call_output items
    become role "tool" messages whose content is the unwrapped tool
    result string.
    """
    messages = []
    instructions = body.get("instructions")
    if isinstance(instructions, str) and instructions:
        messages.append({"role": "system", "content": instructions})
    skipped = []
    for item in body.get("input") or []:
        if not isinstance(item, dict):
            continue
        kind = item.get("type")
        if kind == "message":
            role = item.get("role") or "user"
            text = _item_text(item.get("content"))
            # Codex prepends a user-role `<environment_context>`
            # wrapper (cwd, shell, date, workspace roots) ahead of
            # the real prompt on every request. The stub keys its
            # task text on the FIRST user message, so the wrapper
            # would make it decide on the date string instead of the
            # task (measured in the probe: it "calculated"
            # 2026-11-14). The wrapper is framework-added context,
            # not task content, so it is dropped from the stub's
            # view; the task itself arrives verbatim as the next
            # user message. No task in the battery starts with this
            # marker.
            if role == "user" and text.startswith("<environment_context>"):
                skipped.append("environment_context")
                SKIPPED_ITEM_TYPES.add("environment_context")
                continue
            messages.append({"role": role, "content": text})
        elif kind in ("function_call", "custom_tool_call"):
            fn_name = item.get("name") or ""
            args = item.get("arguments")
            if not isinstance(args, str):
                args = json.dumps(args if args is not None else {})
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": item.get("call_id") or item.get("id") or
                    "call_stub",
                    "type": "function",
                    "function": {"name": fn_name, "arguments": args},
                }],
            })
        elif kind == "function_call_output":
            messages.append({
                "role": "tool",
                "content": _strip_wall_time_prefix(
                    _output_text(item.get("output"))),
                "tool_call_id": item.get("call_id") or "",
            })
        elif kind in ("reasoning", "item_reference"):
            skipped.append(kind)
            SKIPPED_ITEM_TYPES.add(kind)
        else:
            skipped.append(kind)
            SKIPPED_ITEM_TYPES.add(kind)
    tools = []
    for tool in body.get("tools") or []:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") == "function":
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters") or {},
                },
            })
    chat_body = {"messages": messages, "tools": tools}
    if body.get("model"):
        chat_body["model"] = body["model"]
    return chat_body, skipped


def _response_object(resp, response_id):
    """Render a stub Chat Completions decision as a Responses API
    response object (the `response` payload of response.created /
    response.completed, and the whole body for non-streaming)."""
    message = (resp.get("choices") or [{}])[0].get("message") or {}
    output = []
    tool_calls = message.get("tool_calls")
    if tool_calls:
        for call in tool_calls:
            fn = call.get("function") or {}
            call_id = call.get("id") or "call_" + uuid.uuid4().hex[:24]
            output.append(_wire_item(
                fn.get("name", ""), fn.get("arguments", ""), call_id))
    else:
        text = message.get("content") or ""
        output.append({
            "type": "message",
            "id": "msg_" + uuid.uuid4().hex[:12],
            "status": "completed",
            "role": "assistant",
            "content": [{"type": "output_text", "text": text,
                         "annotations": []}],
        })
    # Responses API usage uses input/output token keys; the stub's
    # Chat Completions usage (prompt/completion tokens) is mapped.
    # Codex's ResponseCompleted parser requires input_tokens,
    # output_tokens, and total_tokens (codex-rs/codex-api/src/sse/
    # responses.rs, audited commit) -- a usage object without them
    # fails the stream with "missing field `input_tokens`" and
    # Codex retries the turn 5 times.
    usage = resp.get("usage") or {}
    responses_usage = {
        "input_tokens": usage.get("prompt_tokens", 10),
        "output_tokens": usage.get("completion_tokens", 5),
        "total_tokens": usage.get("total_tokens", 15),
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    }
    return {
        "id": response_id,
        "object": "response",
        "created_at": resp.get("created", 0),
        "status": "completed",
        "model": resp.get("model", "deterministic-stub-v1"),
        "output": output,
        "usage": responses_usage,
    }


def response_events(resp):
    """Render a stub Chat Completions decision as Responses API SSE
    event dicts, in the order Codex's parser handles: created, item
    added, text deltas + text done (message items only), item done
    (carrying the FULL item -- function-call arguments included,
    since Codex leaves function_call_arguments delta/done events
    unhandled), completed."""
    response_id = "resp_" + uuid.uuid4().hex[:24]
    obj = _response_object(resp, response_id)
    events = [{
        "type": "response.created",
        "response": {"id": response_id, "object": "response",
                     "status": "in_progress",
                     "model": obj["model"], "output": []},
    }]
    for index, item in enumerate(obj["output"]):
        events.append({
            "type": "response.output_item.added",
            "output_index": index,
            "item": dict(item, status="in_progress"),
        })
        if item["type"] == "message":
            text = ""
            for block in item.get("content") or []:
                if isinstance(block, dict) and isinstance(
                        block.get("text"), str):
                    text += block["text"]
            events.append({
                "type": "response.output_text.delta",
                "item_id": item["id"],
                "output_index": index,
                "content_index": 0,
                "delta": text,
            })
            events.append({
                "type": "response.output_text.done",
                "item_id": item["id"],
                "output_index": index,
                "content_index": 0,
                "text": text,
            })
        events.append({
            "type": "response.output_item.done",
            "output_index": index,
            "item": item,
        })
    events.append({"type": "response.completed", "response": obj})
    return events


def response_object(resp):
    """Render a stub decision as a full Responses API response
    object (non-streaming requests)."""
    response_id = "resp_" + uuid.uuid4().hex[:24]
    return _response_object(resp, response_id)
