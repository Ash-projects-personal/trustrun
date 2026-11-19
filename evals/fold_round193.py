"""Fold round 193 into DATASET.md Totals; independently re-sum three ways."""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-193 + 15 round-1 residual
disk = 0
for n in range(2, 194):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 53292, "disk rows rounds 2-193: %d (expected 53292)" % disk
assert disk + 15 == 53307, "rounds 1-193 audits"
# 2. check math
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 100 * 300 * 22
assert checks == 1148619, "check math: %d" % checks

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
assert (a_old, c_old) == (55668, 1242480), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()

EDITS = [
    ("## Totals (2026-11-16 ~12:52 UTC)",
     "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-192 (`reports/round*/summary.json`) | 53,007 | 1,142,019 |",
     "| Labeled eval rounds 1-193 (`reports/round*/summary.json`) | 53,307 | 1,148,619 |", 1),
    ("| **Total** | **55,668** | **1,242,480** |",
     "| **Total** | **55,968** | **1,249,080** |", 1),
    ("Round-audit detail: 52,992 audits sit in the round2-192 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-192: 300 each)",
     "Round-audit detail: 53,292 audits sit in the round2-193 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-193: 300 each)", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 99x300x22 = 1,142,019.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 100x300x22 = 1,148,619.", 1),
    ("round 191: 1,235,770, 235,770 past target; round 192: 1,242,480, 242,480 past target.)",
     "round 191: 1,235,770, 235,770 past target; round 192: 1,242,480, 242,480 past target; "
     "round 193: 1,249,080, 249,080 past target.)", 1),
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
assert (a_new, c_new) == (55968, 1249080), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 193: rounds 53,307 / 1,148,619; grand total 55,968 / 1,249,080")
print("Totals header now:", utc)
