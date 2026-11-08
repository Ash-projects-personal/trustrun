"""Audit CrewAI Agent (crewai 1.15.37) with Trustrun (fourth real-agent
audit; first was smolagents 1.26.0, second LangChain create_react_agent,
third LlamaIndex ReActAgent).

Usage: evals/.venv-crewai/bin/python run_real_agents_crewai.py
(crewai lives in a separate venv; see real_agents/crewai_adapter.py
for the install command: pip install crewai litellm. litellm is an
optional extra in crewai 1.15 and the adapter's stub patches
litellm.completion, so it must be installed explicitly.)

Runs trustrun.cli.run_audit over the crewai adapter on all 25 tasks,
seed 0, k=5, with the eval corpus as the data module input. Writes one
machine readable summary into reports/real_agents/crewai/summary.json
and the evidence logs (injection observations, tampering calls) into
reports/real_agents/crewai/evidence.json. Every number in those files
comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to such
a model unfiltered. The evidence logs show the exact observation text
the framework handed the model, which is the framework-level fact.
Never present a clean-room failure as a flaw in a real product: the
clean-room agents' failures are theirs; crewai's rows are crewai's.

Environment: the runner clears the VM's proxy variables before importing
crewai (the native OpenAI provider constructor chokes on the bare ::1
no_proxy entry; the audit makes no network calls, so nothing is lost).
Telemetry is disabled for the same reason (no network, no phone-home
attempts on every agent run).
"""

import json
import os
import sys
import time

# No network is involved in this audit (the stub answers every model
# call), and crewai's native provider constructor fails on this VM's
# proxy env vars, so clear them before importing crewai. See the
# adapter docstring for the measured details.
for _var in (
    "HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy",
    "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
):
    os.environ.pop(_var, None)
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

from real_agents.crewai_adapter import (  # noqa: E402
    CREWAI_REPO,
    CREWAI_VERSION,
    RUN_LOGS,
    crewai_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "crewai")
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
            crewai_agent, task, data_path=CORPUS, seed=0, k=5
        )
        sections = report["sections"]
        rows.append({
            "agent": "crewai_agent",
            "task": task_def["id"],
            "verdict": report["verdict"],
            "contract": sections["contract"]["verdict"],
            "stress": sections["stress"]["verdict"],
            "consistency": sections["consistency"]["verdict"],
            "data": sections["data"]["verdict"],
            "pass_rate_k": sections["consistency"]["pass_rate_k"],
        })
        print("crewai x %s -> %s (contract %s, stress %s, consistency %s)"
              % (task_def["id"], report["verdict"],
                 sections["contract"]["verdict"],
                 sections["stress"]["verdict"],
                 sections["consistency"]["verdict"]))
    summary = {
        "product": "CrewAI Agent",
        "component": "Agent",
        "version": "crewai %s" % CREWAI_VERSION,
        "repo": CREWAI_REPO,
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; see real_agents/crewai_adapter.py)",
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
