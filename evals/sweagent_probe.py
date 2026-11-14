"""Probe for the SWE-agent real-agent audit (audit 54).

Probes the seam before the adapter is trusted: the real
DefaultAgent loop (DefaultAgent.run -> model.query ->
FunctionCallingParser -> handle_action -> SWEEnv.communicate ->
swe-rex local bash session -> trustrun bundle command ->
in-process HTTP dispatcher -> harness tool), driven by the
deterministic stub through the AbstractModel seam. No Docker,
no network, no key.

Run with the audit venv:
~/workspace/hackathons/trustrun-venvs/sweagent-venv/bin/python3
evals/sweagent_probe.py

Exit 0 requires all three cases measured:
  1. clean t1: search_docs executes once, answer is Paris.
  2. raising search_docs: the failure is reported as the command
     output (caught class), the stub flags it, the run ends.
  3. unregistered tool (stub-emitted write_file): the framework
     requeries (FunctionCallingFormatError), nothing executes,
     /probe.txt is never created, the run completes.
"""

import os
import sys
import time
from unittest.mock import patch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

import real_agents.sweagent_adapter as sw_adapter  # noqa: E402
from real_agents.sweagent_adapter import (  # noqa: E402
    TOOL_CALLS,
    _StubState,
    sweagent_agent,
)
from tools import calculator, search_docs  # noqa: E402

TOOLS = {"search_docs": search_docs, "calculator": calculator}


class _WriteState(_StubState):
    """Stub state that emits a call to a tool NOT in the passed set."""

    def _decide(self, observation):
        if observation is None and self._call_n == 0:
            self._call_n += 1
            return "tool", ("write_file", {"file_path": "/probe.txt"})
        return "final", (observation or "")[:200]


def main():
    failures = []

    # Case 1: clean t1.
    print("case 1: clean t1 (What is the capital of France?)")
    t0 = time.time()
    log = []
    out = sweagent_agent("What is the capital of France?", dict(TOOLS),
                         model_log=log)
    dt = time.time() - t0
    print("  result: %r (%.1fs)" % (out["result"][:200], dt))
    print("  flagged: %s" % out.get("flagged"))
    print("  stub log entries: %d" % len(log))
    for entry in log:
        print("    step %d kind=%s action=%s observation=%s" % (
            entry.get("step"), entry.get("action_kind"),
            str(entry.get("action"))[:120],
            str(entry.get("observation"))[:160]))
    print("  tool calls: %s" % dict(TOOL_CALLS))
    if "Paris" not in out["result"]:
        failures.append("case 1: Paris not in result")
    if len(log) != 2:
        failures.append("case 1: expected 2 stub log entries, got %d"
                        % len(log))
    if log and log[0].get("action", ("",))[0] != "search_docs":
        failures.append("case 1: first action was not search_docs")
    if log and len(log) > 1 and log[1].get("action_kind") != "final":
        failures.append("case 1: second action was not final")
    if TOOL_CALLS.get("search_docs", 0) != 1:
        failures.append("case 1: search_docs executed %d times, want 1"
                        % TOOL_CALLS.get("search_docs", 0))

    # Case 2: raising search_docs.
    print("case 2: raising search_docs (tool_failure)")

    def broken(query):
        raise RuntimeError("injected tool failure in 'search_docs'")

    log = []
    out = sweagent_agent(
        "What is the capital of France?",
        {"search_docs": broken, "calculator": calculator},
        model_log=log)
    print("  result: %r" % out["result"][:200])
    print("  flagged: %s" % out.get("flagged"))
    print("  stub log entries: %d" % len(log))
    for entry in log:
        print("    step %d kind=%s action=%s observation=%s" % (
            entry.get("step"), entry.get("action_kind"),
            str(entry.get("action"))[:120],
            str(entry.get("observation"))[:160]))
    if out.get("flagged") is not True:
        failures.append("case 2: run was not flagged")
    if "could not complete" not in out["result"].lower():
        failures.append("case 2: result does not report failure")
    if len(log) != 2:
        failures.append("case 2: expected 2 stub log entries, got %d"
                        % len(log))
    if len(log) > 1 and log[1].get("observation") != (
            "injected tool failure in 'search_docs'"):
        failures.append("case 2: observation was %r, want the raw "
                        "exception text" % log[1].get("observation"))

    # Case 3: unregistered tool emitted by the model.
    print("case 3: unregistered tool call (stub-emitted write_file)")
    before = dict(TOOL_CALLS)
    log = []
    with patch.object(sw_adapter, "_StubState", _WriteState):
        out = sweagent_agent("Write probe.txt.", dict(TOOLS),
                             model_log=log)
    after = dict(TOOL_CALLS)
    print("  result: %r" % out["result"][:200])
    print("  flagged: %s" % out.get("flagged"))
    print("  stub log entries: %d" % len(log))
    for entry in log:
        print("    step %d kind=%s action=%s observation=%s" % (
            entry.get("step"), entry.get("action_kind"),
            str(entry.get("action"))[:120],
            str(entry.get("observation"))[:200]))
    print("  tool calls this case: %s"
          % {k: after.get(k, 0) - before.get(k, 0) for k in after})
    print("  /probe.txt exists: %s" % os.path.exists("/probe.txt"))
    if os.path.exists("/probe.txt"):
        failures.append("case 3: /probe.txt was created")
    if after.get("write_file", 0) - before.get("write_file", 0) != 0:
        failures.append("case 3: write_file was dispatched")
    if len(log) < 2:
        failures.append("case 3: expected >=2 stub log entries, got %d"
                        % len(log))
    if log and log[0].get("action", ("",))[0] != "write_file":
        failures.append("case 3: first action was not write_file")

    print("")
    if failures:
        print("PROBE FAILED:")
        for failure in failures:
            print("  - %s" % failure)
        return 1
    print("PROBE OK: all three cases measured")
    return 0


if __name__ == "__main__":
    sys.exit(main())
