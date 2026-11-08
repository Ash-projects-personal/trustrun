"""Validate the grown task set (25) and agent set (12) before round 19.

Usage: python3 run_tasks_agents_validation.py

Part 1: clean single runs — every agent over every task, one call each,
labeled pass/fail by expected-answer containment. This checks that the
new tasks are answerable and the new agents behave as designed, without
duplicating the eval loop's round 19 (which runs the full audit battery
over the same grid and records the labeled rows).

Part 2: full-audit sample — run_audit over the six new agents on the
five discriminating new tasks (t14 echo failure, t21 word problem,
t23 multistep, t24 underspecified, t25 impossible), to verify the new
agents behave in the battery: the literal agent must be caught by the
injection attacks, the cautious agent must pass the impossible task,
the clarification agent must handle the underspecified task.

Writes the machine readable summary into
reports/validation/summary.json. Every number in that file comes from
a real run. Nothing is invented.
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
from agents_round3 import (  # noqa: E402
    abstaining_agent,
    cautious_agent,
    clarification_agent,
    literal_agent,
    retry_agent,
    verifying_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

AGENTS = {
    "react": react_agent,
    "rag": rag_agent,
    "plan_execute": plan_execute_agent,
    "guardrail_rag": guardrail_rag_agent,
    "hardened": hardened_agent,
    "reflection": reflection_agent,
    "cautious": cautious_agent,
    "clarification": clarification_agent,
    "verifying": verifying_agent,
    "literal": literal_agent,
    "abstaining": abstaining_agent,
    "retry": retry_agent,
}

NEW_AGENTS = [
    "cautious", "clarification", "verifying",
    "literal", "abstaining", "retry",
]

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "validation")
CORPUS = os.path.join(HERE, "corpus.jsonl")
AUDIT_TASKS = ["t14_stinger", "t21_percent_word", "t23_station_add",
               "t24_underspecified", "t25_impossible"]


def _build_task(task_def):
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
    return task


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as handle:
        tasks = json.load(handle)
    started = time.time()
    clean_rows = []
    for agent_name, agent in AGENTS.items():
        for task_def in tasks:
            tools = {
                name: TOOL_BUILDERS[name]
                for name in task_def["tools_order"]
            }
            try:
                out = agent(task_def["text"], dict(tools))
                result = out.get("result", "") if isinstance(out, dict) else ""
            except Exception as exc:
                result = "RAISED: %s" % exc
            clean_rows.append({
                "agent": agent_name,
                "task": task_def["id"],
                "pass": isinstance(result, str) and task_def["expect"] in result,
                "result": result[:200] if isinstance(result, str) else str(result)[:200],
            })
    clean_pass = sum(1 for r in clean_rows if r["pass"])
    print("clean grid: %d/%d pass" % (clean_pass, len(clean_rows)))
    audit_rows = []
    by_id = {t["id"]: t for t in tasks}
    for agent_name in NEW_AGENTS:
        for task_id in AUDIT_TASKS:
            task = _build_task(by_id[task_id])
            report = run_audit(
                AGENTS[agent_name], task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            audit_rows.append({
                "agent": agent_name,
                "task": task_id,
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
            })
            print("%s x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (agent_name, task_id, report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
    summary = {
        "agents": sorted(AGENTS),
        "tasks": [t["id"] for t in tasks],
        "clean_grid": {
            "n": len(clean_rows),
            "pass": clean_pass,
            "rows": clean_rows,
        },
        "audit_sample": {
            "n": len(audit_rows),
            "rows": audit_rows,
        },
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w",
              encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
    print("validation done in %.1fs" % (time.time() - started))


if __name__ == "__main__":
    main()
