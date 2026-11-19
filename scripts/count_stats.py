#!/usr/bin/env python3
"""Recompute Trustrun's public numbers from the stored results in this repo.

Every number in README.md and STATS.md comes from here. Nothing is
estimated: each count is read out of a stored result file or out of
evals/DATASET.md's own accounting table, whose rows each name the
summary file they were counted from.

What is counted
---------------
Audit-level row
    One full run_audit over one agent x one task, or one
    calibration/validation run of the same shape (a labeled row in
    evals/DATASET.md's Totals table).
Check-level labeled judgment
    One labeled verdict at check granularity inside an audit. A full
    audit contributes 8 base checks (contract claim verdicts,
    consistency checks, data checks) plus one survived / not-survived /
    unverified judgment per attack in the battery. The battery grew
    over time (9 attacks in rounds 1-3 up to 19 attacks from round
    242), so checks per audit run from 17 to 27. Single-purpose rows
    (a probe-case verdict, a tenet verdict) count as 1 judgment each.
Framework audited
    One row of the DATASET.md Totals table for a real-agent audit:
    one named agent implementation driven through the standard
    25-task battery. Some frameworks contribute more than one audited
    agent (for example a second agent class from the same package);
    each audited agent counts once. In-progress audits whose slices
    are not yet folded into the Totals table are not counted.

Usage: python3 scripts/count_stats.py
Prints the counts as JSON. Exit code is 0 when the DATASET.md table
re-sums exactly to its own printed Total row, 1 otherwise.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATASET = os.path.join(ROOT, "evals", "DATASET.md")
REAL_AGENTS = os.path.join(ROOT, "evals", "reports", "real_agents")
GOOSE_SUMMARY = os.path.join(REAL_AGENTS, "goose", "summary.json")
RETRY_DROP_SUMMARY = os.path.join(
    ROOT, "evals", "reports", "retry_drop_visibility", "summary.json")


def _number(cell):
    """First integer in a Totals-table cell ('-' counts as 0)."""
    m = re.search(r"[\d,]+", cell)
    return int(m.group(0).replace(",", "")) if m else 0


def dataset_totals():
    text = open(DATASET, encoding="utf-8").read()
    section = text.split("## Totals")[1].split("Round-audit detail")[0]
    rows = re.findall(r"^\| (.+?) \| (.*?) \| (.*?) \|", section, re.M)
    audits = 0
    checks = 0
    frameworks = 0
    printed_audits = None
    printed_checks = None
    for name, a_cell, c_cell in rows:
        if name.startswith("**Total**"):
            printed_audits = _number(a_cell)
            printed_checks = _number(c_cell)
            continue
        audits += _number(a_cell)
        checks += _number(c_cell)
        if name.startswith("Real-agent audit:"):
            frameworks += 1
    return {
        "audits": audits,
        "checks": checks,
        "frameworks_audited": frameworks,
        "printed_audits": printed_audits,
        "printed_checks": printed_checks,
        "table_resums_exactly": (audits == printed_audits
                                 and checks == printed_checks),
    }


def goose_plaintext_injection():
    """Count plaintext-injection outcomes from the stored Goose audit."""
    data = json.load(open(GOOSE_SUMMARY, encoding="utf-8"))
    rows = data["rows"]
    followed = survived = 0
    for row in rows:
        for attack in row["attacks"]:
            if attack["kind"] == "injection" \
                    and attack.get("vector") == "plaintext":
                if attack["survived"] is False:
                    followed += 1
                elif attack["survived"] is True:
                    survived += 1
    return {"tasks": len(rows), "followed": followed, "survived": survived}


def retry_drop_sweep():
    """Count the retry-and-drop tool-failure visibility sweep."""
    data = json.load(open(RETRY_DROP_SUMMARY, encoding="utf-8"))
    rows = data["rows"]
    dropped = sum(1 for r in rows
                  if r.get("visibility_class") == "retry_and_drop")
    retries = sorted({r.get("retry_count") for r in rows})
    return {"tasks": len(rows), "retry_and_drop": dropped,
            "retry_counts": retries}


def main():
    totals = dataset_totals()
    out = {
        "audits": totals["audits"],
        "labeled_checks": totals["checks"],
        "frameworks_audited": totals["frameworks_audited"],
        "dataset_table_printed_total": {
            "audits": totals["printed_audits"],
            "labeled_checks": totals["printed_checks"],
        },
        "dataset_table_resums_exactly": totals["table_resums_exactly"],
        "finding_goose_plaintext_injection": goose_plaintext_injection(),
        "finding_retry_drop_sweep": retry_drop_sweep(),
    }
    print(json.dumps(out, indent=2))
    return 0 if totals["table_resums_exactly"] else 1


if __name__ == "__main__":
    sys.exit(main())
