"""Fold round 257 into DATASET.md Totals.

Round 257 is the sixteenth round on the 19-attack battery
(PageReaderInject shipped 2026-11-18): 27 checks per audit, 8,100 per
round. Summary.json md5 f72cde9e333162ec0ba9157fd1cd143c — byte-identical
to rounds 242-256: 0 rows moved, all tallies identical, t9 probe
identical, escape probe 20/20. The unverified-substring count
(13,415 -> 13,349, same grep -o method) is seed noise in evidence
text; it drives no verdict. Round ran 87.4s vs 92.8s for round 256.
Totals 75,127 / 1,723,238 before this fold (includes the
audit-88 PARTIAL slice t1-t24 row, 24 / 648).
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
# 1. disk rows rounds 2-257 + 15 round-1 residual
disk = 0
for n in range(2, 258):
    path = os.path.join(HERE, "reports", "round%d" % n, "summary.json")
    with open(path, encoding="utf-8") as h:
        disk += len(json.load(h))
assert disk == 72492, "disk rows rounds 2-257: %d (expected 72492)" % disk
assert disk + 15 == 72507, "rounds 1-257 audits"

# 2. round check math (rounds 206-220 are 23-check rounds, round 221
#    is the only 24-check round, rounds 222-241 are 26-check rounds,
#    rounds 242-257 are 27-check rounds)
checks = 15 * 17 + 24 * 17 + 48 * 17 + 5 * 48 * 19 + 10 * 48 * 21 \
    + 75 * 300 * 21 + 112 * 300 * 22 + 15 * 300 * 23 + 1 * 300 * 24 \
    + 20 * 300 * 26 + 16 * 300 * 27
assert checks == 1624119, "round check math: %d" % checks

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
assert (a_old, c_old) == (75127, 1723238), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Labeled eval rounds 1-256 (`reports/round*/summary.json`) | 72,207 | 1,616,019 |",
     "| Labeled eval rounds 1-257 (`reports/round*/summary.json`) | 72,507 | 1,624,119 |", 1),
    ("| **Total** | **75,127** | **1,723,238** |",
     "| **Total** | **75,427** | **1,731,338** |", 1),
    ("Round-audit detail: 72,192 audits sit in the round2-256 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-256: 300 each); the 72,207 total",
     "Round-audit detail: 72,492 audits sit in the round2-257 summary files\n"
     "(round 2: 24; rounds 3-18: 48 each; rounds 19-257: 300 each); the 72,507 total", 1),
    ("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 15x300x27 = 1,616,019.",
     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 20x300x26 + 16x300x27 = 1,624,119.", 1),
    ("audit 88 slice t20-t24: 1,723,238, 723,238 past target.)",
     "audit 88 slice t20-t24: 1,723,238, 723,238 past target; "
     "round 257: 1,731,338, 731,338 past target.)", 1),
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
assert (a_new, c_new) == (75427, 1731338), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

# Write via temp file + atomic rename with retries: writes on this
# box intermittently fail with EPERM (two windows ~08:18 and ~08:21 UTC
# on 2026-11-19); a direct open("w") truncates the original first,
# which cost DATASET.md its contents once that morning (restored
# byte-identical from the trustrun-git copy). Never write DATASET.md
# in place again.
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
print("folded round 257: Totals now 75,427 / 1,731,338")
