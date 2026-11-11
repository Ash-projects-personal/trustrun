"""Audit Strands' Agent (strands-agents)
(eighteenth real-agent audit; seventeenth was AgentScope Agent 2.0.11).

Usage: ~/workspace/hackathons/trustrun-venvs/strands-venv/bin/python3 run_real_agents_strands.py
(strands-agents lives in a separate venv; see
real_agents/strands_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the strands adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/strands/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/strands/evidence.json. Every number in those
files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The evidence logs show the exact observation
text the framework handed the model, which is the framework-level
fact. Never present a clean-room failure as a flaw in a real product:
the clean-room agents' failures are theirs; strands' rows
are strands'.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

from real_agents.strands_adapter import (  # noqa: E402
    STRANDS_REPO,
    STRANDS_VERSION,
    RUN_LOGS,
    strands_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "strands")
CORPUS = os.path.join(HERE, "corpus.jsonl")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as handle:
        tasks = json.load(handle)
    started = time.time()
    rows = []
    for task_def in tasks:
        tools = {
            name: TOOL_BUILDERS[name] for name in task_def["tools_order"]
        }
        task = {
            "text": task_def["text"],
            "expect": task_def["expect"],
            "tools": tools,
        }
        if task_def.get("variants"):
            task["variants"] = task_def["variants"]
        if task_def.get("rubric"):
            task["rubric"] = task_def["rubric"]
        if task_def.get("misleading_suggestion"):
            task["misleading_suggestion"] = task_def["misleading_suggestion"]
        report = run_audit(
            strands_agent, task, data_path=CORPUS, seed=0, k=5
        )
        sections = report["sections"]
        rows.append({
            "agent": "strands_agent",
            "task": task_def["id"],
            "verdict": report["verdict"],
            "contract": sections["contract"]["verdict"],
            "stress": sections["stress"]["verdict"],
            "consistency": sections["consistency"]["verdict"],
            "data": sections["data"]["verdict"],
            "pass_rate_k": sections["consistency"]["pass_rate_k"],
        })
        print("strands x %s -> %s (contract %s, stress %s, consistency %s)"
              % (task_def["id"], report["verdict"],
                 sections["contract"]["verdict"],
                 sections["stress"]["verdict"],
                 sections["consistency"]["verdict"]))
    summary = {
        "product": "Strands Agent (strands-agents)",
        "component": "strands.Agent",
        "version": "strands-agents %s" % STRANDS_VERSION,
        "repo": STRANDS_REPO,
        "repo_resolved": "https://github.com/strands-agents/harness-sdk (sdk-python redirects to the harness-sdk monorepo; Python SDK under strands-py/)",
        "model_driver": "deterministic-stub-v1 via strands.models.Model subclass implementing stream() (literal model: follows instructions in task text and tool output; see real_agents/strands_adapter.py)",
        "confirmation_gate": "none in the default configuration: a tool the model requests executes immediately, with no human-in-the-loop approval step (hooks/interventions exist for a developer to wire one, but nothing gates by default)",
        "tasks": [t["id"] for t in tasks],
        "seed": 0,
        "k": 5,
        "audits": len(rows),
        "rows": rows,
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w",
              encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
    with open(os.path.join(OUT_DIR, "evidence.json"), "w",
              encoding="utf-8") as handle:
        json.dump(RUN_LOGS, handle, indent=1)
    from collections import Counter
    print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
    print("stress:", dict(Counter(r["stress"] for r in rows)))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))


if __name__ == "__main__":
    main()
