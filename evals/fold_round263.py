"""Fold round 263 into DATASET.md Totals.

Round 263 is the FOURTH round on the 20-attack battery (TerminalGap
shipped 2026-11-19): 28 checks per audit, 8,400 per round.
Totals 77,384 / 1,776,233 before this fold.
"""
import json
import os
import re
import subprocess
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

# --- independent re-sums BEFORE editing ---
# 1. disk rows rounds 2-263 + 15 round-1 residual
disk = 0
for n in range(2, 264):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 74292, "disk rows rounds 2-263: %d (expected 74292)" % disk
assert disk + 15 == 74307, "rounds 1-263 audits"

# 2. round check math (rounds 260-263 are 28-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24 \
    + 20 * 300 * 26 + 18 * 300 * 27 + 4 * 300 * 28
assert checks == 1673919, "round check math: %d" % checks

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
assert (a_old, c_old) == (77384, 1776233), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-262 (`reports/round*/summary.json`) | 74,007 | 1,665,519 |",
     "| Labeled eval rounds 1-263 (`reports/round*/summary.json`) | 74,307 | 1,673,919 |", 1),
    ("| **Total** | **77,384** | **1,776,233** |",
     "| **Total** | **77,684** | **1,784,633** |", 1),
    ("Round-audit detail: 73,992 audits sit in the round2-262 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-262: 300 each); the 74,007 total",
     "Round-audit detail: 74,292 audits sit in the round2-263 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-263: 300 each); the 74,307 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 18x300x27 + 3x300x28 = 1,665,519.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 18x300x27 + 4x300x28 = 1,673,919.", 1),
    ("audit 90 slices t1–t4 + t5–t9: 1,776,233, 776,233 past target.)",
     "audit 90 slices t1–t4 + t5–t9: 1,776,233, 776,233 past target; "
     "round 263: 1,784,633, 784,633 past target.)", 1),
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
assert (a_new, c_new) == (77684, 1784633), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

# Write via temp file + atomic rename with retries: writes on this
# box intermittently fail with EPERM; a direct open("w") truncates
# the original first, which cost DATASET.md its contents once
# (restored byte-identical from the trustrun-git copy). Never write
# DATASET.md in place again.
tmp = None
for attempt in range(5):
    try:
        fd, tmp = tempfile.mkstemp(dir=HERE, prefix=".DATASET-tmp-")
        with os.fdopen(fd, "w", encoding="utf-8") as h:
            h.write(text)
            h.flush()
            os.fsync(h.fileno())
        assert os.path.getsize(tmp) == len(text.encode("utf-8"))
        os.replace(tmp, DS)
        tmp = None
        break
    except PermissionError:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            tmp = None
        if attempt == 4:
            raise
        time.sleep(5)
assert tmp is None
print("folded round 263: Totals now 77,684 / 1,784,633")
