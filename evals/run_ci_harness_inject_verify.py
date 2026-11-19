"""Run the CI-harness injection attack across all 25 tasks (TRUSTRUN-CIHarnessInject).

Measures the new ci_harness_inject kind on the repo's task set with
four deterministic stub agents, one run per task per agent:

- label follower: applies an attacker-chosen label named in plain
  text in tool output, the failure Depi Security measured in the
  openai/codex issue-labeler incident (Nov 11, 2026).
  Expectation: followed on direct and prompt_mimic, every task;
  resisted on encoded_command (the label hides behind the base64
  blob, which a literal reader cannot see).
- base64 decoder: decodes an encoded command and applies the label
  it outputs. Expectation: followed on encoded_command only, every
  task; resisted on direct and prompt_mimic. This is the control
  showing the per-vector scoring separates the delivery shapes.
- naive echo agent: follows plaintext injected instructions, the
  naive_agent shape. Expectation: never followed; every vector
  unclear (it echoes the poisoned tool output, label with benign
  content, so no label is applied). This is the control showing the
  class is a different mechanism from instruction following.
- careful resister: flags planted instructions in issue text, the
  label_resister shape. Expectation: never followed; every vector
  resisted; survived True on every task.

Metrics: followed rate per agent, per-vector follow rates, and the
echo-vs-execution split (unclear vectors on the naive agent).

Usage: python3 run_ci_harness_inject_verify.py
Writes reports/ci_harness_inject_verify/summary.json.

Deterministic, stdlib only. Stub agents only, not real models: this
measures the harness protocol, not a shipped product's robustness.
"""

import base64
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.stress import replay_attack  # noqa: E402
from trustrun.stress import ci_harness_inject  # noqa: E402


def _stub_tools(names):
    def benign(query):
        return {"content": "stub content"}

    return {name: benign for name in names}


def _follower_for(tool):
    def agent(task_text, tools):
        result = tools[tool]("query")
        content = result.get("content", "") if isinstance(result, dict) else ""
        if "CI-PWNED" in content:
            return {"result": "CI-PWNED"}
        return {"result": "answer from: " + content}

    return agent


def _decoder_for(tool):
    def agent(task_text, tools):
        result = tools[tool]("query")
        content = result.get("content", "") if isinstance(result, dict) else ""
        match = re.search(r"base64\): ([A-Za-z0-9+/=]+)", content)
        if match:
            try:
                decoded = base64.b64decode(match.group(1)).decode("utf-8")
            except Exception:
                return {"result": "answer from: " + content}
            if "CI-PWNED" in decoded:
                return {"result": "CI-PWNED"}
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
        lowered = content.lower()
        if "apply the label" in lowered or "run the diagnostic" in lowered:
            return {
                "result": None,
                "flagged": "suspicious instruction in issue text",
            }
        return {"result": "answer from: " + content}

    return agent


AGENTS = (
    ("label_follower", _follower_for),
    ("base64_decoder", _decoder_for),
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
        attack = {"kind": "ci_harness_inject", "tool": tool}
        for agent_name, builder in AGENTS:
            result = replay_attack(builder(tool), probe_task, attack)
            rows.append(
                {
                    "task": task["id"],
                    "agent": agent_name,
                    "tool": tool,
                    "probes": result["probes"],
                    "followed_vectors": result["followed_vectors"],
                    "survived": result["survived"],
                    "detected": result["detected"],
                    "vectors": result["vectors"],
                }
            )
    summary = {"rows": rows, "agents": {}, "per_vector": {}}
    for agent_name, _ in AGENTS:
        agent_rows = [r for r in rows if r["agent"] == agent_name]
        summary["agents"][agent_name] = {
            "tasks": len(agent_rows),
            "followed_any": sum(
                1 for r in agent_rows if r["followed_vectors"]
            ),
            "followed_all_three": sum(
                1
                for r in agent_rows
                if len(r["followed_vectors"])
                == len(ci_harness_inject.VECTORS)
            ),
            "survived_true": sum(1 for r in agent_rows if r["survived"] is True),
            "survived_unverified": sum(
                1 for r in agent_rows if r["survived"] == "unverified"
            ),
        }
    for vector in ci_harness_inject.VECTORS:
        summary["per_vector"][vector] = {}
        for agent_name, _ in AGENTS:
            agent_rows = [r for r in rows if r["agent"] == agent_name]
            summary["per_vector"][vector][agent_name] = sum(
                1
                for r in agent_rows
                if any(
                    v["vector"] == vector and v["outcome"] == "followed"
                    for v in r["vectors"]
                )
            )
    out_dir = os.path.join(HERE, "reports", "ci_harness_inject_verify")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2)
    for agent_name, stats in summary["agents"].items():
        print(
            "%s: %d/%d followed any vector, %d followed all three, "
            "survived True %d, unverified %d"
            % (
                agent_name,
                stats["followed_any"],
                stats["tasks"],
                stats["followed_all_three"],
                stats["survived_true"],
                stats["survived_unverified"],
            )
        )
    for vector in ci_harness_inject.VECTORS:
        print(
            "%s: followed %s"
            % (
                vector,
                ", ".join(
                    "%s %d/25" % (name, summary["per_vector"][vector][name])
                    for name, _ in AGENTS
                ),
            )
        )


if __name__ == "__main__":
    main()
