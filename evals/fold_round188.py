"""Fold round 188 into DATASET.md Totals; independently re-sum three ways."""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-188 + 15 round-1 residual
disk = 0
for n in range(2, 189):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 51792, "disk rows rounds 2-188: %d (expected 51792)" % disk
assert disk + 15 == 51807, "rounds 1-188 audits"
# 2. check math
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 95 * 300 * 22
assert checks == 1115619, "check math: %d" % checks

with open(DS, encoding="utf-8") as h:
    text = h.read()

# 3. full Totals-table re-sum on the CURRENT table, then apply the delta
# (audit column may carry a parenthetical, e.g. "330 (300 clean + ...)").
# Scope to the Totals table block only: a battery-size table above it
# (lines 34-37) has the same 3-column shape.
TABLE_ROW = re.compile(r"^\| [^|]*\| ([0-9,]+|-)[^|]*\| ([0-9,]+)", flags=re.M)
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
_tot_block = text[_tot_start:_tot_end]
rows = TABLE_ROW.findall(_tot_block)
a_old = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_old = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_old, c_old) == (54163, 1209370), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()

EDITS = [
    ("## Totals (2026-11-16 ~10:19 UTC)",
     "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-187 (`reports/round*/summary.json`) | 51,507 | 1,109,019 |",
     "| Labeled eval rounds 1-188 (`reports/round*/summary.json`) | 51,807 | 1,115,619 |", 1),
    ("| **Total** | **54,163** | **1,209,370** |",
     "| **Total** | **54,463** | **1,215,970** |", 1),
    ("Round-audit detail: 51,492 audits sit in the round2-187 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-187: 300 each)",
     "Round-audit detail: 51,792 audits sit in the round2-188 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-188: 300 each)", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 94x300x22 = 1,109,019.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 95x300x22 = 1,115,619.", 1),
    ("round 186: 1,202,770, 202,770 past target; round 187: 1,209,370, 209,370 past target.)",
     "round 186: 1,202,770, 202,770 past target; round 187: 1,209,370, 209,370 past target; "
     "round 188: 1,215,970, 215,970 past target.)", 1),
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
assert (a_new, c_new) == (54463, 1215970), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 188: rounds 51,807 / 1,115,619; grand total 54,463 / 1,215,970")
print("Totals header now:", utc)
