"""Fold round 265 into DATASET.md Totals.

Round 265 is the SIXTH round on the 20-attack battery (TerminalGap
shipped 2026-11-19): 28 checks per audit, 8,400 per round.
Summary md5 cc258410d84ff95e02df05ae503c3b6d — IDENTICAL to rounds
260-264 (sixth identical round). Totals 77,994 / 1,793,313 before
this fold.
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
# 1. disk rows rounds 2-265 + 15 round-1 residual
disk = 0
for n in range(2, 266):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 74892, "disk rows rounds 2-265: %d (expected 74892)" % disk
assert disk + 15 == 74907, "rounds 1-265 audits"

# 2. round check math (rounds 260-265 are 28-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24 \
    + 20 * 300 * 26 + 18 * 300 * 27 + 6 * 300 * 28
assert checks == 1690719, "round check math: %d" % checks

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
assert (a_old, c_old) == (77994, 1793313), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-264 (`reports/round*/summary.json`) | 74,607 | 1,682,319 |",
     "| Labeled eval rounds 1-265 (`reports/round*/summary.json`) | 74,907 | 1,690,719 |", 1),
    ("| **Total** | **77,994** | **1,793,313** |",
     "| **Total** | **78,294** | **1,801,713** |", 1),
    ("Round-audit detail: 74,592 audits sit in the round2-264 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-264: 300 each); the 74,607 total",
     "Round-audit detail: 74,892 audits sit in the round2-265 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-265: 300 each); the 74,907 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 18x300x27 + 5x300x28 = 1,682,319.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 18x300x27 + 6x300x28 = 1,690,719.", 1),
    ("audit 90 slice t15–t19: 1,793,313, 793,313 past target.)",
     "audit 90 slice t15–t19: 1,793,313, 793,313 past target; "
     "round 265: 1,801,713, 801,713 past target.)", 1),
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
assert (a_new, c_new) == (78294, 1801713), (
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
print("folded round 265: Totals now 78,294 / 1,801,713")
