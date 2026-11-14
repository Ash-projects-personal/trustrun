"""Run the AGORA judge-panel aggregation comparison and report it.

Usage: python3 run_agora_comparison.py

Runs every pool x size x seed cell in agora_validation.py (3 pools,
sizes 20/50/100, 5 seeds = 45 cells, 2,550 labeled items) and writes
reports/agora/summary.json (machine readable) and reports/agora/
summary.txt (human readable). Every number in those files comes from
a real run of the clean-room harness. The paper's reference numbers
(AGORA matching or exceeding Dawid-Skene; advantage widening on small
sets; dispersion-gain Spearman +0.73 and +0.61) are cited in the text
summary for comparison only; they are not Trustrun measurements.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agora_validation import POOLS, SEEDS, SIZES, run_comparison  # noqa: E402

OUT_DIR = os.path.join(HERE, "reports", "agora")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    summary = run_comparison()
    summary["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    summary["pools"] = POOLS
    summary["sizes"] = list(SIZES)
    summary["seeds"] = list(SEEDS)
    summary["references"] = {
        "agora_paper": (
            "Ahn, arXiv:2611.05556: AGORA matches or exceeds "
            "Dawid-Skene on large sets, advantage widens as sets "
            "shrink to a few hundred; dispersion-gain Spearman "
            "+0.73 and +0.61; learned weights track per-judge human "
            "validity."),
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
    lines = []
    lines.append("AGORA judge-panel aggregation comparison")
    lines.append("Generated: %s" % summary["generated_at"])
    lines.append("Cells: %d (3 pools x sizes 20/50/100 x 5 seeds)"
                 % summary["audit_level_rows"])
    lines.append("Labeled items: %d; check-level judgments: %d"
                 % (summary["check_level_judgments"] // 2,
                    summary["check_level_judgments"]))
    lines.append("")
    lines.append("Mean agreement with ground truth (majority vs AGORA):")
    for key in sorted(summary["aggregates"]):
        agg = summary["aggregates"][key]
        lines.append(
            "  %-14s majority %.3f  agora %.3f  gain %+.3f  "
            "dispersion %.3f" % (
                key, agg["mean_majority_agreement"],
                agg["mean_agora_agreement"], agg["mean_gain"],
                agg["mean_dispersion"]))
    lines.append("")
    spearman = summary["dispersion_gain_spearman"]
    lines.append("Dispersion-gain Spearman across cells: %s"
                 % ("%.3f" % spearman if spearman is not None else "n/a"))
    lines.append("(Paper: +0.73 and +0.61 on real benchmarks; this "
                 "number is Trustrun's clean-room measurement.)")
    lines.append("")
    lines.append("Method: %s" % summary["method"])
    with open(os.path.join(OUT_DIR, "summary.txt"), "w") as handle:
        handle.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
