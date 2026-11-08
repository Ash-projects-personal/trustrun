"""Focused verification for TRUSTRUN-CheatCoverage.

Runs the three capital tasks (t1_factual, t8_imperative, t18_tokyo)
over all twelve clean-room agents, same protocol as round 19
(trustrun.cli.run_audit, k=5, seed=17), after the corpus fix added
Berlin (fact-10) and Rome (fact-11) documents. Round 19 is the
before baseline: t18 consistency BLOCK 12/12 with pass_rate_k 1.0
(the identical-output cheating flag firing on the France vs Italy
variants, whose answers the corpus could not distinguish).

Writes one formatted report per agent x task pair into
reports/cheatcoverage-verify/<agent>__<task>.txt and a machine
readable summary into reports/cheatcoverage-verify/summary.json.
Expected yield: 36 audits, 756 check-level judgments (21 per audit
at the 13-attack battery).

This script was derived from run_evals_round19.py with the task list
restricted to the three capital tasks. Its REPORTS constant was
verified to point at cheatcoverage-verify/ before the run, so it
cannot overwrite any round directory.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

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
from trustrun.cli import format_report, run_audit  # noqa: E402

AGENTS = {
    "react": react_agent,
    "rag": rag_agent,
    "plan_execute": plan_execute_agent,
    "hardened": hardened_agent,
    "reflection": reflection_agent,
    "guardrail_rag": guardrail_rag_agent,
    "cautious": cautious_agent,
    "clarification": clarification_agent,
    "verifying": verifying_agent,
    "literal": literal_agent,
    "abstaining": abstaining_agent,
    "retry": retry_agent,
}

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

CORPUS = os.path.join(HERE, "corpus.jsonl")
REPORTS = os.path.join(HERE, "reports", "cheatcoverage-verify")

SEED = 17  # same seed as round 19, so the numbers are comparable
TASK_IDS = ("t1_factual", "t8_imperative", "t18_tokyo")


def main():
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as handle:
        tasks = [t for t in json.load(handle) if t["id"] in TASK_IDS]
    assert len(tasks) == 3, "expected 3 capital tasks, got %d" % len(tasks)
    assert len(AGENTS) == 12, "expected 12 agents, got %d" % len(AGENTS)
    assert REPORTS.endswith("cheatcoverage-verify"), REPORTS
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
                agent, task, data_path=CORPUS, seed=SEED, k=5
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
                    "cheating_flag": sections["consistency"]["cheating_flag"],
                    "cheating_evidence": sections["consistency"][
                        "cheating_evidence"
                    ],
                    "stress_attacks": len(sections["stress"]["attacks"]),
                }
            )
            print(
                "%s x %s -> %s (contract %s, stress %s, consistency %s, "
                "cheating %s)"
                % (
                    agent_name,
                    task_id,
                    report["verdict"],
                    sections["contract"]["verdict"],
                    sections["stress"]["verdict"],
                    sections["consistency"]["verdict"],
                    sections["consistency"]["cheating_flag"],
                )
            )
    with open(os.path.join(REPORTS, "summary.json"), "w",
              encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
    print("done in %.1fs, %d audits" % (time.time() - started, len(summary)))


if __name__ == "__main__":
    main()
