"""Fold round 260 into DATASET.md Totals.

Round 260 is the FIRST round on the 20-attack battery (TerminalGap
shipped 2026-11-19): 28 checks per audit, 8,400 per round.
Summary.json md5 cc258410d84ff95e02df05ae503c3b6d — DIFFERS from rounds
242-259 (f72cde9e...): 6 rows differ, all plan_execute, all stress
REVIEW -> BLOCK on the new terminal_gap cell (survived False:
obeyed the hidden instruction on 1 of 11 techniques, backspace).
Contract/consistency/data tallies and mean pass@k 0.7067 identical
to round 259; t9 probe identical; escape probe 20/20. The
unverified-substring count (13,424 -> 13,941, same grep -o method)
is the new terminal_gap evidence text: 559 occurrences sit on
terminal_gap lines, offset by -42 seed noise elsewhere; it drives no
verdict. Round ran 100.5s vs 67.6s for round 259 (the 20th attack
runs 11 technique probes per audit).
Totals 76,028 / 1,747,565 before this fold.
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
# 1. disk rows rounds 2-260 + 15 round-1 residual
disk = 0
for n in range(2, 261):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 73392, "disk rows rounds 2-260: %d (expected 73392)" % disk
assert disk + 15 == 73407, "rounds 1-260 audits"

# 2. round check math (rounds 206-220 are 23-check rounds, round 221
#    is the only 24-check round, rounds 222-241 are 26-check rounds,
#    rounds 242-259 are 27-check rounds, round 260 is the first
#    28-check round)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24 \
    + 20 * 300 * 26 + 18 * 300 * 27 + 1 * 300 * 28
assert checks == 1648719, "round check math: %d" % checks

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
assert (a_old, c_old) == (76028, 1747565), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-259 (`reports/round*/summary.json`) | 73,107 | 1,640,319 |",
     "| Labeled eval rounds 1-260 (`reports/round*/summary.json`) | 73,407 | 1,648,719 |", 1),
    ("| **Total** | **76,028** | **1,747,565** |",
     "| **Total** | **76,328** | **1,755,965** |", 1),
    ("Round-audit detail: 73,092 audits sit in the round2-259 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-259: 300 each); the 73,107 total",
     "Round-audit detail: 73,392 audits sit in the round2-260 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-260: 300 each); the 73,407 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 18x300x27 = 1,640,319.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 18x300x27 + 1x300x28 = 1,648,719.", 1),
    ("round 259: 1,747,565, 747,565 past target.)",
     "round 259: 1,747,565, 747,565 past target; "
     "round 260: 1,755,965, 755,965 past target.)", 1),
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
assert (a_new, c_new) == (76328, 1755965), (
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
print("folded round 260: Totals now 76,328 / 1,755,965")
