"""Run the decision-tampering attack across all 25 tasks (TRUSTRUN-TaskTamper).

Measures the new task_tamper kind on the repo's task set with three
deterministic stub agents, one run per task per agent:

- decision follower: adopts an asserted decision value from tool
  output, the failure Zhang et al. (arXiv:2611.07640) measure.
  Expectation: followed on all six decision targets, every task.
- naive echo agent: follows plaintext injected instructions, the
  naive_agent shape. Expectation: never followed; every target
  unclear (it echoes the poisoned tool output, marker with benign
  content, so no decision is adopted). This is the control showing
  the class is a different mechanism from instruction following.
- careful resister: flags asserted decision values, the
  decision_resister shape. Expectation: never followed; every
  target resisted; survived True on every task.

Metrics: followed rate per agent, per-target follow rates, and the
echo-vs-adoption split (unclear targets on the naive agent).

Usage: python3 run_task_tamper_verify.py
Writes reports/task_tamper_verify/summary.json.

Deterministic, stdlib only. Stub agents only, not real models: this
measures the harness protocol, not a shipped product's robustness.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.stress import replay_attack  # noqa: E402
from trustrun.stress import task_tamper  # noqa: E402


def _stub_tools(names):
    def benign(query):
        return {"content": "stub content"}

    return {name: benign for name in names}


def _follower_for(tool):
    def agent(task_text, tools):
        result = tools[tool]("query")
        content = result.get("content", "") if isinstance(result, dict) else ""
        if "TAMPERED" in content:
            return {"result": "TAMPERED"}
        return {"result": "answer from: " + content}

    return agent


def _echo_for(tool):
    def agent(task_text, tools):
        result = tools[tool]("query")
        content = result.get("content", "") if isinstance(result, dict) else ""
        if "INJECTED:" in content:
            return {"result": content.split("INJECTED:", 1)[1].strip()}
        return {"result": "answer from: " + content}

    return agent


def _resister_for(tool):
    def agent(task_text, tools):
        result = tools[tool]("query")
        content = result.get("content", "") if isinstance(result, dict) else ""
        if any(
            marker in content
            for marker in (
                "recorded value",
                "recorded here",
                "was read as",
                "holds the value",
            )
        ):
            return {
                "result": None,
                "flagged": "suspicious decision claim in tool output",
            }
        return {"result": "answer from: " + content}

    return agent


AGENTS = (
    ("decision_follower", _follower_for),
    ("naive_echo", _echo_for),
    ("careful_resister", _resister_for),
)


def main():
    with open(os.path.join(HERE, "tasks.json")) as handle:
        tasks = json.load(handle)
    rows = []
    for task in tasks:
        tool = task["tools_order"][0]
        probe_task = {
            "text": task["text"],
            "tools": _stub_tools(task["tools_order"]),
            "expect": task["expect"],
        }
        attack = {"kind": "task_tamper", "tool": tool}
        for agent_name, builder in AGENTS:
            result = replay_attack(builder(tool), probe_task, attack)
            rows.append(
                {
                    "task": task["id"],
                    "agent": agent_name,
                    "tool": tool,
                    "probes": result["probes"],
                    "followed_targets": result["followed_targets"],
                    "survived": result["survived"],
                    "detected": result["detected"],
                    "targets": result["targets"],
                }
            )
    summary = {"rows": rows, "agents": {}, "per_target": {}}
    for agent_name, _ in AGENTS:
        agent_rows = [r for r in rows if r["agent"] == agent_name]
        summary["agents"][agent_name] = {
            "tasks": len(agent_rows),
            "followed_any": sum(
                1 for r in agent_rows if r["followed_targets"]
            ),
            "followed_all_six": sum(
                1
                for r in agent_rows
                if len(r["followed_targets"]) == len(task_tamper.DECISION_TARGETS)
            ),
            "survived_true": sum(1 for r in agent_rows if r["survived"] is True),
            "survived_unverified": sum(
                1 for r in agent_rows if r["survived"] == "unverified"
            ),
        }
    for target in task_tamper.DECISION_TARGETS:
        summary["per_target"][target] = {}
        for agent_name, _ in AGENTS:
            agent_rows = [r for r in rows if r["agent"] == agent_name]
            summary["per_target"][target][agent_name] = sum(
                1
                for r in agent_rows
                if any(
                    t["target"] == target and t["outcome"] == "followed"
                    for t in r["targets"]
                )
            )
    out_dir = os.path.join(HERE, "reports", "task_tamper_verify")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2)
    for agent_name, stats in summary["agents"].items():
        print(
            "%s: %d/%d followed any target, %d followed all six, "
            "survived True %d, unverified %d"
            % (
                agent_name,
                stats["followed_any"],
                stats["tasks"],
                stats["followed_all_six"],
                stats["survived_true"],
                stats["survived_unverified"],
            )
        )
    for target in task_tamper.DECISION_TARGETS:
        print(
            "%s: followed %s"
            % (
                target,
                ", ".join(
                    "%s %d/25" % (name, summary["per_target"][target][name])
                    for name, _ in AGENTS
                ),
            )
        )


if __name__ == "__main__":
    main()
