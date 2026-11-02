"""Dogfood: run dolly-15k through Trustrun's data module.

Not part of the package API. Reads the 15,011 real human written rows
from the Lexsi project's dolly_raw.jsonl (databricks-dolly-15k,
CC BY-SA 3.0) and audits them with audit_dataset.

Two passes:

1. Prompt pass: text is instruction plus input. This is the real audit,
   the same view a training data check would take.
2. Response pass: text is the response. This exists to check the module
   against the Lexsi gate's measured ground truth, because the gate ran
   its near duplicate detector on responses.

Ground truth from the gate (TABLE1_dolly.md, collapse_dolly_full.json):
exact duplicate rows 16 (0.1 percent), near duplicate rows 65
(0.4 percent), template clusters 8888.

Known methodological differences, stated plainly:

- The gate counted exact duplicates on the normalized (prompt,
  response) pair. This module counts them on the single text field, so
  the exact duplicate numbers are not directly comparable.
- The gate's template key is the first four prompt words with numbers
  masked. This module masks numbers and capitalized words across the
  whole text. The cluster counts will differ by design.
- The near duplicate method is identical (word 5 gram Jaccard at 0.8),
  so the response pass near duplicate count should reproduce the
  gate's 65.

Run with: python3 trustrun/data/dogfood.py
"""

import json
import sys
from pathlib import Path

from trustrun.data import audit_dataset

DOLLY = (
    Path.home()
    / "workspace"
    / "hackathons"
    / "lexsi-collapsewatch"
    / "dolly_raw.jsonl"
)

GATE_EXACT_DUP_ROWS = 16
GATE_NEAR_DUP_ROWS = 65
GATE_TEMPLATE_CLUSTERS = 8888


def load_rows():
    rows = []
    with open(DOLLY) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _prompt(row):
    instruction = str(row.get("instruction", ""))
    context = str(row.get("input", "") or "")
    if context.strip():
        return instruction + "\n\n" + context
    return instruction


def _show(title, report):
    print(title)
    print("  records: %d" % report["records"])
    print(
        "  exact duplicates: %d rows (%.3f%%) -> %s"
        % (
            report["exact_duplicate_rows"],
            report["exact_duplicate_rate"] * 100,
            report["metrics"]["exact_duplicates"]["verdict"],
        )
    )
    print(
        "  near duplicates:  %d rows (%.3f%%) -> %s"
        % (
            report["near_duplicate_rows"],
            report["near_duplicate_rate"] * 100,
            report["metrics"]["near_duplicates"]["verdict"],
        )
    )
    print(
        "  template clusters: %d, top sizes %s -> %s"
        % (
            report["template_cluster_count"],
            report["top_template_cluster_sizes"],
            report["metrics"]["template_clusters"]["verdict"],
        )
    )
    print("  overall verdict: %s" % report["verdict"])


def main():
    rows = load_rows()
    print("Trustrun data module dogfood")
    print("Source: %s (%d real rows)" % (DOLLY.name, len(rows)))
    print()

    prompt_records = [{"text": _prompt(r)} for r in rows]
    prompt_report = audit_dataset(prompt_records)
    _show("Prompt pass (instruction + input), the real audit:", prompt_report)
    print()

    response_records = [{"text": str(r.get("output", ""))} for r in rows]
    response_report = audit_dataset(response_records)
    _show("Response pass (output), ground truth comparison:", response_report)
    print()

    print("Against the Lexsi gate ground truth:")
    print(
        "  exact dup rows: gate %d on (prompt, response) pairs vs "
        "module %d on prompts (different definition, not comparable)"
        % (GATE_EXACT_DUP_ROWS, prompt_report["exact_duplicate_rows"])
    )
    near = response_report["near_duplicate_rows"]
    match = "REPRODUCED" if near == GATE_NEAR_DUP_ROWS else "DIFFERS"
    print(
        "  near dup rows: gate %d on responses vs module %d on "
        "responses [%s, same method]"
        % (GATE_NEAR_DUP_ROWS, near, match)
    )
    print(
        "  template clusters: gate %d (first four word key) vs module "
        "%d on prompts (different method, not comparable)"
        % (GATE_TEMPLATE_CLUSTERS, prompt_report["template_cluster_count"])
    )
    ok = near == GATE_NEAR_DUP_ROWS
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
