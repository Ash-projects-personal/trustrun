"""Fold planted-error judge round 1 into DATASET.md Totals.

Round 1 runs the deterministic demo detecting agent over the full
Skepthical corpus (357 planted + 90 clean tasks) at k=4:
447 audit-level rows, 3,216 check-level judgments
(357 x 2 claims x 4 + 90 x 1 claim x 4).
Totals 76,932 / 1,772,769 before this fold.
"""
import json
import os
import re
import subprocess
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")
REPORT = os.path.join(
    HERE, "reports", "planted_error_judge", "summary.json"
)

# --- verify the round report before editing ---
with open(REPORT, encoding="utf-8") as h:
    report = json.load(h)
assert report["task_count"] == 447, report["task_count"]
assert report["planted_count"] == 357, report["planted_count"]
assert report["clean_count"] == 90, report["clean_count"]
assert report["check_level_judgments"] == 3216, (
    report["check_level_judgments"]
)
# Re-derive the check math from the per-task rows, not the header.
checks = sum(t["check_level_judgments"] for t in report["tasks"])
assert checks == 3216, "per-task check sum: %d" % checks
planted = [t for t in report["tasks"] if t["kind"] == "planted"]
detected = sum(
    1
    for t in planted
    if t["per_claim"][0]["pass_at_1"] == 1.0
)
assert detected == 348, "detected tasks: %d" % detected
assert report["detection_rate"] == detected / 357
assert report["characterisation_rate"] == 0.0
assert report["false_positive_rate"] == 1.0

with open(DS, encoding="utf-8") as h:
    text = h.read()

# --- full Totals-table re-sum on the CURRENT table ---
TABLE_ROW = re.compile(r"^\| [^|]*\| ([0-9,]+|-)[^|]*\| ([0-9,]+)", flags=re.M)
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
_tot_block = text[_tot_start:_tot_end]
rows = TABLE_ROW.findall(_tot_block)
a_old = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_old = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_old, c_old) == (76932, 1772769), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

NEW_ROW = (
    "| Planted-error judge round 1 "
    "(`reports/planted_error_judge/summary.json`) | 447 (357 planted "
    "+ 90 clean) | 3,216 (357 x 2 claims x 4 + 90 x 1 claim x 4) |"
)
NEW_SECTION = """### Planted-error judge target (Skepthical, round 1 folded)

`{task, kind, paper_id, copy_id, module, severity, k, runs,
per_claim, ...}` — one target report per judge agent over a local
checkout of the Skepthical benchmark (30 real arXiv preprints, 357
planted errors in 4 modules x 3 severities; data CC-BY-4.0, papers
NOT redistributed, fetched from arXiv by ID — see
`evals/skepthical/fetch_papers.py`), produced by `trustrun
planted-error-judge` from `trustrun.planted_error_judge`. Each
planted task scores 2 claims (detected, characterised) repeated k=4
times; each clean-copy task scores 1 claim (no findings) repeated
k=4 times. A full target run is 357 planted + 90 clean tasks =
447 audit-level rows and 3,216 check-level judgments. Round 1 ran
the deterministic demo detecting agent (quotes the passage it was
given, generic issue line): detection 348/357 (0.9748), by module
citations 0.9556, numerics 1.0, mathematics 0.9540, general 0.9889;
characterisation 0.0; false-positive rate on clean copies 1.0. The
9 undetected errors are all deletion-type injections whose injected
passage is a substring of the original after normalisation (or
differs only in whitespace): the quote-based detection proxy cannot
register them by construction, because quoting the remaining text
does not distinguish the corrupted passage from the clean one. That
is a known proxy limit, recorded in the module docstring. These
numbers describe the stub agent and the proxy, not a real reviewer;
no model judge is used anywhere in the scoring.
"""

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    (
        "| Rogue evidence pack labeled cases "
        "(`reports/rogue-evidence-pack/summary.json`) | - | 8 (7 "
        "Practice 5 item verdicts + 1 repro-from-pack verdict on "
        "audit-64 mastra) |\n",
        "| Rogue evidence pack labeled cases "
        "(`reports/rogue-evidence-pack/summary.json`) | - | 8 (7 "
        "Practice 5 item verdicts + 1 repro-from-pack verdict on "
        "audit-64 mastra) |\n" + NEW_ROW + "\n",
        1,
    ),
    ("| **Total** | **76,932** | **1,772,769** |",
     "| **Total** | **77,379** | **1,775,985** |", 1),
    ("round 262: 1,772,769, 772,769 past target.)",
     "round 262: 1,772,769, 772,769 past target; planted-error judge "
     "round 1: 1,775,985, 775,985 past target.)", 1),
    (
        "reported as a proxy only, never as the CWE-bench reward.\n",
        "reported as a proxy only, never as the CWE-bench reward.\n\n"
        + NEW_SECTION,
        1,
    ),
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
assert (a_new, c_new) == (77379, 1775985), (
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
print("folded planted-error judge round 1: Totals now 77,379 / 1,775,985")
