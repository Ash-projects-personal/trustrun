"""Fold round 212 into DATASET.md Totals.

Round 212 is the seventh round on the 15-attack battery
(adaptive_injection shipped 2026-11-16): 23 checks per audit, 6,900
per round. No slice folds this run (audit-78 t21 consistency + data
remain).
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-212 + 15 round-1 residual
disk = 0
for n in range(2, 213):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 58992, "disk rows rounds 2-212: %d (expected 58992)" % disk
assert disk + 15 == 59007, "rounds 1-212 audits"

# 2. round check math (rounds 206-212 are 23-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 7 * 300 * 23
assert checks == 1276119, "round check math: %d" % checks

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
assert (a_old, c_old) == (61373, 1369791), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-211 (`reports/round*/summary.json`) | 58,707 | 1,269,219 |",
     "| Labeled eval rounds 1-212 (`reports/round*/summary.json`) | 59,007 | 1,276,119 |", 1),
    ("| **Total** | **61,373** | **1,369,791** |",
     "| **Total** | **61,673** | **1,376,691** |", 1),
    ("Round-audit detail: 58,692 audits sit in the round2-211 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-211: 300 each); the 58,707 total",
     "Round-audit detail: 58,992 audits sit in the round2-212 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-212: 300 each); the 59,007 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 6x300x23 = 1,269,219.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 7x300x23 = 1,276,119.", 1),
    ("round 211: 1,369,791, 369,791 past target.)",
     "round 211: 1,369,791, 369,791 past target; "
     "round 212: 1,376,691, 376,691 past target.)", 1),
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
assert (a_new, c_new) == (61673, 1376691), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 212: Totals now 61,673 / 1,376,691")
