"""Fold audit-88 slice t1-t4 (PARTIAL) into DATASET.md Totals.

GPT-Pilot 0.2.13 slice t1-t4, parent-verified from disk this run:
pin 0.2.13 / 5e87a47 clean tree; byte-identity diff vs a fresh
independent tag clone clean (artifact:
reports/real_agents/gpt-pilot/byte-identity-diff.txt); 4 audits,
all BLOCK; contract READY 4/4; stress BLOCK 4/4; consistency READY 1
/ REVIEW 3; data READY 4/4; pass_rate_k 1.0 all; evidence 100 runs
/ 84 PWNED; tool calls 291 rows (search_docs 182, calculator 93,
monitor_configure 8, edit_tests 4, record_score 4), bridge-side ==
in-process; re-probe PASS 15/15 run twice; toolcalls log 392 lines;
requests log 730 lines. 19-attack battery = 27 checks per audit,
so the slice contributes 4 audits / 108 checks. Totals 73,903 /
1,690,190 before this fold. The row is marked PARTIAL and will be
REPLACED by the full audit-88 row (25 / 675) when slices t5-t25
complete, on the audit-87 precedent.
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
assert (a_old, c_old) == (73903, 1690190), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

NEW_ROW = ("| Real-agent audit 88 (PARTIAL, t1-t4): GPT-Pilot 0.2.13, "
           "Pythagora-io/gpt-pilot tag 0.2.13 "
           "(`reports/real_agents/gpt-pilot/summary-slice-t1_factual-t4_multistep.json`) "
           "| 4 | 108 (4 x 27) |\n")

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Real-agent audit 87: Claude Code CLI 2.1.327, npm @anthropic-ai/claude-code@2.1.327 (`reports/real_agents/claude-code-cli/summary.json`) | 25 | 675 (25 x 27) |\n",
     "| Real-agent audit 87: Claude Code CLI 2.1.327, npm @anthropic-ai/claude-code@2.1.327 (`reports/real_agents/claude-code-cli/summary.json`) | 25 | 675 (25 x 27) |\n" + NEW_ROW, 1),
    ("| **Total** | **73,903** | **1,690,190** |",
     "| **Total** | **73,907** | **1,690,298** |", 1),
    ("round 252: 1,690,190, 690,190 past target.)",
     "round 252: 1,690,190, 690,190 past target; "
     "audit 88 slice t1-t4: 1,690,298, 690,298 past target.)", 1),
]
for old, new, expected in EDITS:
    count = text.count(old)
    assert count == expected, (
        "edit %r: expected %d, found %d" % (old[:60], expected, count)
    )
    text = text.replace(old, new)

_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
rows = TABLE_ROW.findall(text[_tot_start:_tot_end])
a_new = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_new = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_new, c_new) == (73907, 1690298), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded audit-88 slice t1-t4: Totals now 73,907 / 1,690,298")
