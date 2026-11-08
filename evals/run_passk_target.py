"""Run the PassKTarget calibration: pass@k curves in tau2-bench format.

Usage: python3 run_passk_target.py

For each of the six clean-room agents over the eight eval tasks, runs
score_repeated_runs with k=5 and reports pass@1 through pass@5 from
the tau-bench estimator (trustrun.consistency.pass_at_k), averaged
across tasks per agent. The calibration axis is pass@4, the number
tau2-bench reports as Pass^4 (GPT-4.1, 57.5% on the retail held-out
set, rising to 67.5% with the ALTK-Evolve playbook; BenchLM's
tau3-bench Telecom leader is Mercury 2.5 at 96.0%). Those published
numbers are reference points from other agents on other tasks, not
same-agent comparisons: same-agent calibration requires running the
tau2-bench tasks themselves, which Trustrun does not ship. This
script establishes Trustrun's pass^k reporting in tau2-bench's
format so the comparison is apples-to-apples when that data exists.
Writes the machine readable summary into reports/passk_target/
summary.json. Every number in that file comes from a real run.
Nothing is invented.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agents import plan_execute_agent, rag_agent, react_agent  # noqa: E402
from agents_round2 import (  # noqa: E402
    guardrail_rag_agent,
    hardened_agent,
    reflection_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.consistency import pass_at_k, score_repeated_runs  # noqa: E402

AGENTS = {
    "react": react_agent,
    "rag": rag_agent,
    "plan_execute": plan_execute_agent,
    "guardrail_rag": guardrail_rag_agent,
    "hardened": hardened_agent,
    "reflection": reflection_agent,
}

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "passk_target")
K = 5


def _bound(agent, tools):
    """Wrap an agent so score_repeated_runs can call it with text only.

    The eval agents take (task_text, tools); the consistency module
    calls the agent with the text alone, so the tools must be bound
    first, exactly as trustrun.cli._consistency_section does.
    """
    def wrapped(task_text):
        return agent(task_text, tools)

    return wrapped


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as handle:
        tasks = json.load(handle)
    started = time.time()
    per_agent = {}
    rows = []
    for agent_name, agent in AGENTS.items():
        curves = {k: [] for k in range(1, K + 1)}
        for task_def in tasks:
            tools = {
                name: TOOL_BUILDERS[name]
                for name in task_def["tools_order"]
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
            report = score_repeated_runs(_bound(agent, tools), task, k=K, seed=0)
            outcomes = [r["completed"] for r in report["runs"]]
            row = {"agent": agent_name, "task": task_def["id"]}
            for k in range(1, K + 1):
                value = pass_at_k(outcomes, k)
                row["pass_at_%d" % k] = value
                if value != "unverified":
                    curves[k].append(value)
            rows.append(row)
        per_agent[agent_name] = {
            "pass_at_%d" % k: (
                sum(values) / len(values) if values else "unverified"
            )
            for k, values in curves.items()
        }
    overall = {
        "pass_at_%d" % k: (
            sum(
                per_agent[a]["pass_at_%d" % k]
                for a in AGENTS
                if per_agent[a]["pass_at_%d" % k] != "unverified"
            )
            / len(AGENTS)
        )
        for k in range(1, K + 1)
    }
    summary = {
        "agents": sorted(AGENTS),
        "tasks": [t["id"] for t in tasks],
        "k": K,
        "seed": 0,
        "per_agent": per_agent,
        "overall": overall,
        "rows": rows,
        "reference": {
            "note": "published numbers from other agents on other tasks, "
            "not same-agent comparisons",
            "tau2_bench_gpt41_pass4_retail_heldout": 0.575,
            "tau2_bench_gpt41_altk_evolve_pass4_retail_heldout": 0.675,
            "tau3_bench_mercury25_telecom": 0.96,
        },
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w",
              encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
    print(
        "passk target: overall pass@1 %.3f, pass@4 %.3f, pass@5 %.3f (%.1fs)"
        % (overall["pass_at_1"], overall["pass_at_4"], overall["pass_at_5"],
           time.time() - started)
    )


if __name__ == "__main__":
    main()
