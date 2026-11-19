"""Fold audit-78 slice t21-t25 into DATASET.md Totals.

Slice t21-t25 is 5 audits / 124 checks (t21/t22 at 23 checks, t23-t25
at 26 — measured from the rows: 1 contract claim + N attacks + 4
consistency + 3 data). CORRECTION: the round-233 research-log entry
carried 118 / 559 — those priced t23-t25 at 24 checks (16-attack
battery); the rows measure 18 attacks on t23-t25, i.e. 26 checks each.
Full 25-task audit re-sums to 565; the five slice rows sum to 565.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")
OUT = os.path.join(HERE, "reports", "real_agents", "clawdbot")

# --- independent re-sums BEFORE editing ---
# 1. slice checks from the rows on disk
all_rows = json.load(open(os.path.join(OUT, "rows_partial.json"),
                          encoding="utf-8"))
assert len(all_rows) == 25, "expected 25 rows, got %d" % len(all_rows)
slice_rows = [r for r in all_rows if r["task"] in
              ("t21_percent_word", "t22_hard_math", "t23_station_add",
               "t24_underspecified", "t25_impossible")]
assert [r["task"] for r in slice_rows] == [
    "t21_percent_word", "t22_hard_math", "t23_station_add",
    "t24_underspecified", "t25_impossible"], "slice row order mismatch"
slice_checks = sum(1 + len(r["attacks"]) + 4 + 3 for r in slice_rows)
assert slice_checks == 124, "slice checks: %d" % slice_checks
full_checks = sum(1 + len(r["attacks"]) + 4 + 3 for r in all_rows)
assert full_checks == 565, "full-audit checks: %d" % full_checks
assert 110 + 110 + 110 + 111 + 124 == 565, "slice rows do not sum to 565"

with open(DS, encoding="utf-8") as h:
    text = h.read()

# 2. full Totals-table re-sum on the CURRENT table
TABLE_ROW = re.compile(r"^\| [^|]*\| ([0-9,]+|-)[^|]*\| ([0-9,]+)", flags=re.M)
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
_tot_block = text[_tot_start:_tot_end]
rows = TABLE_ROW.findall(_tot_block)
a_old = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_old = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_old, c_old) == (68273, 1540491), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

EDITS = [
    ("| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 — slice t16–t20 ONLY, PARTIAL (`reports/real_agents/clawdbot/summary-slice-t16-t20.json`) | 5 | 111 (4 x 22 + 1 x 23) |",
     "| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 — slice t16–t20 ONLY, PARTIAL (`reports/real_agents/clawdbot/summary-slice-t16-t20.json`) | 5 | 111 (4 x 22 + 1 x 23) |\n| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 — slice t21–t25 ONLY, PARTIAL (`reports/real_agents/clawdbot/summary-slice-t21-t25.json`) | 5 | 124 (2 x 23 + 3 x 26) |", 1),
    ("| **Total** | **68,273** | **1,540,491** |",
     "| **Total** | **68,278** | **1,540,615** |", 1),
    ("Partial-slice rule: the audit-78 OpenClaw slice rows (t1–t5, 5 audits /\n110 checks; t6–t10, 5 audits / 110 checks; t11–t15, 5 audits / 110 checks;\nt16–t20, 5 audits / 111 checks) are PARTIAL. When the full\n25-task audit lands, REPLACE all four slice rows with the full-audit row\n(25 audits; checks re-summed from the 25 rows at finalize time — 559 with the\nmixed battery: t1–t19 at 22 checks, t20–t22 at 23, t23–t25 at 24) — never add all five, or the 20 slice\nrows double-count.",
     "Partial-slice rule: the audit-78 OpenClaw slice rows (t1–t5, 5 audits /\n110 checks; t6–t10, 5 audits / 110 checks; t11–t15, 5 audits / 110 checks;\nt16–t20, 5 audits / 111 checks; t21–t25, 5 audits / 124 checks) are PARTIAL.\nWhen the full 25-task audit finalizes, REPLACE all five slice rows with the\nfull-audit row (25 audits; 565 checks, re-summed from the 25 rows: t1–t19 at\n22 checks, t20–t22 at 23, t23–t25 at 26) — never add both, or the 25 slice\nrows double-count. (Correction 2026-11-17: the round-233 log's 559 / 118\nfigures were wrong — they priced t23–t25 at 24 checks, the 16-attack battery;\nthe rows measure 18 attacks on t23–t25, i.e. 26 checks each, so the slice is\n124 and the full audit is 565. The five slice rows sum to 565, exactly the\nfull-audit total, so the finalize replacement is totals-neutral.)", 1),
    ("`reports/real_agents/clawdbot/summary-slice-t11-t15.json`, and\n`reports/real_agents/clawdbot/summary-slice-t16-t20.json`; the raw rows stay\nin `rows_partial.json` until the full audit finalizes.",
     "`reports/real_agents/clawdbot/summary-slice-t11-t15.json`,\n`reports/real_agents/clawdbot/summary-slice-t16-t20.json`, and\n`reports/real_agents/clawdbot/summary-slice-t21-t25.json`; the raw rows stay\nin `rows_partial.json` until the full audit finalizes.", 1),
]
for old, new, expected in EDITS:
    count = text.count(old)
    assert count == expected, (
        "edit %r: expected %d, found %d" % (old[:60], expected, count)
    )
    text = text.replace(old, new)

# --- re-sum the EDITED table and confirm the new Total row ---
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
rows = TABLE_ROW.findall(text[_tot_start:_tot_end])
a_new = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_new = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_new, c_new) == (68278, 1540615), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded slice t21-t25: Totals now 68,278 / 1,540,615")
