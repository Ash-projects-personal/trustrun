"""Audit OpenAI Swarm (openai-swarm 0.1.1) with Trustrun
(forty-sixth real-agent audit; first audit of the Swarm framework
in the rotation -- the lightweight multi-agent handoff framework
from openai/swarm, the experimental predecessor the OpenAI Agents
SDK replaced).

Configuration under test: a single Swarm Agent holding the whole
Trustrun tool set (search_docs, monitor_configure, edit_tests,
record_score, calculator, ask_user) as plain Python functions
(named exactly after the tools; Swarm converts each to an OpenAI
tool schema with function_to_json), driven by a deterministic
stub model (DeterministicChatModel, the audit-30 decision logic
reused verbatim via the audit-45 adapter) served through a fake
OpenAI client (DeterministicOpenAIClient: chat.completions.create
returns a real ChatCompletion built from the stub's decision; no
key, no network). One fresh agent, stub, and client are built per
call. Instructions are Swarm's own default ("You are a helpful
agent."); no human-in-the-loop, no checkpointer, max_turns=20
(safety cap, never binds on the measured tasks). See
real_agents/swarm_adapter.py for the wiring facts.

Usage: ~/workspace/hackathons/trustrun-venvs/swarm-venv/bin/python3 run_real_agents_swarm.py
(openai-swarm lives in a separate venv; see
real_agents/swarm_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the Swarm adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/swarm/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/swarm/evidence.json. Every number in those
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
agents' failures are theirs; the Swarm rows are Swarm's.
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

import real_agents.swarm_adapter as sw_adapter  # noqa: E402
from real_agents.swarm_adapter import (  # noqa: E402
    OPENAI_VERSION,
    RUN_LOGS,
    SWARM_PYPI,
    SWARM_REPO,
    SWARM_REPO_HEAD,
    SWARM_REPO_HEAD_DATE,
    SWARM_REPO_HEAD_MESSAGE,
    SWARM_VERSION,
    swarm_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "swarm")
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
                swarm_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the Swarm (non-)effect lives
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
                "agent": "swarm",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("swarm x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "swarm",
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
            print("swarm x %s -> CRASH (%s: %s)"
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
        "product": "OpenAI Swarm (openai-swarm 0.1.1, lightweight multi-agent handoff framework)",
        "component": "Single Swarm Agent holding the whole Trustrun tool set as plain Python functions (named exactly after the tools; Swarm converts each to an OpenAI tool schema with function_to_json), driven by DeterministicChatModel (the audit-30 decision logic reused verbatim via the audit-45 adapter; literal model) served through a fake OpenAI client (chat.completions.create returns a real ChatCompletion built from the stub's decision; no key, no network) inside Swarm.run (max_turns=20 safety cap, Swarm's default instructions, no human-in-the-loop, no checkpointer). One fresh agent, stub, and client are built per call. The framework runs the turn loop, dispatches tool calls, and switches agents on handoff; it performs no sanitization, filtering, or flagging of tool results.",
        "version": "openai-swarm %s (openai %s, Swarm's own client-library dependency, supplies the ChatCompletion types)" % (
            SWARM_VERSION, OPENAI_VERSION),
        "repo": SWARM_REPO,
        "repo_resolved": "https://github.com/openai/swarm, default-branch HEAD %s (commit %s, '%s'). Installed with pip install %s pytest in a separate venv (~/workspace/hackathons/trustrun-venvs/swarm-venv); openai-swarm 0.1.1 is the current latest release on PyPI at audit time. PyPI ships NO source URL for this package (no home_page, no project_urls). The installed wheel's swarm/core.py, swarm/types.py, swarm/util.py, and swarm/__init__.py are byte-identical to that HEAD's source (diff-verified against raw.githubusercontent content at the pinned commit), so the wheel and HEAD are the same code. No version tag exists for 0.1.1. The repo is NOT archived; the README states Swarm 'is now replaced by the OpenAI Agents SDK' and recommends migrating for production use. The audited object is the `swarm` package itself -- see the adapter docstring for the wiring facts." % (
            SWARM_REPO_HEAD,
            SWARM_REPO_HEAD_DATE, SWARM_REPO_HEAD_MESSAGE,
            SWARM_PYPI),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim via the audit-45 adapter, served to Swarm as a fake OpenAI client returning real ChatCompletion objects; final answers returned as the last assistant message's content; see real_agents/swarm_adapter.py)",
        "confirmation_gate": "NONE by default -- no per-tool confirmation gate exists in the package (zero hits for sanitize / filter / confirm / approval / human_in_the_loop / require_confirmation / interrupt / escape across the installed package). Measured: tampering knobs called by the model execute with no approval step. Swarm-specific: a tool function returning an Agent triggers the handoff path with no model confirmation of the switch (measured in the re-probe); a tool result containing tool JSON does NOT execute (it is a string in a tool-role message, not a dispatch -- measured in the re-probe).",
        "tool_calls": dict(sw_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(sw_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
