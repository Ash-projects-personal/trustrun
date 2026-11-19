"""Fold round 234 into DATASET.md Totals.

Round 234 is the thirteenth round on the 18-attack battery: 26 checks per
audit, 7,800 per round. Aggregate-identical to rounds 222-233 expected
(summary.json md5 e42d092a506d8a6faddb4c7a5cee4470, the 18-attack
baseline). No slice folds in this script (audit-78 slice t21-t25 folds
separately when t25 completes).
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-233 + 15 round-1 residual
disk = 0
for n in range(2, 235):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 65592, "disk rows rounds 2-234: %d (expected 65592)" % disk
assert disk + 15 == 65607, "rounds 1-234 audits"

# 2. round check math (rounds 206-220 are 23-check rounds, round 221
#    is the only 24-check round, rounds 222-234 are 26-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24 \
    + 13 * 300 * 26
assert checks == 1439919, "round check math: %d" % checks

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
assert (a_old, c_old) == (67973, 1532691), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-233 (`reports/round*/summary.json`) | 65,307 | 1,432,119 |",
     "| Labeled eval rounds 1-234 (`reports/round*/summary.json`) | 65,607 | 1,439,919 |", 1),
    ("| **Total** | **67,973** | **1,532,691** |",
     "| **Total** | **68,273** | **1,540,491** |", 1),
    ("Round-audit detail: 65,292 audits sit in the round2-233 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-233: 300 each); the 65,307 total",
     "Round-audit detail: 65,592 audits sit in the round2-234 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-234: 300 each); the 65,607 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 12x300x26 = 1,432,119.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 13x300x26 = 1,439,919.", 1),
    ("round 233: 1,532,691, 532,691 past target.)",
     "round 233: 1,532,691, 532,691 past target; "
     "round 234: 1,540,491, 540,491 past target.)", 1),
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
assert (a_new, c_new) == (68273, 1540491), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 234: Totals now 68,273 / 1,540,491")
