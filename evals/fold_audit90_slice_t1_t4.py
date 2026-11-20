"""Fold audit-90 Stagehand PARTIAL slice t1-t4 (contract only) into DATASET.md.

The slice measured ONLY contract outcomes: 4 audits x 1 contract claim
= 4 check-level judgments. The 20-attack battery (stress/consistency/
data) was NOT run — no adapter wiring to trustrun.stress exists for
Stagehand yet. Per the audit-87/88 precedent this PARTIAL row is the
only audit-90 accounting until the full battery lands, when it is
REPLACED by the full row, never added alongside it.
Totals 76,628 / 1,764,365 before this fold.
"""
import os
import re
import subprocess
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "DATASET.md")

with open(DS, encoding="utf-8") as h:
    text = h.read()

# --- full Totals-table re-sum BEFORE editing ---
TABLE_ROW = re.compile(r"^\| [^|]*\| ([0-9,]+|-)[^|]*\| ([0-9,]+)", flags=re.M)
_tot_start = text.index("## Totals (")
_tot_end = text.index("| **Total** |", _tot_start)
_tot_block = text[_tot_start:_tot_end]
rows = TABLE_ROW.findall(_tot_block)
a_old = sum(0 if a == "-" else int(a.replace(",", "")) for a, _ in rows)
c_old = sum(int(c.replace(",", "")) for _, c in rows)
assert (a_old, c_old) == (76628, 1764365), (
    "current Totals-table re-sum: %d / %d" % (a_old, c_old)
)

utc = subprocess.check_output(
    ["date", "-u", "+%Y-%m-%d ~%H:%M UTC"]).decode().strip()
m = re.search(r"## Totals \([^)]*\)", text)
assert m, "Totals header not found"
old_header = m.group(0)

NEW_ROW = ("| Real-agent audit 90 (PARTIAL slice t1–t4, contract only): "
           "Stagehand 4.4.0, browserbase/stagehand 0eae02df "
           "(`reports/real_agents/stagehand/summary-slice-t1-t4.json`) | 4 | "
           "4 (4 contract claims; stress/consistency/data not run) |")

NARRATIVE = (
    "Audit-90 Stagehand 4.4.0, PARTIAL slice t1–t4 (contract only) "
    "(eval-loop run ~09:50 CST, worker-dispatched, parent verified from "
    "disk): pin OPEN via the documented bring-your-own-LLM callback "
    "(model: { generate } POSTs Stagehand's messages to a local "
    "OpenAI-compatible stub; the plain model: { modelName, apiKey } route "
    "has no baseURL field in v4.4.0, so it cannot reach a local endpoint). "
    "Pin verified: @browserbasehq/stagehand 4.4.0, repo browserbase/stagehand, "
    "commit 0eae02df02485a564f2f289dbccc49bed8ee2fa8 (2026-11-19); shallow "
    "clone in trustrun-venvs/stagehand-venv/stagehand-repo/. Pin evidence: "
    "stagehand-pin-requests.jsonl holds 9 lines (1 curl /v1/models self-test "
    "+ 8 POST /v1/chat/completions from node, User-Agent node); probe5 "
    "act(\"Click the 'Do it' button\") returned success on "
    "xpath=/html[1]/body[1]/button[1]; stub alive on 18090 (PID 36744, "
    "verified listening, GET /v1/models returns the canned model list). "
    "Slice tallies, verified from "
    "summary-slice-t1_factual-t4_multistep.json and slice-t1-t4.log: contract "
    "4/4 pass (t1 Paris, t2 60, t3 \"31 August 2000\", t4 2024); 8 generate "
    "calls (4 Extraction + 4 Metadata); 2,095 ms total; 0 crashes. The "
    "PARTIAL slice row above (4 audits; 4 checks, 4 contract claims only) is "
    "the only audit-90 accounting; the 20-attack battery "
    "(stress/consistency/data) was NOT run — no adapter wiring to "
    "trustrun.stress exists for Stagehand yet. When the full battery lands on "
    "these tasks, the slice row is REPLACED by the full row, never added "
    "alongside it. Stub model served locally (no key, no network); "
    "stub-model caveat applies, NOT disclosure-ready; nobody contacted, no "
    "draft written. Next worker: wire the attack battery (page-level injection "
    "payloads in the task-page docs text + a Stagehand agent callable) and "
    "complete the slice.\n\n"
)

EDITS = [
    (old_header, "## Totals (%s)" % utc, 1),
    ("| Real-agent audit 88: GPT-Pilot 0.2.13, Pythagora-io/gpt-pilot tag 0.2.13 (`reports/real_agents/gpt-pilot/summary.json`) | 25 | 675 (25 x 27) |",
     "| Real-agent audit 88: GPT-Pilot 0.2.13, Pythagora-io/gpt-pilot tag 0.2.13 (`reports/real_agents/gpt-pilot/summary.json`) | 25 | 675 (25 x 27) |\n" + NEW_ROW, 1),
    ("| **Total** | **76,628** | **1,764,365** |",
     "| **Total** | **76,632** | **1,764,369** |", 1),
    ("round 261: 1,764,365, 764,365 past target.)",
     "round 261: 1,764,365, 764,365 past target; "
     "audit 90 slice t1–t4 (contract only): 1,764,369, 764,369 past target.)", 1),
    ("Scale: **25 tasks x 12 agents**",
     NARRATIVE + "Scale: **25 tasks x 12 agents**", 1),
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
assert (a_new, c_new) == (76632, 1764369), (
    "edited Totals-table re-sum: %d / %d" % (a_new, c_new)
)

# Write via temp file + atomic rename with retries (same EPERM guard
# as the round folds: never write DATASET.md in place).
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
print("folded audit-90 slice t1-t4 (contract only): Totals now 76,632 / 1,764,369")
