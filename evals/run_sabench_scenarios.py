"""Run Trustrun's full audit over the SABench-style side-effect scenarios.

Usage: python3 run_sabench_scenarios.py

For each scenario in sabench_scenarios.py and each demonstrator agent
(shortcut, compliant), runs trustrun.cli.run_audit with the scenario's
contract, authorization set, and effect kinds, plus the eval corpus as
the data module input, k=3 repeated runs. Writes one formatted report
per agent x scenario pair into reports/sabench/<agent>__<scenario>.txt
and a machine readable summary into reports/sabench/summary.json.

The measured quantity is collateral-damage detection: the shortcut
agent commits its trap family's unauthorized side effect, the
compliant agent does not, and the scenario contract fails exactly the
shortcut run. The summary also records the CAREFUL-Bench accounting
(unrequested destructive calls, duplicate writes, redundant reads,
surplus steps, confirmed vs unconfirmed destructive calls) from the
contract section's side-effect oracle. Every number in those files
comes from a real run. Nothing is invented.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from sabench_scenarios import SCENARIOS, build_task  # noqa: E402
from trustrun.cli import format_report, run_audit  # noqa: E402

CORPUS = os.path.join(HERE, "corpus.jsonl")
OUT_DIR = os.path.join(HERE, "reports", "sabench")
K = 3


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    started = time.time()
    for scenario in SCENARIOS:
        for agent_name, agent in scenario["agents"].items():
            label = "%s__%s" % (agent_name, scenario["id"])
            report = run_audit(
                agent, build_task(scenario), data_path=CORPUS, seed=0, k=K
            )
            path = os.path.join(OUT_DIR, label + ".txt")
            with open(path, "w") as fh:
                fh.write(format_report(report))
            contract = report["sections"]["contract"]
            side = contract.get("side_effects") or {}
            rows.append(
                {
                    "agent": agent_name,
                    "scenario": scenario["id"],
                    "domain": scenario["domain"],
                    "trap_family": scenario["trap_family"],
                    "contract_verdict": contract["verdict"],
                    "contract_claims": [
                        {
                            "id": c["id"],
                            "verdict": c["verdict"],
                            "evidence": c["evidence"],
                        }
                        for c in contract["claims"]
                    ],
                    "side_effects": {
                        "verdict": side.get("verdict"),
                        "collateral_damage": side.get("collateral_damage"),
                        "cd_rate": side.get("cd_rate"),
                        "goal_satisfied_with_cd": side.get(
                            "goal_satisfied_with_cd"),
                        "unrequested_destructive": side.get(
                            "unrequested_destructive"),
                        "duplicate_writes": side.get("duplicate_writes"),
                        "redundant_reads": side.get("redundant_reads"),
                        "surplus_steps": side.get("surplus_steps"),
                        "confirmed_destructive": side.get(
                            "confirmed_destructive"),
                        "unconfirmed_destructive": side.get(
                            "unconfirmed_destructive"),
                    },
                    "overall": report["verdict"],
                    "report": os.path.basename(path),
                }
            )
            print(
                "%-28s contract=%-6s side=%-18s overall=%s"
                % (
                    label,
                    contract["verdict"],
                    side.get("verdict"),
                    report["verdict"],
                ),
                flush=True,
            )
    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "k": K,
        "data_path": os.path.basename(CORPUS),
        "runs": rows,
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    blocked = sum(1 for r in rows if r["overall"] == "BLOCK")
    print(
        "%d runs, %d BLOCK, %.1fs"
        % (len(rows), blocked, time.time() - started)
    )


if __name__ == "__main__":
    main()
