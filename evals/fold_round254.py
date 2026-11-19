"""Fold round 254 into DATASET.md Totals.

Round 254 is the thirteenth round on the 19-attack battery
(PageReaderInject shipped 2026-11-18): 27 checks per audit, 8,100 per
round. Summary.json md5 f72cde9e333162ec0ba9157fd1cd143c — byte-identical
to rounds 242-253: 0 rows moved, all tallies identical, t9 probe
identical, escape probe 20/20. The unverified-substring count
(13,352 -> 13,235, same grep -o method) is seed noise in evidence
text; it drives no verdict. Round ran 84.3s vs 81.9s for round 253.
Totals 74,212 / 1,698,533 before this fold (includes the
audit-88 PARTIAL slice t1-t9 row, 9 / 243).
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-254 + 15 round-1 residual
disk = 0
for n in range(2, 255):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 71592, "disk rows rounds 2-254: %d (expected 71592)" % disk
assert disk + 15 == 71607, "rounds 1-254 audits"

# 2. round check math (rounds 206-220 are 23-check rounds, round 221
#    is the only 24-check round, rounds 222-241 are 26-check rounds,
#    rounds 242-254 are 27-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24 \
    + 20 * 300 * 26 + 13 * 300 * 27
assert checks == 1599819, "round check math: %d" % checks

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
assert (a_old, c_old) == (74212, 1698533), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-253 (`reports/round*/summary.json`) | 71,307 | 1,591,719 |",
     "| Labeled eval rounds 1-254 (`reports/round*/summary.json`) | 71,607 | 1,599,819 |", 1),
    ("| **Total** | **74,212** | **1,698,533** |",
     "| **Total** | **74,512** | **1,706,633** |", 1),
    ("Round-audit detail: 71,292 audits sit in the round2-253 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-253: 300 each); the 71,307 total",
     "Round-audit detail: 71,592 audits sit in the round2-254 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-254: 300 each); the 71,607 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 12x300x27 = 1,591,719.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 13x300x27 = 1,599,819.", 1),
    ("audit 88 slice t5-t9: 1,698,533, 698,533 past target.)",
     "audit 88 slice t5-t9: 1,698,533, 698,533 past target; "
     "round 254: 1,706,633, 706,633 past target.)", 1),
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
assert (a_new, c_new) == (74512, 1706633), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 254: Totals now 74,512 / 1,706,633")
