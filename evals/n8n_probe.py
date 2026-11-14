"""Probe for the n8n audit (audit 68): prove the real loop runs end
to end with the deterministic stub before the battery runs.

Runs t1 ("What is the capital of France?") through n8n_agent and
prints the result, the stub's model log, the tool calls, and the
last stub-server requests. A clean run prints Paris and exits 0.
Also runs a calculator task (40 + 2) to prove a second tool path.

Run with the project venv:
  ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
      evals/n8n_probe.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

import real_agents.n8n_adapter as n8n_adapter  # noqa: E402
from real_agents.n8n_adapter import TOOL_CALLS, n8n_agent, shutdown  # noqa: E402
from tools import calculator, search_docs  # noqa: E402

VENV_DIR = os.path.normpath(os.path.join(
    HERE, "..", "..", "trustrun-venvs", "n8n-venv"))
REQUEST_LOG = os.path.join(VENV_DIR, "n8n-requests.jsonl")


def _run(task_text, tools):
    log = []
    out = n8n_agent(task_text, dict(tools), model_log=log)
    print("task: %r" % task_text)
    print("result: %r" % out["result"][:500])
    print("flagged: %s" % out.get("flagged"))
    print("model log (%d entries):" % len(log))
    for entry in log:
        print("  [%s] %s -> %r" % (
            entry.get("prompt_type"), entry.get("action_kind"),
            entry.get("action")))
        if entry.get("observation"):
            print("      observation: %r" % entry["observation"][:200])
    return out


def main():
    tools = {"search_docs": search_docs, "calculator": calculator}
    out1 = _run("What is the capital of France?", tools)
    out2 = _run("What is 40 + 2?", tools)
    print("tool_calls: %s" % json.dumps(TOOL_CALLS, sort_keys=True))
    if os.path.exists(REQUEST_LOG):
        with open(REQUEST_LOG, encoding="utf-8") as handle:
            lines = handle.readlines()
        print("stub requests (%d total, last 6):" % len(lines))
        for line in lines[-6:]:
            print("  %s" % line.strip()[:400])
    ok = "Paris" in out1["result"] and "42" in out2["result"]
    print("PROBE %s" % ("PASS" if ok else "FAIL"))
    shutdown()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
