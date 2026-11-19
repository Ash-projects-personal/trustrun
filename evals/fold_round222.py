"""Fold round 222 into DATASET.md Totals.

Round 222 is the FIRST round on the 18-attack battery (task_tamper 16th,
ci_harness_inject 17th, prompt_adware 18th, all shipped 2026-11-16/17):
26 checks per audit, 7,800 per round. No round ever ran at 25 checks
(round 221 was 16 attacks / 24 checks; round 222 jumps straight to
18 / 26). No slice folds this run (audit-78 t23-t25 remain; slice
t21-t25 folds when t25 completes).
"""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-222 + 15 round-1 residual
disk = 0
for n in range(2, 223):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 61992, "disk rows rounds 2-222: %d (expected 61992)" % disk
assert disk + 15 == 62007, "rounds 1-222 audits"

# 2. round check math (rounds 206-220 are 23-check rounds, round 221
#    is the only 24-check round, round 222 is the first 26-check round)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24 \
    + 1 * 300 * 26
assert checks == 1346319, "round check math: %d" % checks

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
assert (a_old, c_old) == (64373, 1439091), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-221 (`reports/round*/summary.json`) | 61,707 | 1,338,519 |",
     "| Labeled eval rounds 1-222 (`reports/round*/summary.json`) | 62,007 | 1,346,319 |", 1),
    ("| **Total** | **64,373** | **1,439,091** |",
     "| **Total** | **64,673** | **1,446,891** |", 1),
    ("Round-audit detail: 61,692 audits sit in the round2-221 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-221: 300 each); the 61,707 total",
     "Round-audit detail: 61,992 audits sit in the round2-222 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-222: 300 each); the 62,007 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 = 1,338,519.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 1x300x26 = 1,346,319.", 1),
    ("round 221: 1,439,091, 439,091 past target.)",
     "round 221: 1,439,091, 439,091 past target; "
     "round 222: 1,446,891, 446,891 past target.)", 1),
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
assert (a_new, c_new) == (64673, 1446891), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 222: Totals now 64,673 / 1,446,891")
