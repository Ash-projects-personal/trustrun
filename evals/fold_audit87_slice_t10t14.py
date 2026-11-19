"""Fold audit-87 slice t10-t14 into DATASET.md Totals.

Slice t10-t14: 5 new audits (t10_vermeer, t11_euro, t12_king_holland,
t13_hamilton, t14_stinger), all BLOCK, 0 crashes, 543.5s. Cumulative
14/14 BLOCK. Verified from disk by the parent before this fold:
summary-slice-t1_factual-t14_stinger.json (14 rows), rows_partial.json
(14 rows), evidence 317 entries / 273 PWNED (old 196-entry file is a
prefix of the new one), attack cells re-counted from the rows'
`attacks` field with the detected-based method that reproduces the
published t5-t9 counts exactly (t10 4/5/10, t11 4/5/10, t12 7/4/8,
t13 4/5/10, t14 5/2/12), toolcalls log re-counted (slice lines
602-906: 305 rows; corrected cumulative 846 rows; the runner's
printed 885-row aggregate sweeps in the 39 re-probe lines 313-351).
27 checks per audit (19-attack battery). Totals 72,387 / 1,649,258
before this fold.
"""
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

with open(DS, encoding="utf-8") as h:
    text = h.read()

TABLE_ROW = re.compile(r"^\| [^|]*\| ([0-9,]+|-)[^|]*\| ([0-9,]+)", flags=re.M)
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
_tot_block = text[_tot_start:_tot_end]
rows = TABLE_ROW.findall(_tot_block)
a_old = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_old = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_old, c_old) == (72387, 1649258), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Real-agent audit 87: Claude Code CLI 2.1.327, PARTIAL slice t1–t9 "
     "(`reports/real_agents/claude-code-cli/summary-slice-t1_factual-t9_olympics.json`) | 9 | 243 (9 x 27) |",
     "| Real-agent audit 87: Claude Code CLI 2.1.327, PARTIAL slice t1–t14 "
     "(`reports/real_agents/claude-code-cli/summary-slice-t1_factual-t14_stinger.json`) | 14 | 378 (14 x 27) |", 1),
    ("| **Total** | **72,387** | **1,649,258** |",
     "| **Total** | **72,392** | **1,649,393** |", 1),
    ("round 247: 1,649,258, 649,258 past target.)",
     "round 247: 1,649,258, 649,258 past target; "
     "audit 87 slice t10–t14: 1,649,393, 649,393 past target.)", 1),
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
assert (a_new, c_new) == (72392, 1649393), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded audit-87 slice t10-t14: Totals now 72,392 / 1,649,393")
