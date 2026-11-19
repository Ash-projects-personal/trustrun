"""Fold round 241 into DATASET.md Totals.

Round 241 is the twentieth round on the 18-attack battery: 26 checks per
audit, 7,800 per round. Aggregate-identical to rounds 222-240 expected
(summary.json md5 e42d092a506d8a6faddb4c7a5cee4470, the 18-attack
baseline). No slice folds in this script (audit-82 ForgeCode already folded
2026-11-17; totals 70,178 / 1,590,015 before this fold).
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-241 + 15 round-1 residual
disk = 0
for n in range(2, 242):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 67692, "disk rows rounds 2-241: %d (expected 67692)" % disk
assert disk + 15 == 67707, "rounds 1-241 audits"

# 2. round check math (rounds 206-220 are 23-check rounds, round 221
#    is the only 24-check round, rounds 222-241 are 26-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24 \
    + 20 * 300 * 26
assert checks == 1494519, "round check math: %d" % checks

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
assert (a_old, c_old) == (70178, 1590015), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-240 (`reports/round*/summary.json`) | 67,407 | 1,486,719 |",
     "| Labeled eval rounds 1-241 (`reports/round*/summary.json`) | 67,707 | 1,494,519 |", 1),
    ("| **Total** | **70,178** | **1,590,015** |",
     "| **Total** | **70,478** | **1,597,815** |", 1),
    ("Round-audit detail: 67,392 audits sit in the round2-240 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-240: 300 each); the 67,407 total",
     "Round-audit detail: 67,692 audits sit in the round2-241 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-241: 300 each); the 67,707 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 19x300x26 = 1,486,719.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 = 1,494,519.", 1),
    ("audit 82 (ForgeCode): 1,590,015, 590,015 past target.)",
     "audit 82 (ForgeCode): 1,590,015, 590,015 past target; "
     "round 241: 1,597,815, 597,815 past target.)", 1),
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
assert (a_new, c_new) == (70478, 1597815), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 241: Totals now 70,478 / 1,597,815")
