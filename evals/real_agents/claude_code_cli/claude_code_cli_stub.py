"""Claude Code CLI wire shim over the shared deterministic stub
(n8n-stub.py) for audit 87.

Claude Code CLI 2.1.327 (tag v2.1.327) speaks the Anthropic
Messages API and offers MCP tools to the model as DEFERRED tools
behind the built-in ToolSearch tool (the audit-65 SDK precedent):
the tools list the stub receives carries 12 built-ins (Agent,
Bash, Edit, ListAgents, Read, ReportFindings, ScheduleWakeup,
Skill, ToolSearch, Workflow, DeferredToolPlaceholder, Write) and
NO MCP tool. A harness tool call therefore takes two turns:

- the stub emits ToolSearch {"query": "select:mcp__trustrun__<name>"};
  the CLI answers with a tool_result carrying a tool_reference
  block for that tool plus a "Tool loaded." text message;
- the stub then emits the real tool_use mcp__trustrun__<name>
  with the harness arguments; the CLI executes the MCP tool and
  returns its text as a tool_result block.

The stub's own log (decide_anthropic entries) is recorded in
HARNESS terms -- the ToolSearch hop and the mcp__ prefix apply
only to the wire events -- so the adapter's evidence logs, the
"interesting run" rule, and the battery's tool-call counts all
stay in harness terms, exactly as in the n8n/Dify/Cline/Roo/
OpenCode/Kilo/Crush/Kimi Code/Copilot CLI adapters.

Wire facts measured in the probes
(trustrun-venvs/claude-code-venv/claude-code-probe{3,4,6}.py):
- One POST /v1/messages?beta=true per turn, model
  claude-opus-5-5, stream True. The CLI requires streaming SSE
  (non-streaming JSON fails with StreamNoEventsError, audit-65)
  AND the stub must send `Connection: close` and close the
  connection after the final SSE event (keep-alive hangs the CLI).
- The task text arrives as its own user message, verbatim, AFTER
  three system-reminder user messages (the /home/hatch/AGENTS.md
  contents, a gitStatus reminder, an attribution reminder) -- the
  CLI walks up from cwd and injects them. The shim finds the user
  message carrying the known task text verbatim and decides on
  exactly that text (the Copilot CLI <current_datetime> / Crush
  system_reminder precedent); the reminders never reach the stub's
  decision table.
- The CLI coalesces consecutive tool results into ONE user message
  (the audit-65 t4 bug): the scan returns the NEWEST real result,
  never the oldest, and skips tool_reference blocks entirely.
- A denied tool call (default permission mode) returns a
  tool_result with is_error true and the plain-string content
  "Claude requested permissions to use <name>, but you haven't
  granted it yet." -- measured in probe4. The audited invocation
  therefore passes --allowedTools with exactly the 8 Trustrun MCP
  tools (see the adapter); --permission-mode bypassPermissions is
  refused when run as root.
"""

import copy
import importlib.util
import json
import os
import uuid

try:
    from real_agents.n8n_stub import _args_for_tool, _find_injection
except ImportError:  # standalone load: n8n_stub.py sits one dir up
    _stub_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "n8n_stub.py")
    _spec = importlib.util.spec_from_file_location(
        "claude_code_cli_n8n_stub_fb", _stub_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _args_for_tool = _mod._args_for_tool
    _find_injection = _mod._find_injection

MCP_SERVER_NAME = "trustrun"
_STUB_MODEL = "deterministic-stub-v1"

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


def claude_tool_name(harness_name):
    """The direct model-tool name for a harness tool."""
    return "mcp__%s__%s" % (MCP_SERVER_NAME, harness_name)


def _content_text(content):
    """A message's content as plain text (string, or text blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text") or "")
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return "" if content is None else str(content)


def _tool_result_texts(block):
    """(loaded_names, text_parts) from one tool_result block.

    content may be a list of blocks (tool_reference and/or text)
    or a plain string (the permission-denial shape).
    """
    loaded = set()
    texts = []
    content = block.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_reference":
                if item.get("tool_name"):
                    loaded.add(item["tool_name"])
            elif item.get("type") == "text":
                texts.append(item.get("text") or "")
    elif isinstance(content, str):
        texts.append(content)
    return loaded, texts


def scan_messages(messages):
    """Scan Anthropic messages for (loaded_tools, observations,
    last_tool_use_names).

    observations is a list of (raw, text) in wire order, one per
    tool_result block carrying real text; tool_reference-only
    blocks contribute their tool name to loaded_tools and no
    observation (the audit-65 probe-4 fix). last_tool_use_names
    are the tool names of the LAST assistant message's tool_use
    blocks, for the duplicate-request guard.
    """
    loaded = set()
    observations = []
    last_tool_use_names = []
    for message in messages or []:
        role = message.get("role")
        content = message.get("content")
        if role == "assistant" and isinstance(content, list):
            names = [b.get("name") for b in content
                     if isinstance(b, dict) and b.get("type") == "tool_use"
                     and b.get("name")]
            if names:
                last_tool_use_names = names
        if role != "user" or not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_result":
                continue
            names, texts = _tool_result_texts(block)
            loaded |= names
            if texts:
                text = "".join(texts)
                observations.append((text, _unwrap_observation(text)))
    return loaded, observations, last_tool_use_names


def _unwrap_observation(raw):
    """Unwrap a tool_result text to the tool result string.

    The common case is bare MCP tool text, verbatim. A JSON MCP
    envelope ({"content": [{"type": "text", "text": ...}],
    "isError": ...}) is unwrapped to the inner text if one ever
    appears (the n8n/Crush/Kimi Code transport-envelope
    precedent). An isError result maps to the "error:" form the
    stub's error branch checks (the n8n error-item precedent).
    """
    if not isinstance(raw, str):
        return "" if raw is None else str(raw)
    text = raw.strip()
    if not text.startswith("{"):
        return raw
    try:
        parsed = json.loads(text)
    except ValueError:
        return raw
    if not isinstance(parsed, dict):
        return raw
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
            joined = "".join(parts)
            if parsed.get("isError"):
                return "error:" + joined
            return joined
    if "error" in parsed:
        err = parsed["error"]
        err = err if isinstance(err, str) else json.dumps(err)
        return "error:" + err
    return raw


def find_task_text(messages, task_text):
    """The user message carrying the known task text verbatim.

    The CLI sends the task as its own user message after the
    system-reminder messages; an exact match wins, else the first
    message containing the task text. None when no user message
    carries it (an auxiliary call, not a turn of the task).
    """
    if not task_text:
        return None
    containing = None
    for message in messages or []:
        if message.get("role") != "user":
            continue
        text = _content_text(message.get("content"))
        if text == task_text:
            return text
        if containing is None and task_text in text:
            containing = text
    return containing


def _render_messages(messages):
    lines = []
    for message in messages or []:
        role = message.get("role", "?")
        content = message.get("content")
        if isinstance(content, list):
            parts = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text":
                    parts.append(block.get("text", "")[:2000])
                elif block.get("type") == "tool_use":
                    parts.append("[tool-use %s %s]" % (
                        block.get("name"),
                        json.dumps(block.get("input", ""))[:500]))
                elif block.get("type") == "tool_result":
                    _names, texts = _tool_result_texts(block)
                    if _names:
                        parts.append("[tool-reference %s]"
                                     % ", ".join(sorted(_names)))
                    if texts:
                        parts.append("[tool-result %s]"
                                     % "".join(texts)[:500])
                else:
                    parts.append("[%s]" % block.get("type"))
            lines.append("%s: %s" % (role, " ".join(parts)))
        else:
            lines.append("%s: %s" % (role, str(content)[:2000]))
    return "\n".join(lines)


def _text_events(text, tool_counter):
    """SSE (event, obj) pairs for a final text answer."""
    del tool_counter
    yield ("message_start", {
        "type": "message_start",
        "message": {"id": "msg_stub", "type": "message",
                    "role": "assistant", "content": [],
                    "model": _STUB_MODEL, "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 10, "output_tokens": 1}},
    })
    yield ("content_block_start", {
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "text", "text": ""},
    })
    yield ("content_block_delta", {
        "type": "content_block_delta", "index": 0,
        "delta": {"type": "text_delta", "text": text},
    })
    yield ("content_block_stop", {"type": "content_block_stop", "index": 0})
    yield ("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": 5},
    })
    yield ("message_stop", {"type": "message_stop"})


def _tool_use_events(name, args, tool_id):
    """SSE (event, obj) pairs for one tool_use call."""
    yield ("message_start", {
        "type": "message_start",
        "message": {"id": "msg_stub", "type": "message",
                    "role": "assistant", "content": [],
                    "model": _STUB_MODEL, "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 10, "output_tokens": 1}},
    })
    yield ("content_block_start", {
        "type": "content_block_start", "index": 0,
        "content_block": {"type": "tool_use", "id": tool_id,
                          "name": name, "input": {}},
    })
    yield ("content_block_delta", {
        "type": "content_block_delta", "index": 0,
        "delta": {"type": "input_json_delta",
                  "partial_json": json.dumps(args)},
    })
    yield ("content_block_stop", {"type": "content_block_stop", "index": 0})
    yield ("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": "tool_use", "stop_sequence": None},
        "usage": {"output_tokens": 5},
    })
    yield ("message_stop", {"type": "message_stop"})


def _toolsearch_events(harness_name, tool_id):
    """SSE pairs for the ToolSearch hop that loads one MCP tool."""
    return _tool_use_events(
        "ToolSearch",
        {"query": "select:%s" % claude_tool_name(harness_name)},
        tool_id)


def decide_anthropic(stub, body, task_text):
    """Answer one Anthropic /v1/messages request body.

    Returns (events, log_entry). events is a list of (name, obj)
    SSE pairs; log_entry mirrors the decide_for_request shape
    (step, prompt_type, observation, observation_raw,
    observation_had_injection, action_kind, action, prompt) in
    HARNESS terms. The stub's decision logic is the audit-30
    DeterministicChatModel._decide ported VERBATIM into
    n8n-stub.py (same regexes, branch order, fall-through, plus
    the audit-45 "tool failure" extension); this function only
    translates between the Anthropic wire and that table.

    A harness tool decision for an unloaded MCP tool is rendered
    as a ToolSearch hop and remembered as the stub's pending tool;
    the next request, once the tool_reference has arrived, emits
    the real tool_use without re-deciding. A forced call
    (re-probe hook) to a KNOWN tool goes through the same hop; a
    forced call to an UNKNOWN tool goes straight to the CLI's own
    tool resolution as mcp__trustrun__<name>.
    """
    messages = body.get("messages") or []
    if not hasattr(stub, "_tool_counter"):
        stub._tool_counter = 0
    if not hasattr(stub, "_pending_tool"):
        stub._pending_tool = None
    loaded, observations, last_calls = scan_messages(messages)
    key = (len(observations), tuple(last_calls))
    entry = {
        "step": len(stub.log),
        "prompt_type": "anthropic",
        "observation": None,
        "observation_raw": None,
        "observation_had_injection": False,
        "action_kind": None,
        "action": None,
        "prompt": _render_messages(messages),
    }

    def _finish(events, kind, action, observation=None,
                observation_raw=None):
        entry["observation"] = observation
        entry["observation_raw"] = observation_raw
        entry["observation_had_injection"] = bool(
            observation) and _find_injection(observation)
        entry["action_kind"] = kind
        entry["action"] = action
        stub.log.append(entry)
        stub._last_key = key
        stub._last_response = events
        return events, entry

    # Duplicate-request guard: same observation count and same last
    # assistant tool_calls as the previous request -> replay the
    # cached events instead of re-deciding, so a CLI retry can
    # never double-apply a state transition.
    if stub._last_key is not None and key == stub._last_key:
        entry["action_kind"] = "duplicate"
        entry["action"] = stub._last_response
        stub.log.append(entry)
        return stub._last_response, entry

    # Pending tool: the previous decision was rendered as a
    # ToolSearch hop; once the tool_reference has arrived, emit
    # the real tool_use without re-deciding.
    pending = getattr(stub, "_pending_tool", None)
    if pending is not None:
        name, args = pending
        if claude_tool_name(name) in loaded:
            stub._pending_tool = None
            tool_id = "toolu_stub_%d" % stub._tool_counter
            stub._tool_counter += 1
            events = list(_tool_use_events(
                claude_tool_name(name),
                _args_for_tool(name, args), tool_id))
            return _finish(events, "tool", (name, _args_for_tool(name, args)))
        tool_id = "toolu_stub_%d" % stub._tool_counter
        stub._tool_counter += 1
        events = list(_toolsearch_events(name, tool_id))
        return _finish(events, "tool",
                       ("ToolSearch",
                        {"query": "select:%s" % claude_tool_name(name)}))

    # Re-probe hook: emit one forced tool call on the first request
    # of the call, whatever the decision table says.
    if stub._forced is not None and not stub._forced_used:
        stub._forced_used = True
        forced = stub._forced
        name = forced["name"]
        args = forced.get("args") or {}
        if name in KNOWN_TOOLS and claude_tool_name(name) not in loaded:
            stub._pending_tool = (name, args)
            tool_id = "toolu_stub_%d" % stub._tool_counter
            stub._tool_counter += 1
            events = list(_toolsearch_events(name, tool_id))
            return _finish(events, "tool",
                           ("ToolSearch",
                            {"query": "select:%s" % claude_tool_name(name)}))
        tool_id = "toolu_stub_%d" % stub._tool_counter
        stub._tool_counter += 1
        events = list(_tool_use_events(
            claude_tool_name(name), args, tool_id))
        return _finish(events, "tool", (name, args))

    if not observations:
        kind, payload = stub._decide(None)
        if kind == "tool":
            name, args = payload
            if name in KNOWN_TOOLS and claude_tool_name(name) not in loaded:
                stub._pending_tool = (name, args)
                tool_id = "toolu_stub_%d" % stub._tool_counter
                stub._tool_counter += 1
                events = list(_toolsearch_events(name, tool_id))
                return _finish(events, "tool",
                               ("ToolSearch",
                                {"query": "select:%s"
                                 % claude_tool_name(name)}))
            tool_id = "toolu_stub_%d" % stub._tool_counter
            stub._tool_counter += 1
            events = list(_tool_use_events(
                claude_tool_name(name),
                _args_for_tool(name, args), tool_id))
            return _finish(events, "tool",
                           (name, _args_for_tool(name, args)))
        events = list(_text_events(payload, stub._tool_counter))
        return _finish(events, "final", payload)

    # Replay any observations already passed over (a jumped
    # history), then decide on the newest one exactly once.
    new_obs = observations[stub._decided_count:]
    if not new_obs:
        if stub._last_response is not None:
            entry["action_kind"] = "duplicate"
            entry["action"] = stub._last_response
            stub.log.append(entry)
            return stub._last_response, entry
        new_obs = observations[-1:]
    for _raw, obs in new_obs[:-1]:
        stub._decide(obs)
    raw, obs = new_obs[-1]
    stub._decided_count = len(observations)
    kind, payload = stub._decide(obs)
    if kind == "tool":
        name, args = payload
        if name in KNOWN_TOOLS and claude_tool_name(name) not in loaded:
            stub._pending_tool = (name, args)
            tool_id = "toolu_stub_%d" % stub._tool_counter
            stub._tool_counter += 1
            events = list(_toolsearch_events(name, tool_id))
            return _finish(events, "tool",
                           ("ToolSearch",
                            {"query": "select:%s" % claude_tool_name(name)}),
                           observation=obs, observation_raw=raw)
        tool_id = "toolu_stub_%d" % stub._tool_counter
        stub._tool_counter += 1
        events = list(_tool_use_events(
            claude_tool_name(name),
            _args_for_tool(name, args), tool_id))
        return _finish(events, "tool",
                       (name, _args_for_tool(name, args)),
                       observation=obs, observation_raw=raw)
    events = list(_text_events(payload, stub._tool_counter))
    return _finish(events, "final", payload,
                   observation=obs, observation_raw=raw)


def aux_events():
    """SSE pairs for an auxiliary model call (no user message
    carrying the task text): a plain-text answer that never
    touches the stub."""
    return list(_text_events("Trustrun audit task", 0))


def message_from_events(events):
    """The non-streaming Messages-API message object for events
    (fallback when a request arrives with stream False)."""
    content = []
    stop_reason = "end_turn"
    for name, obj in events:
        if name == "content_block_start":
            block = copy.deepcopy(obj.get("content_block") or {})
            if block.get("type") == "tool_use":
                block["input"] = {}
            content.append(block)
        elif name == "content_block_delta":
            delta = obj.get("delta") or {}
            if delta.get("type") == "text_delta" and content:
                content[-1]["text"] = (
                    content[-1].get("text", "") + delta.get("text", ""))
            elif delta.get("type") == "input_json_delta" and content:
                partial = content[-1].setdefault("_partial", "")
                content[-1]["_partial"] = partial + delta.get(
                    "partial_json", "")
        elif name == "message_delta":
            stop_reason = (obj.get("delta") or {}).get(
                "stop_reason") or stop_reason
    for block in content:
        if block.get("type") == "tool_use" and "_partial" in block:
            try:
                block["input"] = json.loads(block.pop("_partial"))
            except ValueError:
                block["input"] = {}
                block.pop("_partial", None)
    return {
        "id": "msg_stub",
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": _STUB_MODEL,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
