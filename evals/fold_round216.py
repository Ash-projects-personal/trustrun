"""Fold round 216 into DATASET.md Totals.

Round 216 is the eleventh round on the 15-attack battery
(adaptive_injection shipped 2026-11-16): 23 checks per audit, 6,900
per round. No slice folds this run (audit-78 t22 consistency + data
remain; slice t21-t25 folds when t25 completes).
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-216 + 15 round-1 residual
disk = 0
for n in range(2, 217):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 60192, "disk rows rounds 2-216: %d (expected 60192)" % disk
assert disk + 15 == 60207, "rounds 1-216 audits"

# 2. round check math (rounds 206-216 are 23-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 11 * 300 * 23
assert checks == 1303719, "round check math: %d" % checks

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
assert (a_old, c_old) == (62573, 1397391), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-215 (`reports/round*/summary.json`) | 59,907 | 1,296,819 |",
     "| Labeled eval rounds 1-216 (`reports/round*/summary.json`) | 60,207 | 1,303,719 |", 1),
    ("| **Total** | **62,573** | **1,397,391** |",
     "| **Total** | **62,873** | **1,404,291** |", 1),
    ("Round-audit detail: 59,892 audits sit in the round2-215 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-215: 300 each); the 59,907 total",
     "Round-audit detail: 60,192 audits sit in the round2-216 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-216: 300 each); the 60,207 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 10x300x23 = 1,296,819.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 11x300x23 = 1,303,719.", 1),
    ("round 215: 1,397,391, 397,391 past target.)",
     "round 215: 1,397,391, 397,391 past target; "
     "round 216: 1,404,291, 404,291 past target.)", 1),
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
assert (a_new, c_new) == (62873, 1404291), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 216: Totals now 62,873 / 1,404,291")
