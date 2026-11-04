"""Run Trustrun's full audit over the GDPx-style alignment scenarios.

Usage: python3 run_gdpx_scenarios.py

For each scenario in gdpx_scenarios.py and each demonstrator agent
(shortcut, compliant), runs trustrun.cli.run_audit with the scenario's
contract and the eval corpus as the data module input, k=3 repeated runs.
Writes one formatted report per agent x scenario pair into
reports/gdpx/<agent>__<scenario>.txt and a machine readable summary into
reports/gdpx/summary.json.

The measured quantity is violation detection: the shortcut agent commits
the scenario's violation class, the compliant agent does not, and the
scenario contract fails exactly the shortcut run. Every number in those
files comes from a real run. Nothing is invented.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from gdpx_scenarios import SCENARIOS, build_task  # noqa: E402
from trustrun.cli import format_report, run_audit  # noqa: E402

CORPUS = os.path.join(HERE, "corpus.jsonl")
OUT_DIR = os.path.join(HERE, "reports", "gdpx")
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
            rows.append(
                {
                    "agent": agent_name,
                    "scenario": scenario["id"],
                    "domain": scenario["domain"],
                    "contract_verdict": contract["verdict"],
                    "contract_claims": [
                        {
                            "id": c["id"],
                            "verdict": c["verdict"],
                            "evidence": c["evidence"],
                        }
                        for c in contract["claims"]
                    ],
                    "overall": report["verdict"],
                    "report": os.path.basename(path),
                }
            )
            print(
                "%-28s contract=%-6s overall=%s"
                % (label, contract["verdict"], report["verdict"]),
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
    ready = sum(1 for r in rows if r["overall"] == "READY")
    print(
        "done in %.1fs: %d runs, %d BLOCK, %d READY"
        % (time.time() - started, len(rows), blocked, ready)
    )


if __name__ == "__main__":
    main()
