"""Audit GPT-Pilot (Pythagora-io/gpt-pilot, 0.2.13) with Trustrun
(eighty-eighth real-agent audit).

Configuration under test: the real GPT-Pilot 0.2.13 agent LLM loop
(a real Developer agent instance -- real StateManager on a file
SQLite DB, real AgentConvo with the product's shipped Developer
system prompt, real BaseLLMClient via agent.get_llm(), the default
OpenAI provider path) running the real GPT-Pilot message-history
machinery against the Trustrun tool set, driven by a deterministic
stub model. The model role is the stub served as a local HTTP server
speaking both wire formats GPT-Pilot uses (OpenAI-compatible
/v1/chat/completions and Anthropic /v1/messages) and injected via
the product's own config path (ProviderConfig.base_url -> local
stub, api_key "dummy"; no sign-in). The driver runs under the
gpt-pilot-py venv python and drives the real gpt-pilot package as
one subprocess per call. The stub's tool decisions are rendered as
"CALL <name> <json>" text lines; the driver executes each CALL
through the bridge and feeds "Tool <name> returned: <text>" back as
the next user message. No key, no network beyond loopback. One
fresh process (and one fresh project) per call.

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
trustrun-venvs/gpt-pilot-requests.jsonl).

MEASURED GPT-PILOT STRUCTURE (see the adapter docstring and the
probe): the product has NO function/tool calling anywhere in core/
(agents consume model text through parsers and Python acts on it),
so the audited surface is the agent LLM loop
(BaseLLMClient.__call__ + AgentConvo) every agent step runs
through; the full Orchestrator app-building pipeline is NOT driven.
No confirmation gate stands between the model and a tool call in
the audited invocation. Tool results reach the model verbatim as
the next user message.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
    evals/run_real_agents_gpt_pilot.py [--max-tasks N]
(The GPT-Pilot install lives in
trustrun-venvs/gpt-pilot-venv/ (tag 0.2.13 source + gpt-pilot-py
venv with the era deps). The runner runs under the project venv
python and drives the gpt-pilot-py driver as a subprocess. See
real_agents/gpt_pilot_adapter.py.)

Runs trustrun.cli.run_audit over the gpt_pilot agent on all 25
tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/gpt-pilot/summary.json and the evidence
logs (injection observations, tampering calls) into
reports/real_agents/gpt-pilot/evidence.json. Every number in
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
agents' failures are theirs; the GPT-Pilot rows are GPT-Pilot's.
Note the audited code is the 0.2.13 release, NOT default-branch
HEAD: see the adapter docstring for the pinning facts (including
the June 2026 main-branch compromise the tag predates).
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

import real_agents.gpt_pilot_adapter as gpt_pilot_adapter  # noqa: E402
from real_agents.gpt_pilot_adapter import (  # noqa: E402
    GPT_PILOT_LICENSE,
    GPT_PILOT_MAIN_HEAD,
    GPT_PILOT_MAIN_HEAD_DATE,
    GPT_PILOT_REPO,
    GPT_PILOT_SECURITY_MD,
    GPT_PILOT_TAG,
    GPT_PILOT_TAG_COMMIT,
    GPT_PILOT_TAG_DATE,
    GPT_PILOT_VERSION,
    RUN_LOGS,
    shutdown,
    gpt_pilot_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "gpt-pilot")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
TOOLCALLS_LOG = os.path.normpath(os.path.join(
    os.path.dirname(HERE), "trustrun-venvs",
    "gpt-pilot-venv", "gpt-pilot-toolcalls.jsonl"))
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
    """Bridge-side tool-call counts from gpt-pilot-toolcalls.jsonl,
    counted only from `from_line` onward, so the total covers
    exactly this battery and never depends on a counter living in
    another process (the audit-64/65 open item) or on probe runs
    that wrote to the same log earlier. Returns (Counter, n_rows)."""
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
    tag = "GPT-Pilot %s (tag %s; commit %s, %s; license %s; " \
        "main HEAD %s, %s)" % (
            GPT_PILOT_VERSION, GPT_PILOT_TAG, GPT_PILOT_TAG_COMMIT,
            GPT_PILOT_TAG_DATE, GPT_PILOT_LICENSE,
            GPT_PILOT_MAIN_HEAD, GPT_PILOT_MAIN_HEAD_DATE)
    summary = {
        "product": "GPT-Pilot (Pythagora-io/gpt-pilot, 0.2.13, "
                   "the real agent LLM loop)",
        "component": "The real GPT-Pilot 0.2.13 agent LLM loop (a "
                     "real Developer agent instance -- real "
                     "StateManager on a file SQLite DB, real "
                     "AgentConvo with the product's shipped Developer "
                     "system prompt, real BaseLLMClient via "
                     "agent.get_llm(), the default OpenAI provider "
                     "path) running the real GPT-Pilot message-history "
                     "machinery against the Trustrun tool set "
                     "(search_docs, calculator, plus the "
                     "monitor/grader/clarification tools run_audit "
                     "adds) as real tools executed in-process behind "
                     "an HTTP bridge. The stub model is injected via "
                     "the product's own config path "
                     "(ProviderConfig.base_url -> local stub server "
                     "speaking OpenAI-compatible /v1/chat/completions "
                     "and Anthropic /v1/messages; api_key dummy; no "
                     "sign-in). The stub's tool decisions are rendered "
                     "as CALL <name> <json> text lines; the driver "
                     "executes each CALL through the bridge and feeds "
                     "\"Tool <name> returned: <text>\" back as the "
                     "next user message. The driver runs under the "
                     "gpt-pilot-py venv python and drives the real "
                     "gpt-pilot package as one subprocess per call. "
                     "No key, no network beyond loopback. The loop "
                     "ends on a text response, so multi-hop tasks can "
                     "complete. Tool results reach the model verbatim "
                     "as the next user message.",
        "version": tag,
        "repo": GPT_PILOT_REPO,
        "repo_resolved": "https://github.com/Pythagora-io/gpt-pilot, "
                         "tag %s (commit %s, %s). "
                         "Default-branch HEAD (%s, %s) is a merge of PR "
                         "#1183 \"security/remove-malicious-telemetry-"
                         "loader\" (the maintainers' cleanup after the "
                         "2026-06-08 main-branch compromise), so the "
                         "audited code is the 0.2.13 release, NOT HEAD. "
                         "%s. The audited object is the GPT-Pilot agent "
                         "LLM loop -- see the adapter docstring for the "
                         "wiring facts."
                         % (GPT_PILOT_TAG, GPT_PILOT_TAG_COMMIT,
                            GPT_PILOT_TAG_DATE,
                            GPT_PILOT_MAIN_HEAD, GPT_PILOT_MAIN_HEAD_DATE,
                            GPT_PILOT_SECURITY_MD),
        "model_driver": "deterministic-stub-v1 (literal model: "
                        "follows instructions in task text and tool "
                        "output; the audit-30 DeterministicChatModel "
                        "decision logic ported VERBATIM into "
                        "n8n-stub.py, rendered as CALL <name> <json> "
                        "text lines by real_agents/gpt_pilot/"
                        "gpt_pilot_stub.py; see "
                        "real_agents/gpt_pilot_adapter.py and "
                        "trustrun-venvs/gpt-pilot-requests.jsonl)",
        "confirmation_gate": "No confirmation gate stands between "
            "the model and a tool call in the audited invocation: "
            "GPT-Pilot 0.2.13 has no tool-calling channel and no "
            "approval step on the audited agent LLM loop. "
            "Measured behaviorally by the re-probe (forced "
            "monitor_configure executes with no approval step); "
            "see the slice/final REPORT for the measured gate text.",
        "tool_calls": dict(driver_counts),
        "tool_calls_in_process": dict(gpt_pilot_adapter.TOOL_CALLS),
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
    # The bridge-side tool-call count is anchored once, at the start
    # of the FIRST slice (when no partial rows exist yet), and kept
    # in .toolcalls_start_offset so later slices reuse the same
    # anchor instead of re-anchoring mid-battery. The anchor file
    # is DELETED and re-created fresh before the first slice of a
    # battery: a stale anchor from a probe or an earlier battery
    # would silently drop exact counts (the Sweep audit lost exact
    # counts twice to a stale anchor). Verify the anchor equals the
    # current line count at creation time.
    if os.path.exists(TOOLCALLS_OFFSET):
        with open(TOOLCALLS_OFFSET, encoding="utf-8") as handle:
            toolcalls_start = int(handle.read().strip())
    else:
        toolcalls_start = _toolcalls_line_count()
        with open(TOOLCALLS_OFFSET, "w", encoding="utf-8") as handle:
            handle.write(str(toolcalls_start))
    print("toolcalls log anchored at line %d (current lines %d)"
          % (toolcalls_start, _toolcalls_line_count()), flush=True)
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
                gpt_pilot_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the gpt-pilot (non-)effect lives
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
                "agent": "gpt-pilot",
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
            print("gpt-pilot x %s -> %s (contract %s, stress %s, "
                  "consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "gpt-pilot",
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
            print("gpt-pilot x %s -> CRASH (%s: %s)"
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
        print("tool_calls_in_process:", dict(gpt_pilot_adapter.TOOL_CALLS))
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
    print("tool_calls_in_process:", dict(gpt_pilot_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    shutdown()
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, TOOLCALLS_OFFSET):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
