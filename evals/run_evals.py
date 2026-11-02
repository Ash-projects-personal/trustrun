"""Run the Trustrun audit over every agent and task, save the reports.

Usage: python3 run_evals.py

Reads tasks.json, builds the tools in each task's tools_order, and calls
trustrun.cli.run_audit for every agent x task pair with the eval corpus
as the data module input. Writes one formatted report per pair into
reports/<agent>__<task>.txt and a machine readable summary into
reports/summary.json. Every number in those files comes from a real run.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from agents import plan_execute_agent, rag_agent, react_agent  # noqa: E402
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import format_report, run_audit  # noqa: E402

AGENTS = {
    "react": react_agent,
    "rag": rag_agent,
    "plan_execute": plan_execute_agent,
}

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

CORPUS = os.path.join(HERE, "corpus.jsonl")
REPORTS = os.path.join(HERE, "reports")


def main():
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as handle:
        tasks = json.load(handle)
    summary = []
    started = time.time()
    for agent_name, agent in AGENTS.items():
        for task_def in tasks:
            task_id = task_def["id"]
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
            report = run_audit(
                agent, task, data_path=CORPUS, seed=0, k=5
            )
            text = format_report(report)
            path = os.path.join(
                REPORTS, "%s__%s.txt" % (agent_name, task_id)
            )
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text + "\n")
            sections = report["sections"]
            summary.append(
                {
                    "agent": agent_name,
                    "task": task_id,
                    "verdict": report["verdict"],
                    "contract": sections["contract"]["verdict"],
                    "stress": sections["stress"]["verdict"],
                    "consistency": sections["consistency"]["verdict"],
                    "data": sections["data"]["verdict"],
                    "pass_rate_k": sections["consistency"]["pass_rate_k"],
                }
            )
            print(
                "%s x %s -> %s (contract %s, stress %s, consistency %s, data %s)"
                % (
                    agent_name,
                    task_id,
                    report["verdict"],
                    sections["contract"]["verdict"],
                    sections["stress"]["verdict"],
                    sections["consistency"]["verdict"],
                    sections["data"]["verdict"],
                )
            )
    with open(os.path.join(REPORTS, "summary.json"), "w",
              encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
    print("done in %.1fs, %d audits" % (time.time() - started, len(summary)))


if __name__ == "__main__":
    main()
