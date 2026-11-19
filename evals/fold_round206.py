"""Fold round 206 into DATASET.md Totals; independently re-sum three ways.

Round 206 is the first round on the 15-attack battery (adaptive_injection
shipped 2026-11-16): 23 checks per audit, 6,900 per round.
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-206 + 15 round-1 residual
disk = 0
for n in range(2, 207):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 57192, "disk rows rounds 2-206: %d (expected 57192)" % disk
assert disk + 15 == 57207, "rounds 1-206 audits"

# 2. check math (round 206 is the first 23-check round)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 1 * 300 * 23
assert checks == 1234719, "check math: %d" % checks

with open(DS, encoding="utf-8") as h:
    text = h.read()

# 3. full Totals-table re-sum on the CURRENT table, then apply the delta
# (audit column may carry a parenthetical, e.g. "330 (300 clean + ...)).
# Scope to the Totals table block only: a battery-size table above it
# (lines 34-37) has the same 3-column shape.
TABLE_ROW = re.compile(r"^\| [^|]*\| ([0-9,]+|-)[^|]*\| ([0-9,]+)", flags=re.M)
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
_tot_block = text[_tot_start:_tot_end]
rows = TABLE_ROW.findall(_tot_block)
a_old = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_old = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_old, c_old) == (59568, 1328280), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()

EDITS = [
    ("## Totals (2026-11-16 ~19:21 UTC)",
     "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-205 (`reports/round*/summary.json`) | 56,907 | 1,227,819 |",
     "| Labeled eval rounds 1-206 (`reports/round*/summary.json`) | 57,207 | 1,234,719 |", 1),
    ("| **Total** | **59,568** | **1,328,280** |",
     "| **Total** | **59,868** | **1,335,180** |", 1),
    ("Round-audit detail: 56,892 audits sit in the round2-205 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-205: 300 each); the 56,907 total",
     "Round-audit detail: 57,192 audits sit in the round2-206 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-206: 300 each); the 57,207 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 = 1,227,819.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 1x300x23 = 1,234,719.", 1),
    ("check-level judgments from round 94 onward (21 checks through round 93,\n"
     "at the 13-attack battery).",
     "check-level judgments from round 94 through round 205 (21 checks through round 93,\n"
     "at the 13-attack battery); 300 audits x 23 checks = 6,900 check-level\n"
     "judgments from round 206 onward, at the 15-attack battery.", 1),
    ("round 204: 1,321,680, 321,680 past target; "
     "round 205: 1,328,280, 328,280 past target.)",
     "round 204: 1,321,680, 321,680 past target; "
     "round 205: 1,328,280, 328,280 past target; "
     "round 206: 1,335,180, 335,180 past target.)", 1),
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
assert (a_new, c_new) == (59868, 1335180), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 206: Totals now 59,868 / 1,335,180")
