"""Deterministic stub decision layer for the GPT-Pilot audit (audit 88).

Ports the audit-30 DeterministicChatModel decision table VERBATIM
into DeterministicStub._decide (via evals/real_agents/n8n_stub.py --
same regexes, branch order, and fall-through, plus the audit-45
"tool failure" extension); this module only translates between the
wire formats GPT-Pilot 0.2.13 uses and that table, and renders the
decision as PLAIN TEXT (GPT-Pilot has no tool-calling channel: the
driver parses CALL lines out of the model text, see gpt_pilot_wire).

Wire shapes:
- OpenAI: POST /v1/chat/completions, messages = GPT-Pilot's AgentConvo
  history (system prompt first, then the task as the first user
  message, then alternating assistant text / "Tool <name> returned:
  <text>" user messages).
- Anthropic: POST /v1/messages, messages already adapted by
  GPT-Pilot's AnthropicClient._adapt_messages (system folded into the
  first user message, consecutive same-role messages merged).

Observations are the "Tool <name> returned: <text>" user messages
after the first user message; the stub decides on exactly one new
observation per request (replaying any jumped observations first),
so the state flags advance exactly as in the audit-30 model. A
duplicate request (same observation count as the last one answered)
returns the cached response instead of re-deciding.

A tool decision is rendered as "CALL <name> <json args>" (the Sweep
wire); a final answer is rendered as the answer text verbatim. The
adapter's HTTP stub server streams the text as OpenAI chat-completion
SSE chunks or Anthropic Messages SSE events (whole-text or one-char
deltas for the re-probe variant).
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.normpath(os.path.join(_HERE, ".."))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from gpt_pilot_wire import TOOL_RESULT_RE, render_call  # noqa: E402
from n8n_stub import (  # noqa: E402
    _args_for_tool,
    _content_text,
    _find_injection,
    _render_messages,
)

_STUB_MODEL = "deterministic-stub-v1"


def decide_text(stub, body, task_text):
    """Answer one stub request body (either wire format).

    Returns (decision, entry) where decision is ("tool", (name, args))
    or ("final", text), and entry mirrors the decide_for_request log
    shape (step, prompt_type, observation, observation_raw,
    observation_had_injection, action_kind, action, prompt).
    The decision text is rendered by the caller (render_decision_text).
    """
    messages = body.get("messages") or []
    # Task text: the first user message (the AgentConvo system prompt
    # comes first; the driver puts the task text in as user[0]).
    found_task = ""
    for message in messages:
        if message.get("role") == "user":
            found_task = _content_text(message.get("content"))
            break
    if found_task:
        task_text = found_task
        stub.task_text = found_task
        stub.goal = found_task
    # Observations: "Tool <name> returned: <text>" user messages
    # after the first user message, in order.
    observations = []
    seen_first_user = False
    for message in messages:
        if message.get("role") != "user":
            continue
        content = _content_text(message.get("content"))
        if not seen_first_user:
            seen_first_user = True
            continue
        match = TOOL_RESULT_RE.match(content.strip())
        if match:
            observations.append((content, match.group(2)))
    # Duplicate-request guard: same observation count as the previous
    # request -> replay the cached decision, never re-decide.
    key = (len(observations),)
    entry = {
        "step": len(stub.log),
        "prompt_type": "gpt-pilot",
        "observation": None,
        "observation_raw": None,
        "observation_had_injection": False,
        "action_kind": None,
        "action": None,
        "prompt": _render_messages(messages),
    }
    if stub._last_key is not None and key == stub._last_key:
        entry["action_kind"] = "duplicate"
        entry["action"] = stub._last_response
        stub.log.append(entry)
        return stub._last_response, entry

    def _finish(kind, action, observation=None, observation_raw=None):
        entry["observation"] = observation
        entry["observation_raw"] = observation_raw
        entry["observation_had_injection"] = bool(
            observation) and _find_injection(observation)
        entry["action_kind"] = kind
        entry["action"] = action
        stub.log.append(entry)
        stub._last_key = key
        stub._last_response = (kind, action)
        return (kind, action), entry

    # Re-probe hook: emit one forced tool call on the first request
    # of the call, whatever the decision table says.
    if stub._forced is not None and not stub._forced_used:
        stub._forced_used = True
        forced = stub._forced
        name = forced["name"]
        args = forced.get("args") or {}
        return _finish("tool", (name, _args_for_tool(name, args)))

    if not observations:
        kind, payload = stub._decide(None)
        if kind == "tool":
            name, args = payload
            return _finish("tool", (name, _args_for_tool(name, args)))
        return _finish("final", payload)

    # Replay any observations already passed over (a jumped history),
    # then decide on the newest one exactly once.
    new_obs = observations[stub._decided_count:]
    if not new_obs:
        # No fresh observation (e.g. a client retry of the same
        # request): replay the last decision instead of crashing.
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
        return _finish("tool", (name, _args_for_tool(name, args)),
                       observation=obs, observation_raw=raw)
    return _finish("final", payload, observation=obs, observation_raw=raw)


def render_decision_text(decision):
    """Render a decide_text decision as the model's plain-text reply."""
    kind, payload = decision
    if kind == "tool":
        name, args = payload
        return render_call(name, args)
    return payload


def openai_events(text, stream_mode="whole"):
    """SSE chunk dicts for an OpenAI chat-completions stream."""
    if stream_mode == "char":
        deltas = [{"content": ch} for ch in text]
    else:
        deltas = [{"content": text}] if text else []
    events = [{
        "id": "chatcmpl-stub", "object": "chat.completion.chunk",
        "created": 0, "model": _STUB_MODEL,
        "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""},
                     "finish_reason": None}],
    }]
    for delta in deltas:
        events.append({
            "id": "chatcmpl-stub", "object": "chat.completion.chunk",
            "created": 0, "model": _STUB_MODEL,
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        })
    events.append({
        "id": "chatcmpl-stub", "object": "chat.completion.chunk",
        "created": 0, "model": _STUB_MODEL,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    })
    events.append({
        "id": "chatcmpl-stub", "object": "chat.completion.chunk",
        "created": 0, "model": _STUB_MODEL,
        "choices": [],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                  "total_tokens": 15},
    })
    return events


def anthropic_events(text, stream_mode="whole"):
    """SSE (name, obj) pairs for an Anthropic Messages stream."""
    events = [
        ("message_start", {"type": "message_start", "message": {
            "id": "msg_stub", "type": "message", "role": "assistant",
            "content": [], "model": _STUB_MODEL, "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 1}}}),
        ("content_block_start", {"type": "content_block_start", "index": 0,
                                 "content_block": {"type": "text", "text": ""}}),
    ]
    if stream_mode == "char":
        chunks = list(text)
    else:
        chunks = [text] if text else []
    for chunk in chunks:
        events.append(("content_block_delta", {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "text_delta", "text": chunk}}))
    events.extend([
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        ("message_delta", {"type": "message_delta",
                           "delta": {"stop_reason": "end_turn",
                                     "stop_sequence": None},
                           "usage": {"output_tokens": 5}}),
        ("message_stop", {"type": "message_stop"}),
    ])
    return events
