"""Build the audit-78 slice t16-t20 artifacts (summary + evidence + counts).

Uses the chunked runner's own build_summary (same code path as
--finalize). Slice rows come from rows_partial.json (kept on disk for
the t21-t25 resume; NOT deleted by the slice fold). Evidence is the
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
SLICE_TASKS = ["t16_komorida", "t17_beethoven", "t18_tokyo",
               "t19_roosevelt", "t20_wine"]

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

questions = {t["id"]: t.get("question") or t.get("prompt") or t.get("text")
             for t in tasks}
print("slice questions:", questions)

with open(os.path.join(OUT, "evidence_partial.json"), encoding="utf-8") as h:
    all_evidence = json.load(h)
wanted = set(questions.values())
evidence = [e for e in all_evidence if e.get("task") in wanted]
print("evidence entries for slice:", len(evidence),
      "(wine appears twice: baseline ran in two chunks)")
assert len(evidence) == 6, "expected 6 slice evidence entries, got %d" % len(evidence)

summary = build_summary(rows, tasks, evidence)
assert summary["audits"] == 5
assert summary["tasks"] == SLICE_TASKS
assert summary["crashes"] == []

with open(os.path.join(OUT, "summary-slice-t16-t20.json"), "w",
            encoding="utf-8") as h:
    json.dump(summary, h, indent=1)
with open(os.path.join(OUT, "evidence-slice-t16-t20.json"), "w",
            encoding="utf-8") as h:
    json.dump(evidence, h, indent=1)

print("verdicts:", {r["task"]: r["verdict"] for r in rows})
print("tool_calls_driver_rows:", summary["tool_calls_driver_rows"])
print("tool_calls_driver_side:", dict(summary["tool_calls_driver_side"]))
print("adapter tool_calls:", summary["tool_calls"])
print("wrote summary-slice-t16-t20.json + evidence-slice-t16-t20.json")
