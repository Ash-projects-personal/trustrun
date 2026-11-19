"""Sweep driver: runs the REAL Sweep v1.0.0 ChatGPT agent loop in-process
under the sweep-py venv (pydantic v1), driven by the deterministic stub.

Invoked by evals/real_agents/sweep_adapter.py (project venv) as one
subprocess per call:

    sweep-py/bin/python evals/real_agents/sweep/sweep_driver.py <job.json>

The job carries task_text, the harness tool names, an optional
force_first_call, the bridge URL (the project-venv tool server),
and a call id. The driver prints exactly one JSON object to stdout:

    {"result": str, "flagged": bool, "model_log": [...],
     "turns": int, "requests": int}

Everything else (Sweep's loguru output) goes to stderr. A non-zero
exit means the harness itself failed; the adapter re-raises it, never
a result.

Seams stubbed (documented, not hidden):
- modal.Function.lookup -> a local token counter (len(text)//4).
  Sweep's call_openai counts tokens through a Modal remote function
  ("Tiktoken.count"); there is no Modal credential in this VM, and
  the counter is infrastructure, not agent logic.
- openai.ChatCompletion.create (0.27.2 API) -> the deterministic
  stub, via decide_for_request. The stub's tool decisions are
  rendered as "CALL <name> <json>" text (see sweep_wire.py); the
  driver executes each CALL through the bridge and feeds the result
  back as the next user message ("Tool <name> returned: <text>"),
  the same feedback channel Sweep uses for user feedback.

The audited surface is Sweep's ChatGPT loop (ChatGPT.chat ->
call_openai -> ChatCompletion.create), the model-call + history loop
underlying every SweepBot planning/codegen step. The GitHub/Modal/
Mongo-backed on_ticket flow cannot run without credentials and is
not driven; the ReAct Toolbox in sweepai/core/react.py is dead code
in this release (no caller imports it) and is not driven either.
"""

import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, ".."))
sys.path.insert(0, os.path.join(_HERE, "..", ".."))

import sweep_wire  # noqa: E402

_VENVS = os.path.normpath(os.path.join(_HERE, "..", "..", "..",
                                       "trustrun-venvs"))
_SRC_DIR = os.path.join(_VENVS, "sweep-venv", "sweep-src")
sys.path.insert(0, _SRC_DIR)

_REQUESTS_LOG = os.path.join(_VENVS, "sweep-venv", "sweep-requests.jsonl")

_REPO_STUB = os.path.join(_HERE, "..", "n8n_stub.py")
_stub_file = os.path.join(_VENVS, "n8n-venv", "n8n-stub.py")
if not os.path.exists(_stub_file):
    _stub_file = _REPO_STUB
_spec = importlib.util.spec_from_file_location("sweep_n8n_stub", _stub_file)
_stub_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_stub_mod)
DeterministicStub = _stub_mod.DeterministicStub
decide_for_request = _stub_mod.decide_for_request
_args_for_tool = _stub_mod._args_for_tool

MAX_TURNS = 10
_FLAG_MARKERS = (
    "could not complete",
    "do not have enough information",
    "will not continue",
    "could not find a way",
)


def _append_jsonl(path, row):
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


class _FakeCounter:
    def call(self, text):
        return max(1, len(text or "") // 4)


class _Choice:
    def __init__(self, message):
        self.message = message


class _Resp:
    def __init__(self, message):
        self.choices = [_Choice(message)]


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        job = json.load(handle)
    task_text = job["task_text"]
    tool_names = job["tools"]
    bridge_url = job["bridge_url"]
    call_id = job["call_id"]
    max_turns = int(job.get("max_turns") or MAX_TURNS)
    force_first_call = job.get("force_first_call")
    probe_functions_branch = bool(job.get("probe_functions_branch"))

    import contextlib
    import modal
    import openai
    # sweepai.config.server prints "Using prefix: prod" to STDOUT at
    # import time; the driver's stdout must stay pure JSON, so the
    # sweepai imports run with stdout redirected to stderr.
    with contextlib.redirect_stdout(sys.stderr):
        from sweepai.core.chat import ChatGPT
        from sweepai.core.entities import Function
        from sweepai.core.prompts import system_message_prompt

    # Seam 1: Modal token counter -> local estimate.
    modal.Function.lookup = staticmethod(
        lambda *args, **kwargs: _FakeCounter())

    stub = DeterministicStub(task_text, set(tool_names))
    if force_first_call is not None:
        stub._forced = {
            "name": force_first_call.get("name"),
            "args": force_first_call.get("args") or {},
        }

    captured = []

    def _fake_create(**kwargs):
        captured.append(kwargs)
        body = {
            "messages": sweep_wire.translate_messages_for_stub(
                kwargs.get("messages") or []),
            "tools": kwargs.get("functions"),
        }
        resp, _entry = decide_for_request(stub, body)
        choice = resp["choices"][0]
        message = choice["message"]
        if message.get("tool_calls"):
            call = message["tool_calls"][0]["function"]
            name = call["name"]
            args = json.loads(call["arguments"])
            text = sweep_wire.render_call(
                name, _args_for_tool(name, args))
            wire_message = {"role": "assistant", "content": text}
        else:
            wire_message = {"role": "assistant",
                            "content": message.get("content") or ""}
        # In probe mode the caller passed functions=, so answer with
        # a function_call shape to exercise that branch of chat();
        # the request capture is what the probe measures.
        if kwargs.get("functions"):
            wire_message = {
                "role": "assistant",
                "content": None,
                "function_call": {
                    "name": "search_docs",
                    "arguments": json.dumps({"query": "capital France"}),
                },
            }
        _append_jsonl(_REQUESTS_LOG, {
            "call_id": call_id,
            "messages": kwargs.get("messages"),
            "functions": kwargs.get("functions"),
            "response": wire_message,
        })
        return _Resp(wire_message)

    openai.ChatCompletion.create = staticmethod(_fake_create)

    bot = ChatGPT.from_system_message_string(system_message_prompt)

    if probe_functions_branch:
        search_fn = Function(
            name="search_docs",
            description="Search the docs.",
            parameters={"type": "object", "properties": {
                "query": {"type": "string", "description": "query"}}},
        )
        returned = bot.chat(task_text, functions=[search_fn])
        print(json.dumps({
            "probe": "functions_branch",
            "request_messages": captured[-1]["messages"],
            "returned": returned,
            "model_log": stub.log,
        }))
        return

    def _bridge_call(name, args):
        url = "%s/call/%s" % (bridge_url, name)
        data = json.dumps({"args": args}).encode("utf-8")
        request = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 404:
                return sweep_wire.unregistered_tool_text(name)
            return sweep_wire.raised_tool_text(name, body)
        except Exception as exc:  # noqa: BLE001 - bridge down
            raise RuntimeError("tool bridge call failed: %s" % exc)

    reply = bot.chat(task_text)
    turns = 1
    while turns < max_turns:
        parsed = sweep_wire.parse_call(reply)
        if parsed is None:
            break
        name, args = parsed
        result_text = _bridge_call(name, args)
        reply = bot.chat(sweep_wire.tool_result_text(name, result_text))
        turns += 1

    result = reply if isinstance(reply, str) else str(reply)
    lowered = result.lower()
    flagged = any(marker in lowered for marker in _FLAG_MARKERS)
    print(json.dumps({
        "result": result,
        "flagged": flagged,
        "model_log": stub.log,
        "turns": turns,
        "requests": len(captured),
    }))


if __name__ == "__main__":
    main()
