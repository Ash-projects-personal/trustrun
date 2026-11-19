"""Fold round 244 into DATASET.md Totals.

Round 244 is the third round on the 19-attack battery (PageReaderInject
shipped 2026-11-18): 27 checks per audit, 8,100 per round. Summary.json
md5 f72cde9e333162ec0ba9157fd1cd143c — byte-identical to rounds 242-243:
0 rows moved, all tallies identical, t9 probe and escape probe md5s
unchanged (b778c83554a6b3c12a10af70e7d0551b /
c79d165250369ff576a366d06b3e90ed). The +60 unverified-substring count
(13,358 -> 13,418, same counting method) is seed noise in evidence
text: the perturbation attack's completed field flips True <-> unverified
with seed; it drives no verdict. Totals
71,178 / 1,616,615 before this fold.
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-244 + 15 round-1 residual
disk = 0
for n in range(2, 245):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 68592, "disk rows rounds 2-244: %d (expected 68592)" % disk
assert disk + 15 == 68607, "rounds 1-244 audits"

# 2. round check math (rounds 206-220 are 23-check rounds, round 221
#    is the only 24-check round, rounds 222-241 are 26-check rounds,
#    rounds 242-244 are 27-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24 \
    + 20 * 300 * 26 + 3 * 300 * 27
assert checks == 1518819, "round check math: %d" % checks

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
assert (a_old, c_old) == (71178, 1616615), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-243 (`reports/round*/summary.json`) | 68,307 | 1,510,719 |",
     "| Labeled eval rounds 1-244 (`reports/round*/summary.json`) | 68,607 | 1,518,819 |", 1),
    ("| **Total** | **71,178** | **1,616,615** |",
     "| **Total** | **71,478** | **1,624,715** |", 1),
    ("Round-audit detail: 68,292 audits sit in the round2-243 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-243: 300 each); the 68,307 total",
     "Round-audit detail: 68,592 audits sit in the round2-244 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-244: 300 each); the 68,607 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 2x300x27 = 1,510,719.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 3x300x27 = 1,518,819.", 1),
    ("round 243: 1,616,615, 616,615 past target.)",
     "round 243: 1,616,615, 616,615 past target; "
     "round 244: 1,624,715, 624,715 past target.)", 1),
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
assert (a_new, c_new) == (71478, 1624715), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 244: Totals now 71,478 / 1,624,715")
