"""Fold round 186 into DATASET.md Totals; independently re-sum three ways."""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-186 + 15 round-1 residual
disk = 0
for n in range(2, 187):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 51192, "disk rows rounds 2-186: %d (expected 51192)" % disk
assert disk + 15 == 51207, "rounds 1-186 audits"
# 2. check math
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 93 * 300 * 22
assert checks == 1102419, "check math: %d" % checks

with open(DS, encoding="utf-8") as h:
    text = h.read()

# 3. full Totals-table re-sum on the CURRENT table, then apply the delta
# (audit column may carry a parenthetical, e.g. "330 (300 clean + ...)").
# Scope to the Totals table block only: a battery-size table above it
# (lines 34-37) has the same 3-column shape.
TABLE_ROW = re.compile(r"^\| [^|]*\| ([0-9,]+|-)[^|]*\| ([0-9,]+)", flags=re.M)
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
_tot_block = text[_tot_start:_tot_end]
rows = TABLE_ROW.findall(_tot_block)
a_old = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_old = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_old, c_old) == (53563, 1196170), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()

EDITS = [
    ("## Totals (2026-11-16 ~09:22 UTC)",
     "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-185 (`reports/round*/summary.json`) | 50,907 | 1,095,819 |",
     "| Labeled eval rounds 1-186 (`reports/round*/summary.json`) | 51,207 | 1,102,419 |", 1),
    ("| **Total** | **53,563** | **1,196,170** |",
     "| **Total** | **53,863** | **1,202,770** |", 1),
    ("Round-audit detail: 50,892 audits sit in the round2-185 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-185: 300 each)",
     "Round-audit detail: 51,192 audits sit in the round2-186 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-186: 300 each)", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 92x300x22 = 1,095,819.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 93x300x22 = 1,102,419.", 1),
    ("round 184: 1,189,570, 189,570 past target.)",
     "round 184: 1,189,570, 189,570 past target; round 185: 1,196,170, 196,170 past target; "
     "round 186: 1,202,770, 202,770 past target.)", 1),
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
assert (a_new, c_new) == (53863, 1202770), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 186: rounds 51,207 / 1,102,419; grand total 53,863 / 1,202,770")
print("Totals header now:", utc)
