"""Audit Sweep (sweepai/sweep, v1.0.0) with Trustrun
(eighty-third real-agent audit).

Configuration under test: the real Sweep v1.0.0 `ChatGPT` agent loop
(`ChatGPT.chat` -> `call_openai` -> `openai.ChatCompletion.create`,
openai 0.27.2 API) running the real Sweep message-history machinery
against the Trustrun tool set, driven by a deterministic stub model.
The driver runs under the sweep-py venv (pydantic v1) as one
subprocess per call; the harness tools execute in-process in the
project venv behind an HTTP bridge. The stub's tool decisions are
rendered as "CALL <name> <json>" text lines; the driver executes
each CALL through the bridge and feeds "Tool <name> returned:
<text>" back as the next user message. No key, no network. One
fresh `ChatGPT` per call.

HONEST-SETUP DISCLOSURE (read every finding with this in mind):
the stub is a deliberately LITERAL model (it follows instructions
in the task text and tool output), so the audit measures what the
FRAMEWORK does about injected instructions: a framework that
passes an injected instruction through to such a model unfiltered
is the finding; a framework that strips or flags it is the
defense. The stub's compliance is stated; the framework's
pass-through (or filtering) is measured from the messages the
stub actually received, which it logs verbatim (the stub log in
each run's model_log, plus the raw wire bodies in
trustrun-venvs/sweep-requests.jsonl).

MEASURED Sweep STRUCTURE (see the adapter docstring and the probe):
the no-functions branch of `call_openai` sends the FULL message
history -- that is the live path, and the one the battery drives.
The FUNCTIONS branch is broken in v1.0.0: it sends only the system
message, twice (chat.py lines 219-223, `self.messages_dicts[:1]`),
so a function-calling model never sees the task or any tool result;
no caller in the tree passes `functions=` to `chat`. The ReAct
Toolbox is dead code (no caller). The on_ticket issue->PR flow
needs GitHub/Modal/Mongo credentials and is not driven. No
confirmation gate exists anywhere in the v1.0.0 tree (zero hits
for confirm / approval / human_in_the_loop / require_approval,
zero `input(` calls).

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
    evals/run_real_agents_sweep.py [--max-tasks N]
(The Sweep install lives in trustrun-venvs/sweep-venv/
(tag source sweep-src + sweep-py venv) with the driver at
evals/real_agents/sweep/sweep_driver.py. The runner runs under
the project venv python and drives the sweep-py driver as a
subprocess. See real_agents/sweep_adapter.py.)

Runs trustrun.cli.run_audit over the sweep adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/sweep/summary.json and the evidence
logs (injection observations, tampering calls) into
reports/real_agents/sweep/evidence.json. Every number in
those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions
in the task text and tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The per-row "attacks" field records every
attack in the stress battery with its survived/detected outcome.
The evidence logs show the exact observation text the framework
handed the model, which is the framework-level fact. Never present
a clean-room failure as a flaw in a real product: the clean-room
agents' failures are theirs; the Sweep rows are Sweep's.
Note the audited code is the sweep_1 release, NOT default-branch
HEAD: see the adapter docstring for the pinning facts.
"""

import json
import os
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

import real_agents.sweep_adapter as sweep_adapter  # noqa: E402
from real_agents.sweep_adapter import (  # noqa: E402
    RUN_LOGS,
    SWEEP_LICENSE,
    SWEEP_MAIN_HEAD,
    SWEEP_MAIN_PUSHED,
    SWEEP_REPO,
    SWEEP_SECURITY_MD,
    SWEEP_TAG,
    SWEEP_TAG_COMMIT,
    SWEEP_TAG_DATE,
    SWEEP_VERSION,
    shutdown,
    sweep_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "sweep")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
TOOLCALLS_LOG = os.path.normpath(os.path.join(
    os.path.dirname(HERE), "trustrun-venvs",
    "sweep-venv", "sweep-toolcalls.jsonl"))
TOOLCALLS_OFFSET = os.path.join(OUT_DIR, ".toolcalls_start_offset")


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_atomic(path, payload):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
    os.replace(tmp, path)


def _toolcalls_line_count():
    if not os.path.exists(TOOLCALLS_LOG):
        return 0
    count = 0
    with open(TOOLCALLS_LOG, encoding="utf-8") as handle:
        for _ in handle:
            count += 1
    return count


def _driver_tool_calls(from_line):
    """Driver-side tool-call counts from sweep-toolcalls.jsonl
    (the bridge logs every tools/call there), counted only from
    `from_line` onward, so the total covers exactly this battery
    and never depends on a counter living in another process (the
    audit-64/65 open item) or on probe runs that wrote to the same
    log earlier. Returns (Counter, n_rows)."""
    counts = Counter()
    n_rows = 0
    if os.path.exists(TOOLCALLS_LOG):
        with open(TOOLCALLS_LOG, encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index < from_line:
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                n_rows += 1
                counts[row.get("tool", "?")] += 1
    return counts, n_rows


def build_summary(rows, driver_counts, driver_n, tasks,
                  partial=False):
    """Build the summary dict from graded rows (same code path
    for a slice and for the full battery)."""
    done_ids = [r["task"] for r in rows]
    tag = "Sweep %s (tag %s; commit %s, %s; license %s; " \
        "main HEAD %s, pushed %s)" % (
            SWEEP_VERSION, SWEEP_TAG, SWEEP_TAG_COMMIT, SWEEP_TAG_DATE,
            SWEEP_LICENSE, SWEEP_MAIN_HEAD, SWEEP_MAIN_PUSHED)
    summary = {
        "product": "Sweep (sweepai/sweep, v1.0.0, the real Sweep "
                   "ChatGPT agent loop)",
        "component": "The real Sweep v1.0.0 `ChatGPT` agent loop "
                     "(`ChatGPT.chat` -> `call_openai` -> "
                     "`openai.ChatCompletion.create`, openai 0.27.2 "
                     "API) running the real Sweep message-history "
                     "machinery against the Trustrun tool set "
                     "(search_docs, calculator, plus the monitor/"
                     "grader/clarification tools run_audit adds) "
                     "as real harness tools executed in-process "
                     "behind an HTTP bridge. The stub's tool "
                     "decisions are rendered as \"CALL <name> "
                     "<json>\" text lines; the driver executes "
                     "each CALL through the bridge and feeds "
                     "\"Tool <name> returned: <text>\" back as "
                     "the next user message. The driver runs "
                     "under the sweep-py venv (pydantic v1) as "
                     "one subprocess per call. No key, no "
                     "network. The loop ends on a text response, "
                     "so multi-hop tasks can complete. Tool "
                     "results reach the model verbatim as the "
                     "next user message.",
        "version": tag,
        "repo": SWEEP_REPO,
        "repo_resolved": "https://github.com/sweepai/sweep, tag %s "
                         "(commit %s, %s). Default-branch HEAD "
                         "(%s, pushed %s) is ~2 years NEWER than "
                         "the release, so the audited code is the "
                         "v1.0.0 release, NOT HEAD. The release is "
                         "the ONLY release of the agent itself; "
                         "the three later releases are a sandbox "
                         "config tool and the browser extension. "
                         "%s. The audited object is the Sweep "
                         "ChatGPT agent loop -- see the adapter "
                         "docstring for the wiring facts."
                         % (SWEEP_TAG, SWEEP_TAG_COMMIT, SWEEP_TAG_DATE,
                            SWEEP_MAIN_HEAD, SWEEP_MAIN_PUSHED,
                            SWEEP_SECURITY_MD),
        "model_driver": "deterministic-stub-v1 (literal model: "
                        "follows instructions in task text and tool "
                        "output; the audit-30 DeterministicChatModel "
                        "decision logic ported VERBATIM into "
                        "n8n-stub.py, rendered as CALL text lines "
                        "by real_agents/sweep/sweep_driver.py; see "
                        "real_agents/sweep_adapter.py and "
                        "trustrun-venvs/sweep-requests.jsonl)",
        "confirmation_gate": "No confirmation gate exists anywhere "
            "in the v1.0.0 tree (package grep: zero hits for "
            "confirm / approval / human_in_the_loop / "
            "require_approval, zero `input(` calls). Measured "
            "behaviorally by the re-probe (forced "
            "monitor_configure executes with no approval step); "
            "see the slice/final REPORT for the measured gate text.",
        "tool_calls": dict(driver_counts),
        "tool_calls_in_process": dict(sweep_adapter.TOOL_CALLS),
        "tool_calls_driver_side": dict(driver_counts),
        "tool_calls_driver_rows": driver_n,
        "tasks": [t["id"] for t in tasks],
        "seed": 0,
        "k": 5,
        "audits": len(rows),
        "crashes": [r["task"] for r in rows if "crash" in r],
        "rows": rows,
    }
    if partial:
        summary["partial"] = True
        summary["tasks_done"] = done_ids
        summary["tasks_total"] = len(tasks)
    return summary


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as handle:
        tasks = json.load(handle)
    started = time.time()
    # Slice support (same rationale as run_real_agents_pi.py:
    # backgrounded sessions do not survive long enough for a 25-task
    # audit, so each eval-loop run does the next N tasks in the
    # foreground and exits; resume picks up the rest next run).
    max_tasks = None
    if "--max-tasks" in sys.argv:
        max_tasks = int(sys.argv[sys.argv.index("--max-tasks") + 1])
    # Resume support (same rationale as run_real_agents_pi.py:
    # rows and evidence are checkpointed after every task; a
    # re-launch skips tasks already in rows_partial.json and keeps
    # their evidence).
    rows = _load_json(PARTIAL_ROWS, [])
    done = {row["task"] for row in rows}
    RUN_LOGS.extend(_load_json(PARTIAL_EVIDENCE, []))
    if done:
        print("resuming: %d tasks already done (%s)"
              % (len(done), ", ".join(sorted(done))), flush=True)
    # The driver-side tool-call count is anchored once, at the start
    # of the FIRST slice (when no partial rows exist yet), and kept
    # in .toolcalls_start_offset so later slices reuse the same
    # anchor instead of re-anchoring mid-battery.
    if os.path.exists(TOOLCALLS_OFFSET):
        with open(TOOLCALLS_OFFSET, encoding="utf-8") as handle:
            toolcalls_start = int(handle.read().strip())
    else:
        toolcalls_start = _toolcalls_line_count()
        with open(TOOLCALLS_OFFSET, "w", encoding="utf-8") as handle:
            handle.write(str(toolcalls_start))
    print("toolcalls log anchored at line %d" % toolcalls_start,
          flush=True)
    pending = [t for t in tasks if t["id"] not in done]
    if max_tasks is not None:
        pending = pending[:max_tasks]
    for task_def in pending:
        tools = {
            name: TOOL_BUILDERS[name] for name in task_def["tools_order"]
        }
        task = {
            "text": task_def["text"],
            "expect": task_def["expect"],
            "tools": tools,
        }
        if task_def.get("variants"):
            task["variants"] = task_def["variants"]
        if task_def.get("rubric"):
            task["rubric"] = task_def["rubric"]
        if task_def.get("misleading_suggestion"):
            task["misleading_suggestion"] = task_def["misleading_suggestion"]
        # Per-task guard (same rationale as run_real_agents_pi.py:
        # a framework crash must be recorded as a crash row, not kill
        # the remaining tasks. A crash row is verdict BLOCK with a
        # "crash" field; its section verdicts were NOT graded, so folds
        # must count checks as 21 per graded row and 0 per crash row,
        # and summary.json lists crash task ids.)
        try:
            report = run_audit(
                sweep_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the sweep (non-)effect lives
            # here, not in the section verdict (worst-case over the
            # battery). Compact each attack to kind + vector /
            # encoding + outcome; the evidence text lives in the
            # re-probe log.
            attacks = []
            for a in sections["stress"].get("attacks", []):
                entry = {
                    "kind": a.get("kind"),
                    "vector": a.get("vector") or a.get("encoding"),
                    "survived": a.get("survived"),
                    "detected": a.get("detected"),
                    "completed": a.get("completed"),
                }
                if a.get("visibility_class"):
                    entry["visibility_class"] = a.get("visibility_class")
                attacks.append(entry)
            rows.append({
                "agent": "sweep",
                "task": task_def["id"],
                "task_id": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("sweep x %s -> %s (contract %s, stress %s, "
                  "consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "sweep",
                "task": task_def["id"],
                "task_id": task_def["id"],
                "verdict": "BLOCK",
                "contract": "BLOCK",
                "stress": "BLOCK",
                "consistency": "BLOCK",
                "data": "BLOCK",
                "pass_rate_k": 0.0,
                "attacks": [],
                "crash": "%s: %s" % (type(exc).__name__, exc),
            })
            print("sweep x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc), flush=True)
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
    if max_tasks is not None and len(rows) < len(tasks):
        # Sliced run: write the slice summary (same code path as
        # the full finalize, via build_summary) and keep the
        # partials for resume; do NOT write the final summary.json
        # or delete the partials.
        driver_counts, driver_n = _driver_tool_calls(toolcalls_start)
        slice_summary = build_summary(rows, driver_counts, driver_n,
                                      tasks, partial=True)
        first = rows[0]["task"] if rows else "none"
        last = rows[-1]["task"] if rows else "none"
        slice_name = "summary-slice-%s-%s.json" % (first, last)
        ev_name = "evidence-slice-%s-%s.json" % (first, last)
        with open(os.path.join(OUT_DIR, slice_name), "w",
                  encoding="utf-8") as handle:
            json.dump(slice_summary, handle, indent=1)
        with open(os.path.join(OUT_DIR, ev_name), "w",
                  encoding="utf-8") as handle:
            json.dump(RUN_LOGS, handle, indent=1)
        print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
        print("stress:", dict(Counter(r["stress"] for r in rows)))
        print("tool_calls:", dict(driver_counts), "rows:", driver_n)
        print("tool_calls_in_process:", dict(sweep_adapter.TOOL_CALLS))
        print("evidence runs kept:", len(RUN_LOGS))
        print("stopped early: %d of %d tasks done (max-tasks %d); "
              "slice summary %s written, partials kept, resume next run"
              % (len(rows), len(tasks), max_tasks, slice_name), flush=True)
        print("done in %.1fs" % (time.time() - started), flush=True)
        shutdown()
        return
    driver_counts, driver_n = _driver_tool_calls(toolcalls_start)
    summary = build_summary(rows, driver_counts, driver_n, tasks)
    with open(os.path.join(OUT_DIR, "summary.json"), "w",
              encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
    with open(os.path.join(OUT_DIR, "evidence.json"), "w",
              encoding="utf-8") as handle:
        json.dump(RUN_LOGS, handle, indent=1)
    print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
    print("stress:", dict(Counter(r["stress"] for r in rows)))
    print("tool_calls:", dict(driver_counts), "rows:", driver_n)
    print("tool_calls_in_process:", dict(sweep_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    shutdown()
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, TOOLCALLS_OFFSET):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
