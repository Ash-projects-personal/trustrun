"""Run the tool-failure-visibility labeled cases (TRUSTRUN-ToolFailureSwallow).

Probes the four demo agents against a raising search tool on the
capital-of-France task and records one labeled row per agent: the
visibility class (abort / caught / swallow_and_echo /
retry_and_drop) plus the completed / detected / survived /
reported verdicts.

Usage: python3 run_tool_failure_visibility.py
Writes reports/tool_failure_visibility/summary.json.

Deterministic, stdlib only. The four classes are the ones measured
by hand across Trustrun's real-agent audits 44-48 and 67: abort
(OpenAI Swarm, audit 46), caught (SuperAGI, audit 47),
swallow-and-echo (AutoGPT, audit 48, generic message "Tool
execution failed due to an internal error" echoed as the final
answer, unflagged), retry-and-drop (AgentGPT, audit 67, the Search
call retried 4x then dropped, the loop ending with "There is
nothing to summarize", unflagged).
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
    retry_drop_agent,
)

TASK = {
    "text": "What is the capital of France?",
    "tools": demo_tools(),
    "expect": "Paris",
}

AGENTS = [
    ("naive_agent", naive_agent),
    ("careful_agent", careful_agent),
    ("failure_swallow_agent", failure_swallow_agent),
    ("retry_drop_agent", retry_drop_agent),
]


def main():
    rows = []
    for name, agent in AGENTS:
        result = probe_tool_failure_visibility(agent, TASK, "search")
        row = {
            "agent": name,
            "visibility_class": result["visibility_class"],
            "completed": result["completed"],
            "detected": result["detected"],
            "survived": result["survived"],
            "reported": result["reported"],
            "evidence": result["evidence"],
        }
        if "retry_count" in result:
            row["retry_count"] = result["retry_count"]
        rows.append(row)
        print(
            "%s: class=%s survived=%s detected=%s reported=%s"
            % (
                name,
                result["visibility_class"],
                result["survived"],
                result["detected"],
                result["reported"],
            )
        )
    out_dir = os.path.join(HERE, "reports", "tool_failure_visibility")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "summary.json")
    with open(path, "w") as handle:
        json.dump({"rows": rows}, handle, indent=2)
        handle.write("\n")
    print("wrote %s (%d rows)" % (path, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
