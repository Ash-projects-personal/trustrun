"""Fold round 209 + audit-78 slice t16-t20 into DATASET.md Totals.

Round 209 is the fourth round on the 15-attack battery
(adaptive_injection shipped 2026-11-16): 23 checks per audit, 6,900
per round. Slice t16-t20 is 5 audits / 111 checks (t16-t19 at 22,
t20 at 23 — the first slice row carrying the 15th attack).
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")
SLICE = os.path.join(HERE, "reports", "real_agents", "clawdbot",
                     "summary-slice-t16-t20.json")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-209 + 15 round-1 residual
disk = 0
for n in range(2, 210):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 58092, "disk rows rounds 2-209: %d (expected 58092)" % disk
assert disk + 15 == 58107, "rounds 1-209 audits"

# 2. round check math (rounds 206-209 are 23-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 4 * 300 * 23
assert checks == 1255419, "round check math: %d" % checks

# 3. slice check count, derived from the slice rows themselves
# (1 contract claim + N stress attacks + 4 consistency + 3 data)
with open(SLICE, encoding="utf-8") as h:
    slice_summary = json.load(h)
assert slice_summary["audits"] == 5
assert [r["task"] for r in slice_summary["rows"]] == [
    "t16_komorida", "t17_beethoven", "t18_tokyo", "t19_roosevelt",
    "t20_wine"]
slice_checks = sum(1 + len(r["attacks"]) + 4 + 3
                   for r in slice_summary["rows"])
assert slice_checks == 111, "slice check math: %d" % slice_checks

with open(DS, encoding="utf-8") as h:
    text = h.read()

# 4. full Totals-table re-sum on the CURRENT table, then apply the delta
TABLE_ROW = re.compile(r"^\| [^|]*\| ([0-9,]+|-)[^|]*\| ([0-9,]+)", flags=re.M)
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
_tot_block = text[_tot_start:_tot_end]
rows = TABLE_ROW.findall(_tot_block)
a_old = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_old = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_old, c_old) == (60468, 1348980), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-208 (`reports/round*/summary.json`) | 57,807 | 1,248,519 |",
     "| Labeled eval rounds 1-209 (`reports/round*/summary.json`) | 58,107 | 1,255,419 |", 1),
    ("| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 — slice t11–t15 ONLY, PARTIAL (`reports/real_agents/clawdbot/summary-slice-t11-t15.json`) | 5 | 110 (5 x 22) |",
     "| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 — slice t11–t15 ONLY, PARTIAL (`reports/real_agents/clawdbot/summary-slice-t11-t15.json`) | 5 | 110 (5 x 22) |\n"
     "| Real-agent audit 78: OpenClaw 2026.11.5-beta.3 — slice t16–t20 ONLY, PARTIAL (`reports/real_agents/clawdbot/summary-slice-t16-t20.json`) | 5 | 111 (4 x 22 + 1 x 23) |", 1),
    ("| **Total** | **60,468** | **1,348,980** |",
     "| **Total** | **60,773** | **1,355,991** |", 1),
    ("Round-audit detail: 57,792 audits sit in the round2-208 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-208: 300 each); the 57,807 total",
     "Round-audit detail: 58,092 audits sit in the round2-209 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-209: 300 each); the 58,107 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 3x300x23 = 1,248,519.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 4x300x23 = 1,255,419.", 1),
    ("Partial-slice rule: the audit-78 OpenClaw slice rows (t1–t5, 5 audits /\n"
     "110 checks; t6–t10, 5 audits / 110 checks; t11–t15, 5 audits / 110 checks) are PARTIAL. When the full\n"
     "25-task audit lands, REPLACE all three slice rows with the full-audit row\n"
     "(25 / 550) — never add all four, or the 15 slice rows double-count.\n"
     "The slice summaries live at\n"
     "`reports/real_agents/clawdbot/summary-slice-t1-t5.json`,\n"
     "`reports/real_agents/clawdbot/summary-slice-t6-t10.json`, and\n"
     "`reports/real_agents/clawdbot/summary-slice-t11-t15.json`; the raw rows stay\n"
     "in `rows_partial.json` until the full audit finalizes.",
     "Partial-slice rule: the audit-78 OpenClaw slice rows (t1–t5, 5 audits /\n"
     "110 checks; t6–t10, 5 audits / 110 checks; t11–t15, 5 audits / 110 checks;\n"
     "t16–t20, 5 audits / 111 checks) are PARTIAL. When the full\n"
     "25-task audit lands, REPLACE all four slice rows with the full-audit row\n"
     "(25 audits; checks re-summed from the 25 rows at finalize time — 556 if the\n"
     "15-attack battery holds for t21–t25) — never add all five, or the 20 slice\n"
     "rows double-count.\n"
     "The slice summaries live at\n"
     "`reports/real_agents/clawdbot/summary-slice-t1-t5.json`,\n"
     "`reports/real_agents/clawdbot/summary-slice-t6-t10.json`,\n"
     "`reports/real_agents/clawdbot/summary-slice-t11-t15.json`, and\n"
     "`reports/real_agents/clawdbot/summary-slice-t16-t20.json`; the raw rows stay\n"
     "in `rows_partial.json` until the full audit finalizes.", 1),
    ("round 208: 1,348,980, 348,980 past target.)",
     "round 208: 1,348,980, 348,980 past target; "
     "round 209: 1,355,991, 355,991 past target.)", 1),
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
assert (a_new, c_new) == (60773, 1355991), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 209 + slice t16-t20: Totals now 60,773 / 1,355,991")
