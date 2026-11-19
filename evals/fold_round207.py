"""Fold round 207 into DATASET.md Totals; independently re-sum three ways.

Round 207 is the second round on the 15-attack battery (adaptive_injection
shipped 2026-11-16): 23 checks per audit, 6,900 per round.
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-207 + 15 round-1 residual
disk = 0
for n in range(2, 208):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 57492, "disk rows rounds 2-207: %d (expected 57492)" % disk
assert disk + 15 == 57507, "rounds 1-207 audits"

# 2. check math (rounds 206-207 are 23-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 2 * 300 * 23
assert checks == 1241619, "check math: %d" % checks

with open(DS, encoding="utf-8") as h:
    text = h.read()

# 3. full Totals-table re-sum on the CURRENT table, then apply the delta
TABLE_ROW = re.compile(r"^\| [^|]*\| ([0-9,]+|-)[^|]*\| ([0-9,]+)", flags=re.M)
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
_tot_block = text[_tot_start:_tot_end]
rows = TABLE_ROW.findall(_tot_block)
a_old = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_old = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_old, c_old) == (59868, 1335180), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-206 (`reports/round*/summary.json`) | 57,207 | 1,234,719 |",
     "| Labeled eval rounds 1-207 (`reports/round*/summary.json`) | 57,507 | 1,241,619 |", 1),
    ("| **Total** | **59,868** | **1,335,180** |",
     "| **Total** | **60,168** | **1,342,080** |", 1),
    ("Round-audit detail: 57,192 audits sit in the round2-206 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-206: 300 each); the 57,207 total",
     "Round-audit detail: 57,492 audits sit in the round2-207 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-207: 300 each); the 57,507 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 1x300x23 = 1,234,719.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 2x300x23 = 1,241,619.", 1),
    ("round 206: 1,335,180, 335,180 past target.)",
     "round 206: 1,335,180, 335,180 past target; "
     "round 207: 1,342,080, 342,080 past target.)", 1),
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
assert (a_new, c_new) == (60168, 1342080), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 207: Totals now 60,168 / 1,342,080")
