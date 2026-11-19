"""Fold round 232 into DATASET.md Totals.

Round 232 is the eleventh round on the 18-attack battery: 26 checks per
audit, 7,800 per round. Aggregate-identical to rounds 222-231 expected
(summary.json md5 e42d092a506d8a6faddb4c7a5cee4470, the 18-attack
baseline). No slice folds this run (audit-78 t24-t25 remain; slice
t21-t25 folds when t25 completes).
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-230 + 15 round-1 residual
disk = 0
for n in range(2, 233):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 64992, "disk rows rounds 2-232: %d (expected 64992)" % disk
assert disk + 15 == 65007, "rounds 1-232 audits"

# 2. round check math (rounds 206-220 are 23-check rounds, round 221
#    is the only 24-check round, rounds 222-232 are 26-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24 \
    + 11 * 300 * 26
assert checks == 1424319, "round check math: %d" % checks

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
assert (a_old, c_old) == (67373, 1517091), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-231 (`reports/round*/summary.json`) | 64,707 | 1,416,519 |",
     "| Labeled eval rounds 1-232 (`reports/round*/summary.json`) | 65,007 | 1,424,319 |", 1),
    ("| **Total** | **67,373** | **1,517,091** |",
     "| **Total** | **67,673** | **1,524,891** |", 1),
    ("Round-audit detail: 64,692 audits sit in the round2-231 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-231: 300 each); the 64,707 total",
     "Round-audit detail: 64,992 audits sit in the round2-232 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-232: 300 each); the 65,007 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 10x300x26 = 1,416,519.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 11x300x26 = 1,424,319.", 1),
    ("round 231: 1,517,091, 517,091 past target.)",
     "round 231: 1,517,091, 517,091 past target; "
     "round 232: 1,524,891, 524,891 past target.)", 1),
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
assert (a_new, c_new) == (67673, 1524891), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 232: Totals now 67,673 / 1,524,891")
