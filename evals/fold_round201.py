"""Fold round 201 into DATASET.md Totals; independently re-sum three ways."""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-201 + 15 round-1 residual
disk = 0
for n in range(2, 202):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 55692, "disk rows rounds 2-201: %d (expected 55692)" % disk
assert disk + 15 == 55707, "rounds 1-201 audits"

# 2. check math
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 108 * 300 * 22
assert checks == 1201419, "check math: %d" % checks

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
assert (a_old, c_old) == (58068, 1295280), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()

EDITS = [
    ("## Totals (2026-11-16 ~16:51 UTC)",
     "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-200 (`reports/round*/summary.json`) | 55,407 | 1,194,819 |",
     "| Labeled eval rounds 1-201 (`reports/round*/summary.json`) | 55,707 | 1,201,419 |", 1),
    ("| **Total** | **58,068** | **1,295,280** |",
     "| **Total** | **58,368** | **1,301,880** |", 1),
    ("Round-audit detail: 55,392 audits sit in the round2-200 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-200: 300 each); the 55,407 total",
     "Round-audit detail: 55,692 audits sit in the round2-201 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-201: 300 each); the 55,707 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 107x300x22 = 1,194,819.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 108x300x22 = 1,201,419.", 1),
    ("round 199: 1,288,680, 288,680 past target; "
     "round 200: 1,295,280, 295,280 past target.)",
     "round 199: 1,288,680, 288,680 past target; "
     "round 200: 1,295,280, 295,280 past target; "
     "round 201: 1,301,880, 301,880 past target.)", 1),
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
assert (a_new, c_new) == (58368, 1301880), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 201: totals now 58,368 / 1,301,880")
