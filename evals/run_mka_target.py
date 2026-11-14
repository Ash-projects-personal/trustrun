"""Run Trustrun's MKA eval target: the 10 public MKA showcase tasks
through the contract + consistency pipeline, for all 12 clean-room
agents, k=5 runs per agent x task.

Usage: python3 run_mka_target.py

Protocol: trustrun.mka_target.run_mka_target with an empty tool set
(no file tools exist in this harness; the MKA input files are listed
by name only and recorded as unprocessed). Seed 0: the stub agents
are deterministic, so the seed does not move their outputs; the
round's value is the labeled rows, not new verdicts. Writes one
formatted report per agent x task pair into reports/mka/<agent>__<task>.txt
and a machine readable summary into reports/mka/summary.json.

Expected yield: 120 audits (12 agents x 10 tasks), 50,100
check-level judgments (12 x 10 tasks x 5 runs x 835 criteria).
Autorater-vs-judge agreement is NOT measured: MKA's autorater runs
inside the Stirrup harness and is not available as a callable here;
see trustrun/mka_target for the scope note. Every number in the
output files comes from a real run. Nothing is invented.
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
from trustrun.mka_target import run_mka_target  # noqa: E402

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

MKA_DIR = os.path.join(HERE, "mka")
REPORTS = os.path.join(HERE, "reports", "mka")
K = 5
SEED = 0


def _format_task_report(agent_name, task_report):
    lines = [
        "MKA target: agent %s, task %s (%s, %s)"
        % (
            agent_name,
            task_report["task"],
            task_report["vertical"],
            task_report["domain"],
        ),
        "criteria: %d (verifiable: %d), k=%d, seed=%d"
        % (
            task_report["criteria"],
            task_report["verifiable_criteria"],
            task_report["k"],
            task_report["seed"],
        ),
        "run 1 contract: passed %d, failed %d, unverified %d"
        % (
            task_report["passed_run1"],
            task_report["failed_run1"],
            task_report["unverified_run1"],
        ),
        "pass rate over verifiable claims (run 1): %s"
        % (task_report["pass_rate_verifiable_run1"],),
        "weighted pass rate over verifiable claims (run 1): %s"
        % (task_report["weighted_pass_rate_verifiable_run1"],),
        "unverifiable share (run 1): %s"
        % (task_report["unverifiable_share_run1"],),
        "mean pass@1 over verifiable criteria: %s"
        % (task_report["mean_pass_at_1"],),
        "mean pass@k over verifiable criteria: %s"
        % (task_report["mean_pass_at_k"],),
    ]
    for run in task_report["runs"]:
        lines.append(
            "run %d: agent_error=%s verdict=%s passed=%d failed=%d unverified=%d"
            % (
                run["run"],
                run["agent_error"],
                run["verdict"],
                run["passed"],
                run["failed"],
                run["unverified"],
            )
        )
        lines.append("  deliverable: %s" % run["deliverable"][:200].replace("\n", " "))
    return "\n".join(lines) + "\n"


def main():
    started = time.time()
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(MKA_DIR, "tasks.json")) as handle:
        bundle = json.load(handle)
    tasks = bundle["tasks"]
    assert len(tasks) == 10
    assert bundle["criterion_count"] == 835

    summary = {
        "target": "mka",
        "source": bundle["source"],
        "revision": bundle["revision"],
        "license": bundle["license"],
        "k": K,
        "seed": SEED,
        "agents": {},
        "totals": {
            "audits": 0,
            "check_level_judgments": 0,
            "criteria": bundle["criterion_count"],
        },
    }
    for agent_name, agent in AGENTS.items():
        report = run_mka_target(agent, tasks, k=K, seed=SEED)
        summary["agents"][agent_name] = report
        summary["totals"]["audits"] += report["task_count"]
        summary["totals"]["check_level_judgments"] += report[
            "check_level_judgments"
        ]
        for task_report in report["tasks"]:
            filename = "%s__%s.txt" % (agent_name, task_report["task"])
            with open(os.path.join(REPORTS, filename), "w") as handle:
                handle.write(_format_task_report(agent_name, task_report))
        print(
            "%s: mean pass@1=%s mean pass@k=%s verifiable=%d/%d"
            % (
                agent_name,
                report["mean_pass_at_1"],
                report["mean_pass_at_k"],
                report["verifiable_criteria"],
                report["total_criteria"],
            )
        )
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=1)
    print(
        "done in %.1fs, %d audits, %d check-level judgments"
        % (
            time.time() - started,
            summary["totals"]["audits"],
            summary["totals"]["check_level_judgments"],
        )
    )


if __name__ == "__main__":
    main()
