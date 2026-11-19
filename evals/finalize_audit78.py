"""Finalize audit-78 (OpenClaw) in DATASET.md Totals.

Replaces the five PARTIAL slice rows (t1-t5, t6-t10, t11-t15, t16-t20,
t21-t25: 25 audits / 110+110+110+111+124 = 565 checks) with the single
full-audit row (25 audits / 565 checks, re-summed from the 25 rows in
reports/real_agents/clawdbot/summary.json). Totals-neutral by
construction: the edited Totals table must re-sum to the same totals.
Run only AFTER run_real_agents_clawdbot_chunked.py --finalize wrote
summary.json (verified: 25 rows, all BLOCK, rows identical to the
pre-finalize rows_partial.json backup).
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

with open(DS, encoding="utf-8") as h:
    text = h.read()

# --- independent re-sums BEFORE editing ---
TABLE_ROW = re.compile(r"^\| [^|]*\| ([0-9,]+|-)[^|]*\| ([0-9,]+)", flags=re.M)
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
_tot_block = text[_tot_start:_tot_end]
rows = TABLE_ROW.findall(_tot_block)
a_old = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_old = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_old, c_old) == (68578, 1548415), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

SLICE_ROWS = (
    "| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 — slice t1–t5 ONLY, PARTIAL (`reports/real_agents/clawdbot/summary-slice-t1-t5.json`) | 5 | 110 (5 x 22) |\n"
    "| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 — slice t6–t10 ONLY, PARTIAL (`reports/real_agents/clawdbot/summary-slice-t6-t10.json`) | 5 | 110 (5 x 22) |\n"
    "| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 — slice t11–t15 ONLY, PARTIAL (`reports/real_agents/clawdbot/summary-slice-t11-t15.json`) | 5 | 110 (5 x 22) |\n"
    "| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 — slice t16–t20 ONLY, PARTIAL (`reports/real_agents/clawdbot/summary-slice-t16-t20.json`) | 5 | 111 (4 x 22 + 1 x 23) |\n"
    "| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 — slice t21–t25 ONLY, PARTIAL (`reports/real_agents/clawdbot/summary-slice-t21-t25.json`) | 5 | 124 (2 x 23 + 3 x 26) |"
)
FULL_ROW = ("| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 "
            "(`reports/real_agents/clawdbot/summary.json`) | 25 | "
            "565 (19 x 22 + 3 x 23 + 3 x 26) |")
assert FULL_ROW not in text, "full-audit row already present"
assert text.count(SLICE_ROWS) == 1, "slice-row block not found exactly once"

OLD_RULE = (
    "Partial-slice rule: the audit-78 OpenClaw slice rows (t1–t5, 5 audits /\n"
    "110 checks; t6–t10, 5 audits / 110 checks; t11–t15, 5 audits / 110 checks;\n"
    "t16–t20, 5 audits / 111 checks; t21–t25, 5 audits / 124 checks) are PARTIAL.\n"
    "When the full 25-task audit finalizes, REPLACE all five slice rows with the\n"
    "full-audit row (25 audits; 565 checks, re-summed from the 25 rows: t1–t19 at\n"
    "22 checks, t20–t22 at 23, t23–t25 at 26) — never add both, or the 25 slice\n"
    "rows double-count. (Correction 2026-11-17: the round-233 log's 559 / 118\n"
    "figures were wrong — they priced t23–t25 at 24 checks, the 16-attack battery;\n"
    "the rows measure 18 attacks on t23–t25, i.e. 26 checks each, so the slice is\n"
    "124 and the full audit is 565. The five slice rows sum to 565, exactly the\n"
    "full-audit total, so the finalize replacement is totals-neutral.)"
)
NEW_RULE = (
    "Audit-78 OpenClaw FINALIZED 2026-11-17 (round-235 run): the five PARTIAL slice\n"
    "rows (t1–t5, 5 audits / 110 checks; t6–t10, 5 / 110; t11–t15, 5 / 110;\n"
    "t16–t20, 5 / 111; t21–t25, 5 / 124) were REPLACED by the single full-audit row\n"
    "(25 audits; 565 checks, re-summed from the 25 rows in summary.json: t1–t19 at\n"
    "22 checks, t20–t22 at 23, t23–t25 at 26) — never add both, or the 25 slice\n"
    "rows double-count. The replacement is totals-neutral (110+110+110+111+124 =\n"
    "565). (Correction 2026-11-17: the round-233 log's 559 / 118 figures were\n"
    "wrong — they priced t23–t25 at 24 checks, the 16-attack battery; the rows\n"
    "measure 18 attacks on t23–t25, i.e. 26 checks each, so the slice is 124 and\n"
    "the full audit is 565.)"
)
assert text.count(OLD_RULE) == 1, "partial-slice rule text not found exactly once"

OLD_SLICES_LIVE = (
    "The slice summaries live at\n"
    "`reports/real_agents/clawdbot/summary-slice-t1-t5.json`,\n"
    "`reports/real_agents/clawdbot/summary-slice-t6-t10.json`,\n"
    "`reports/real_agents/clawdbot/summary-slice-t11-t15.json`,\n"
    "`reports/real_agents/clawdbot/summary-slice-t16-t20.json`, and\n"
    "`reports/real_agents/clawdbot/summary-slice-t21-t25.json`; the raw rows stay\n"
    "in `rows_partial.json` until the full audit finalizes."
)
NEW_SLICES_LIVE = (
    "The full audit lives at `reports/real_agents/clawdbot/summary.json` (rows +\n"
    "evidence in `evidence.json`). The slice summaries remain at\n"
    "`reports/real_agents/clawdbot/summary-slice-t1-t5.json`,\n"
    "`reports/real_agents/clawdbot/summary-slice-t6-t10.json`,\n"
    "`reports/real_agents/clawdbot/summary-slice-t11-t15.json`,\n"
    "`reports/real_agents/clawdbot/summary-slice-t16-t20.json`, and\n"
    "`reports/real_agents/clawdbot/summary-slice-t21-t25.json` as the per-slice\n"
    "record. The pre-finalize rows_partial.json + evidence_partial.json backup is\n"
    "kept in the goal hidden_files audit78-finalize-backup/ directory."
)
assert text.count(OLD_SLICES_LIVE) == 1, "slice-summaries sentence not found exactly once"

EDITS = [
    (SLICE_ROWS, FULL_ROW, 1),
    (OLD_RULE, NEW_RULE, 1),
    (OLD_SLICES_LIVE, NEW_SLICES_LIVE, 1),
]
for old, new, expected in EDITS:
    count = text.count(old)
    assert count == expected, (
        "edit %r: expected %d, found %d" % (old[:60], expected, count)
    )
    text = text.replace(old, new)

# --- re-sum the EDITED table: must be UNCHANGED (totals-neutral) ---
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
rows = TABLE_ROW.findall(text[_tot_start:_tot_end])
a_new = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_new = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_new, c_new) == (68578, 1548415), (
    "edited Totals-table re-sum: %d / %d (expected unchanged 68,578 / 1,548,415)"
    % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("finalized audit 78 in DATASET.md: Totals unchanged 68,578 / 1,548,415")
