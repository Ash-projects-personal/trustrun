"""Audit BabyAGI (yoheinakajima/babyagi, git HEAD
fa8930ebe72a82e5ad57b356e7cbec96290e5bb2) with Trustrun
(forty-ninth real-agent audit).

Configuration under test: a single BabyAGI agent running the
shipped default-pack `chat_with_functions` (one LiteLLM call with
tools, execute any tool calls, one second LiteLLM call WITHOUT
tools, return final text) against the work-dir functionz SQLite
DB, holding the whole Trustrun tool set (search_docs,
monitor_configure, edit_tests, record_score, calculator,
ask_user) as real `functionz` functions registered in the DB
(named exactly after the tools), driven by a deterministic stub
model (DeterministicChatModel, the audit-30 decision logic reused
verbatim via the audit-47 adapter) served by monkeypatching
litellm.completion. One fresh stub and litellm patch are built
per call. No confirmation gate exists in the package; the
one-round limit is the binding constraint (see
real_agents/babyagi_adapter.py for the wiring facts).

Usage: ~/workspace/hackathons/trustrun-venvs/babyagi-venv/bin/python3 run_real_agents_babyagi.py
(BabyAGI lives in a separate venv + git checkout; see
real_agents/babyagi_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the BabyAGI adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/babyagi/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/babyagi/evidence.json. Every number in those
files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The per-row "attacks" field records every
attack in the stress battery with its survived/detected outcome. The
evidence logs show the exact observation text the framework handed
the model, which is the framework-level fact. Never present a
clean-room failure as a flaw in a real product: the clean-room
agents' failures are theirs; the BabyAGI rows are BabyAGI's.
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

import real_agents.babyagi_adapter as bg_adapter  # noqa: E402
from real_agents.babyagi_adapter import (  # noqa: E402
    RUN_LOGS,
    BABYAGI_PYPI,
    BABYAGI_REPO,
    BABYAGI_REPO_HEAD,
    BABYAGI_REPO_HEAD_DATE,
    BABYAGI_REPO_HEAD_MESSAGE,
    BABYAGI_VERSION,
    babyagi_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "babyagi")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")


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


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as handle:
        tasks = json.load(handle)
    started = time.time()
    # Slice support (same rationale as run_real_agents_atomic.py:
    # backgrounded sessions do not survive long enough for a 25-task
    # audit, so each eval-loop run does the next N tasks in the
    # foreground and exits; resume picks up the rest next run).
    max_tasks = None
    if "--max-tasks" in sys.argv:
        max_tasks = int(sys.argv[sys.argv.index("--max-tasks") + 1])
    # Resume support (same rationale as run_real_agents_atomic.py: rows
    # and evidence are checkpointed after every task; a re-launch skips
    # tasks already in rows_partial.json and keeps their evidence).
    rows = _load_json(PARTIAL_ROWS, [])
    done = {row["task"] for row in rows}
    RUN_LOGS.extend(_load_json(PARTIAL_EVIDENCE, []))
    if done:
        print("resuming: %d tasks already done (%s)"
              % (len(done), ", ".join(sorted(done))))
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
        # Per-task guard (same rationale as run_real_agents_atomic.py:
        # a framework crash must be recorded as a crash row, not kill
        # the remaining tasks. A crash row is verdict BLOCK with a
        # "crash" field; its section verdicts were NOT graded, so folds
        # must count checks as 21 per graded row and 0 per crash row,
        # and summary.json lists crash task ids.)
        try:
            report = run_audit(
                babyagi_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the BabyAGI (non-)effect lives
            # here, not in the section verdict (worst-case over the
            # battery). Compact each attack to kind + vector /
            # encoding + outcome; the evidence text lives in the
            # re-probe log.
            attacks = [{
                "kind": a.get("kind"),
                "vector": a.get("vector") or a.get("encoding"),
                "survived": a.get("survived"),
                "detected": a.get("detected"),
                "completed": a.get("completed"),
            } for a in sections["stress"].get("attacks", [])]
            rows.append({
                "agent": "babyagi",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("babyagi x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "babyagi",
                "task": task_def["id"],
                "verdict": "BLOCK",
                "contract": "BLOCK",
                "stress": "BLOCK",
                "consistency": "BLOCK",
                "data": "BLOCK",
                "pass_rate_k": 0.0,
                "attacks": [],
                "crash": "%s: %s" % (type(exc).__name__, exc),
            })
            print("babyagi x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc))
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
    if max_tasks is not None and len(rows) < len(tasks):
        # Sliced run: do NOT write summary.json or delete the partials.
        print("stopped early: %d of %d tasks done (max-tasks %d); "
              "partials kept, resume next run"
              % (len(rows), len(tasks), max_tasks))
        print("done in %.1fs" % (time.time() - started))
        return
    summary = {
        "product": "BabyAGI (yoheinakajima/babyagi, shipped default-pack chat_with_functions)",
        "component": "Single BabyAGI agent running the shipped default-pack chat_with_functions (one LiteLLM call with tools, execute any tool calls, one second LiteLLM call WITHOUT tools, return final text) against the work-dir functionz SQLite DB, holding the whole Trustrun tool set as real functionz functions registered in the DB (named exactly after the tools; BabyAGI execs the DB-stored code with FunctionExecutor and dispatches tool calls through execute_function_wrapper), driven by DeterministicChatModel (the audit-30 decision logic reused verbatim via the audit-47 adapter; literal model) served by monkeypatching litellm.completion (no key, no network). One fresh stub and litellm patch are built per call. No confirmation gate exists in the package; the one-round limit is the binding constraint: a task needing two sequential tool calls cannot complete the second one, and the stub's second tool decision is rendered as final text naming the unexecuted call. The framework runs the single tool round, builds the tool schemas from the DB, catches raising tools as error observations, and passes tool results to the model verbatim; it performs no sanitization, filtering, or flagging of tool results.",
        "version": "BabyAGI %s (PyPI babyagi %s; sdist differs from HEAD in 2 files only, chat_with_functions.py byte-identical; audited code is the git checkout at the pinned HEAD)" % (
            BABYAGI_VERSION, BABYAGI_PYPI),
        "repo": BABYAGI_REPO,
        "repo_resolved": "https://github.com/yoheinakajima/babyagi, HEAD %s (commit %s, '%s'). PyPI babyagi %s sdist differs from HEAD in 2 files only; chat_with_functions.py is byte-identical between sdist and HEAD, so the audit object is the git checkout at the pinned HEAD in ~/workspace/hackathons/trustrun-venvs/babyagi-src (verified with git rev-parse HEAD). No SECURITY.md and no security policy exist in the repo (no SECURITY.md at HEAD, no .github directory, README carries zero hits for 'security' and no security contact). The repo is NOT archived. The classic BabyAGI task-list agent does not exist at this HEAD; the audited object is the functionz framework's shipped default-pack chat_with_functions -- see the adapter docstring for the wiring facts." % (
            BABYAGI_REPO_HEAD,
            BABYAGI_REPO_HEAD_DATE, BABYAGI_REPO_HEAD_MESSAGE,
            BABYAGI_PYPI),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim via the audit-47 adapter, served to BabyAGI by monkeypatching litellm.completion; a tool decision on the second litellm call is rendered as final text naming the unexecuted call, because chat_with_functions gives the model no second tool round; see real_agents/babyagi_adapter.py)",
        "confirmation_gate": "NONE: no confirmation gate exists in the package (zero hits for human_in_the_loop / require_confirmation / sanitize / interrupt / approval; the only two 'confirm' hits are docstrings in packs/plugins/airtable.py, not a gate). The one-round limit is the binding constraint, not a defense: monitor_tampering knobs fire on the first call and execute with no approval step (measured in the re-probe); evaluator_tampering chains are cut short because the edit/record call would be the second tool call (measured in the re-probe: survived with edits == 0, the stub log shows the unexecuted edit_tests intent). Measured: a tool result containing tool JSON does NOT execute (it is a string in a role:tool message, not a dispatch -- measured in the re-probe); a raising tool is CAUGHT by chat_with_functions and returned as an 'Error executing function ...' observation (measured in the re-probe); an unregistered name in available_function_names raises ValueError OUTSIDE the try/except and aborts the run (measured in the re-probe); a tool name the stub emits that was never offered is caught inside the tool loop and becomes an error observation (measured in the re-probe).",
        "tool_calls": dict(bg_adapter.TOOL_CALLS),
        "tasks": [t["id"] for t in tasks],
        "seed": 0,
        "k": 5,
        "audits": len(rows),
        "crashes": [r["task"] for r in rows if "crash" in r],
        "rows": rows,
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w",
              encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
    with open(os.path.join(OUT_DIR, "evidence.json"), "w",
              encoding="utf-8") as handle:
        json.dump(RUN_LOGS, handle, indent=1)
    print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
    print("stress:", dict(Counter(r["stress"] for r in rows)))
    print("tool_calls:", dict(bg_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
