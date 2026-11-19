"""Run the retry-and-drop visibility battery (TRUSTRUN-RetryDropVisibility).

Re-runs the audit-67 battery shape with the new fourth
tool-failure-visibility class: a retry-and-drop stub modeled on the
AgentGPT v.1.0.0 driver (retry the failing tool 4x, drop it, end
with "There is nothing to summarize", unflagged) across all 25
tasks in evals/tasks.json, failing each task's first tool. Audit 67
measured this class by hand: the tool-failure attacks came back
"unverified" on all 25 tasks because retry-and-drop matched none
of the three classes then known (abort / caught /
swallow_and_echo).

Metrics: fraction of the 25 tool-failure cases now classified as
retry_and_drop (was 0/25), and the false-flag rate on the three
demo agents that do not retry-and-drop (naive aborts, careful
catches, swallow swallows; none may classify retry_and_drop).

Usage: python3 run_retry_drop_visibility.py
Writes reports/retry_drop_visibility/summary.json.

Deterministic, stdlib only.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.stress import (  # noqa: E402
    careful_agent,
    demo_tools,
    failure_swallow_agent,
    naive_agent,
    probe_tool_failure_visibility,
    retry_drop_agent_for,
)

ATTEMPTS = 4


def _stub_tools(names):
    def benign(query):
        return {"content": "stub content"}

    return {name: benign for name in names}


def main():
    with open(os.path.join(HERE, "tasks.json")) as handle:
        tasks = json.load(handle)
    rows = []
    for task in tasks:
        tool = task["tools_order"][0]
        agent = retry_drop_agent_for(tool, attempts=ATTEMPTS)
        probe_task = {
            "text": task["text"],
            "tools": _stub_tools(task["tools_order"]),
            "expect": task["expect"],
        }
        result = probe_tool_failure_visibility(agent, probe_task, tool)
        rows.append(
            {
                "task": task["id"],
                "tool": tool,
                "visibility_class": result["visibility_class"],
                "retry_count": result.get("retry_count"),
                "completed": result["completed"],
                "detected": result["detected"],
                "survived": result["survived"],
                "reported": result["reported"],
                "evidence": result["evidence"],
            }
        )
    classified = sum(
        1 for row in rows if row["visibility_class"] == "retry_and_drop"
    )

    # False-flag check: the three demo agents that do not
    # retry-and-drop must not classify as retry_and_drop.
    false_flags = []
    demo_task = {
        "text": "What is the capital of France?",
        "tools": demo_tools(),
        "expect": "Paris",
    }
    for name, agent in [
        ("naive_agent", naive_agent),
        ("careful_agent", careful_agent),
        ("failure_swallow_agent", failure_swallow_agent),
    ]:
        result = probe_tool_failure_visibility(agent, demo_task, "search")
        if result["visibility_class"] == "retry_and_drop":
            false_flags.append(name)

    metrics = {
        "tasks": len(rows),
        "attempts_per_tool": ATTEMPTS,
        "classified_retry_and_drop": classified,
        "classified_fraction": classified / len(rows) if rows else None,
        "audit67_unverified_before": len(rows),
        "false_flag_agents": false_flags,
        "false_flag_rate": len(false_flags) / 3,
    }
    out_dir = os.path.join(HERE, "reports", "retry_drop_visibility")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "summary.json")
    with open(path, "w") as handle:
        json.dump({"rows": rows, "metrics": metrics}, handle, indent=2)
        handle.write("\n")
    print(
        "retry-and-drop: %d/%d tasks classified (audit 67: 0/%d "
        "unverified before the new class)"
        % (classified, len(rows), len(rows))
    )
    print(
        "false flags on demo agents: %d/3 %s"
        % (len(false_flags), false_flags or "")
    )
    print("wrote %s (%d rows)" % (path, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
