"""Fold round 198 into DATASET.md Totals; independently re-sum three ways."""
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-198 + 15 round-1 residual
disk = 0
for n in range(2, 199):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 54792, "disk rows rounds 2-198: %d (expected 54792)" % disk
assert disk + 15 == 54807, "rounds 1-198 audits"

# 2. check math
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 105 * 300 * 22
assert checks == 1181619, "check math: %d" % checks

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
assert (a_old, c_old) == (57168, 1275480), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()

EDITS = [
    ("## Totals (2026-11-16 ~15:19 UTC)",
     "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-197 (`reports/round*/summary.json`) | 54,507 | 1,175,019 |",
     "| Labeled eval rounds 1-198 (`reports/round*/summary.json`) | 54,807 | 1,181,619 |", 1),
    ("| **Total** | **57,168** | **1,275,480** |",
     "| **Total** | **57,468** | **1,282,080** |", 1),
    ("Round-audit detail: 54,492 audits sit in the round2-197 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-197: 300 each)",
     "Round-audit detail: 54,792 audits sit in the round2-198 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-198: 300 each)", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 104x300x22 = 1,175,019.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 105x300x22 = 1,181,619.", 1),
    ("round 194: 1,255,680, 255,680 past target; "
     "round 195: 1,262,280, 262,280 past target; "
     "round 196: 1,268,880, 268,880 past target; "
     "round 197: 1,275,480, 275,480 past target.)",
     "round 194: 1,255,680, 255,680 past target; "
     "round 195: 1,262,280, 262,280 past target; "
     "round 196: 1,268,880, 268,880 past target; "
     "round 197: 1,275,480, 275,480 past target; "
     "round 198: 1,282,080, 282,080 past target.)", 1),
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
assert (a_new, c_new) == (57468, 1282080), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded round 198: totals now 57,468 / 1,282,080")
