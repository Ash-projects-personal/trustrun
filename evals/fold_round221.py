"""Fold round 221 into DATASET.md Totals.

Round 221 is the FIRST round on the 16-attack battery
(task_tamper wired into cli._default_attacks 2026-11-16 22:41; round-221
files written 23:49, after the wiring; report files carry task_tamper
evidence lines): 24 checks per audit, 7,200 per round. Verdicts moved
vs rounds 206-220 (REVIEW 114 / BLOCK 186, 44 REVIEW->BLOCK flips, all
in stress) while contract/consistency/data/pass@k are unchanged, which
is the expected signature of the added attack. No slice folds this run
(audit-78 t23-t25 remain; slice t21-t25 folds when t25 completes).
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-221 + 15 round-1 residual
disk = 0
for n in range(2, 222):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 61692, "disk rows rounds 2-221: %d (expected 61692)" % disk
assert disk + 15 == 61707, "rounds 1-221 audits"

# 2. round check math (rounds 206-220 are 23-check rounds, round 221
#    is the first 24-check round: 15x300x23 + 1x300x24)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24
assert checks == 1338519, "round check math: %d" % checks

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
assert (a_old, c_old) == (64073, 1431891), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-220 (`reports/round*/summary.json`) | 61,407 | 1,331,319 |",
     "| Labeled eval rounds 1-221 (`reports/round*/summary.json`) | 61,707 | 1,338,519 |", 1),
    ("| **Total** | **64,073** | **1,431,891** |",
     "| **Total** | **64,373** | **1,439,091** |", 1),
    ("Round-audit detail: 61,392 audits sit in the round2-220 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-220: 300 each); the 61,407 total",
     "Round-audit detail: 61,692 audits sit in the round2-221 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-221: 300 each); the 61,707 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 = 1,331,319.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 = 1,338,519.", 1),
    ("round 220: 1,431,891, 431,891 past target.)",
     "round 220: 1,431,891, 431,891 past target; "
     "round 221: 1,439,091, 439,091 past target.)", 1),
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
assert (a_new, c_new) == (64373, 1439091), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 221: Totals now 64,373 / 1,439,091")
