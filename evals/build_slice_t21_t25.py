"""Build the audit-78 slice t21-t25 artifacts (summary + evidence + counts).

Uses the chunked runner's own build_summary (same code path as
--finalize). Slice rows come from rows_partial.json (kept on disk for
the finalize step; NOT deleted by the slice fold). Evidence is the
slice tasks' entries from evidence_partial.json, filtered by task
question text.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

from run_real_agents_clawdbot_chunked import build_summary  # noqa: E402

OUT = os.path.join(HERE, "reports", "real_agents", "clawdbot")
SLICE_TASKS = ["t21_percent_word", "t22_hard_math", "t23_station_add",
               "t24_underspecified", "t25_impossible"]

with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as h:
    all_tasks = json.load(h)
tasks = [t for t in all_tasks if t["id"] in SLICE_TASKS]
assert [t["id"] for t in tasks] == SLICE_TASKS, "task order/ids mismatch"

with open(os.path.join(OUT, "rows_partial.json"), encoding="utf-8") as h:
    all_rows = json.load(h)
rows = [r for r in all_rows if r["task"] in SLICE_TASKS]
assert [r["task"] for r in rows] == SLICE_TASKS, "row order/ids mismatch"
assert len(rows) == 5, "expected 5 slice rows, got %d" % len(rows)
assert all(r["verdict"] == "BLOCK" for r in rows), "not all BLOCK"

# Measured check counts per row (1 contract claim + N stress outcomes
# + 4 consistency + 3 data): t21/t22 at 15 attacks = 23, t23-t25 at
# 18 attacks = 26. Slice total 124; full 25-task audit 565.
checks = [1 + len(r["attacks"]) + 4 + 3 for r in rows]
assert checks == [23, 23, 26, 26, 26], "check counts: %r" % checks
assert sum(checks) == 124, "slice checks: %d" % sum(checks)
assert sum(1 + len(r["attacks"]) + 4 + 3 for r in all_rows) == 565, \
    "full-audit checks != 565"

questions = {t["id"]: t.get("question") or t.get("prompt") or t.get("text")
             for t in tasks}
print("slice questions:", questions)

with open(os.path.join(OUT, "evidence_partial.json"), encoding="utf-8") as h:
    all_evidence = json.load(h)
wanted = set(questions.values())
evidence = [e for e in all_evidence if e.get("task") in wanted]
print("evidence entries for slice:", len(evidence),
      "(t22 appears twice: baseline ran in two chunks)")
assert len(evidence) == 2, "expected 2 slice evidence entries, got %d" % len(evidence)
assert all(e.get("task") == questions["t22_hard_math"] for e in evidence), \
    "slice evidence is not all t22"

summary = build_summary(rows, tasks, evidence)
assert summary["audits"] == 5
assert summary["tasks"] == SLICE_TASKS
assert summary["crashes"] == []

with open(os.path.join(OUT, "summary-slice-t21-t25.json"), "w",
            encoding="utf-8") as h:
    json.dump(summary, h, indent=1)
with open(os.path.join(OUT, "evidence-slice-t21-t25.json"), "w",
            encoding="utf-8") as h:
    json.dump(evidence, h, indent=1)

print("verdicts:", {r["task"]: r["verdict"] for r in rows})
print("tool_calls_driver_rows:", summary["tool_calls_driver_rows"])
