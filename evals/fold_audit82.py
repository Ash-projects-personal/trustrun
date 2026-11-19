"""Fold audit 82 (ForgeCode) into DATASET.md Totals.

Audit 82 is one full-audit row: 25 audits / 650 checks at 8 base +
18 attacks. Totals before this fold: 70,153 / 1,589,365 (after the
round-240 fold). Totals after: 70,178 / 1,590,015.
"""
import re
import subprocess

HERE = "/home/hatch/workspace/hackathons/trustrun/evals"
DS = HERE + "/DATASET.md"

with open(DS, encoding="utf-8") as h:
    text = h.read()

TABLE_ROW = re.compile(r"^\| [^|]*\| ([0-9,]+|-)[^|]*\| ([0-9,]+)", flags=re.M)


def resum(txt):
    s = txt.index("## Totals (")
    e = txt.index("| **Total** |", s)
    rows = TABLE_ROW.findall(txt[s:e])
    a = sum(0 if x == "-" else int(x.replace(",", "")) for x, _ in rows)
    c = sum(int(y.replace(",", "")) for _, y in rows)
    return a, c


assert resum(text) == (70153, 1589365), (
    "current Totals-table re-sum: %d / %d" % resum(text))
assert "Real-agent audit 82" not in text, "audit 82 row already present"

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Real-agent audit 81: Pi 1.5.2, earendil-works/pi tag v1.5.2 (`reports/real_agents/pi/summary.json`) | 25 | 650 (25 x 26) |",
     "| Real-agent audit 81: Pi 1.5.2, earendil-works/pi tag v1.5.2 (`reports/real_agents/pi/summary.json`) | 25 | 650 (25 x 26) |\n"
     "| Real-agent audit 82: ForgeCode 2.14.0, tailcallhq/forgecode tag v2.14.0 (`reports/real_agents/forgecode/summary.json`) | 25 | 650 (25 x 26) |", 1),
    ("| **Total** | **70,153** | **1,589,365** |",
     "| **Total** | **70,178** | **1,590,015** |", 1),
    ("round 240: 1,589,365, 589,365 past target.)",
     "round 240: 1,589,365, 589,365 past target; "
     "audit 82 (ForgeCode): 1,590,015, 590,015 past target.)", 1),
]
for old, new, expected in EDITS:
    count = text.count(old)
    assert count == expected, (
        "edit %r: expected %d, found %d" % (old[:60], expected, count)
    )
    text = text.replace(old, new)

assert resum(text) == (70178, 1590015), (
    "edited Totals-table re-sum: %d / %d" % resum(text))

with open(DS, "w", encoding="utf-8") as h:
    h.write(text)
print("folded audit 82: Totals now 70,178 / 1,590,015")
