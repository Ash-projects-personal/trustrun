"""Fold round 252 into DATASET.md Totals.

Round 252 is the eleventh round on the 19-attack battery
(PageReaderInject shipped 2026-11-18): 27 checks per audit, 8,100 per
round. Summary.json md5 f72cde9e333162ec0ba9157fd1cd143c — byte-identical
to rounds 242-251: 0 rows moved, all tallies identical, t9 probe
identical, escape probe 20/20. The -108 unverified-substring count
(13,409 -> 13,301, same counting method) is seed noise in evidence
text: the perturbation attack's completed field flips True <->
unverified with seed; it drives no verdict. Round ran 170.7s vs
217.5s for round 251 (no parallel worker slice competing for CPU
this time; the audit-88 resume worker was dispatched after the round
started). Totals 73,603 / 1,682,090 before this fold.
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-252 + 15 round-1 residual
disk = 0
for n in range(2, 253):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 70992, "disk rows rounds 2-252: %d (expected 70992)" % disk
assert disk + 15 == 71007, "rounds 1-252 audits"

# 2. round check math (rounds 206-220 are 23-check rounds, round 221
#    is the only 24-check round, rounds 222-241 are 26-check rounds,
#    rounds 242-252 are 27-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24 \
    + 20 * 300 * 26 + 11 * 300 * 27
assert checks == 1583619, "round check math: %d" % checks

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
assert (a_old, c_old) == (73603, 1682090), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-251 (`reports/round*/summary.json`) | 70,707 | 1,575,519 |",
     "| Labeled eval rounds 1-252 (`reports/round*/summary.json`) | 71,007 | 1,583,619 |", 1),
    ("| **Total** | **73,603** | **1,682,090** |",
     "| **Total** | **73,903** | **1,690,190** |", 1),
    ("Round-audit detail: 70,692 audits sit in the round2-251 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-251: 300 each); the 70,707 total",
     "Round-audit detail: 70,992 audits sit in the round2-252 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-252: 300 each); the 71,007 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 10x300x27 = 1,575,519.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 11x300x27 = 1,583,619.", 1),
    ("round 251: 1,682,090, 682,090 past target.)",
     "round 251: 1,682,090, 682,090 past target; "
     "round 252: 1,690,190, 690,190 past target.)", 1),
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
assert (a_new, c_new) == (73903, 1690190), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 252: Totals now 73,903 / 1,690,190")
