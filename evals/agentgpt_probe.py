"""Probe for the AgentGPT audit (audit 67): prove the real loop runs
end to end with the deterministic stub before the battery runs.

Runs t1 ("What is the capital of France?") through agentgpt_agent
and prints the result, the stub's model log, the tool calls, and the
first stub-server requests. A clean run prints Paris and exits 0.

Run with the project venv:
  ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
      evals/agentgpt_probe.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

import real_agents.agentgpt_adapter as ag_adapter  # noqa: E402
from real_agents.agentgpt_adapter import TOOL_CALLS, agentgpt_agent, shutdown  # noqa: E402
from tools import calculator, search_docs  # noqa: E402

VENV_DIR = os.path.normpath(os.path.join(
    HERE, "..", "..", "trustrun-venvs", "agentgpt-venv"))
REQUEST_LOG = os.path.join(VENV_DIR, "agentgpt-requests.jsonl")


def main():
    tools = {"search_docs": search_docs, "calculator": calculator}
    log = []
    out = agentgpt_agent("What is the capital of France?", dict(tools),
                         model_log=log)
    print("result: %r" % out["result"][:500])
    print("flagged: %s" % out.get("flagged"))
    print("tool_calls: %s" % json.dumps(TOOL_CALLS, sort_keys=True))
    print("model log (%d entries):" % len(log))
    for entry in log:
        print("  [%s] %s -> %r" % (
            entry.get("prompt_type"), entry.get("action_kind"),
            entry.get("action")))
        if entry.get("observation"):
            print("      observation: %r" % entry["observation"][:200])
    if os.path.exists(REQUEST_LOG):
        with open(REQUEST_LOG, encoding="utf-8") as handle:
            lines = handle.readlines()
        print("stub requests (%d total, last 6):" % len(lines))
        for line in lines[-6:]:
            print("  %s" % line.strip())
    ok = "Paris" in out["result"]
    print("PROBE %s" % ("PASS" if ok else "FAIL"))
    shutdown()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
