"""Fold round 202 into DATASET.md Totals; independently re-sum three ways."""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-202 + 15 round-1 residual
disk = 0
for n in range(2, 203):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 55992, "disk rows rounds 2-202: %d (expected 55992)" % disk
assert disk + 15 == 56007, "rounds 1-202 audits"

# 2. check math
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 109 * 300 * 22
assert checks == 1208019, "check math: %d" % checks

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
assert (a_old, c_old) == (58368, 1301880), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()

EDITS = [
    ("## Totals (2026-11-16 ~17:24 UTC)",
     "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-201 (`reports/round*/summary.json`) | 55,707 | 1,201,419 |",
     "| Labeled eval rounds 1-202 (`reports/round*/summary.json`) | 56,007 | 1,208,019 |", 1),
    ("| **Total** | **58,368** | **1,301,880** |",
     "| **Total** | **58,668** | **1,308,480** |", 1),
    ("Round-audit detail: 55,692 audits sit in the round2-201 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-201: 300 each); the 55,707 total",
     "Round-audit detail: 55,992 audits sit in the round2-202 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-202: 300 each); the 56,007 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 108x300x22 = 1,201,419.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 109x300x22 = 1,208,019.", 1),
    ("round 200: 1,295,280, 295,280 past target; "
     "round 201: 1,301,880, 301,880 past target.)",
     "round 200: 1,295,280, 295,280 past target; "
     "round 201: 1,301,880, 301,880 past target; "
     "round 202: 1,308,480, 308,480 past target.)", 1),
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
assert (a_new, c_new) == (58668, 1308480), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 202: totals now 58,668 / 1,308,480")
