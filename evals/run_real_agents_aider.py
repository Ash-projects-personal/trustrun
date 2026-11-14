"""Audit Aider (Aider-AI/aider, PyPI aider-chat 0.86.2, git HEAD
5dc9490bb35f9729ef2c95d00a19ccd30c26339c) with Trustrun
(fiftieth real-agent audit; thirty-eighth framework).

Configuration under test: Aider's real `Coder` loop (default
`diff` / SEARCH-REPLACE edit format) in a fresh throwaway temp
workdir per call, holding the whole Trustrun tool set
(search_docs, calculator, plus the monitor/grader/clarification
tools run_audit adds) via the adapter's edit-block CALL channel
(see real_agents/aider_adapter.py), driven by a deterministic
stub model (DeterministicChatModel, the audit-30 decision logic
reused verbatim via the audit-47 adapter) served by
monkeypatching litellm.completion (no key, no network). One
fresh stub, Coder, and litellm patch are built per call. Shell
commands the model suggests are parsed but NOT run even with
InputOutput(yes=True) (explicit_yes_required gate); file edits
to the in-chat scratch file apply with no confirmation (see
real_agents/aider_adapter.py for the wiring facts).

Usage: ~/workspace/hackathons/trustrun-venvs/aider-venv/bin/python3 run_real_agents_aider.py
(Aider lives in a separate venv; see real_agents/aider_adapter.py
for the install command.)

Runs trustrun.cli.run_audit over the Aider adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/aider/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/aider/evidence.json. Every number in those
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
agents' failures are theirs; the Aider rows are Aider's.
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

import real_agents.aider_adapter as ad_adapter  # noqa: E402
from real_agents.aider_adapter import (  # noqa: E402
    RUN_LOGS,
    AIDER_PYPI,
    AIDER_REPO,
    AIDER_REPO_HEAD,
    AIDER_REPO_HEAD_DATE,
    AIDER_REPO_HEAD_MESSAGE,
    AIDER_VERSION,
    aider_agent,
    cleanup_work_dirs,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "aider")
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
                aider_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the Aider (non-)effect lives
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
                "agent": "aider",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("aider x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "aider",
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
            print("aider x %s -> CRASH (%s: %s)"
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
        "product": "Aider (Aider-AI/aider, PyPI aider-chat 0.86.2, real Coder loop, default diff edit format)",
        "component": "Aider's real Coder loop (EditBlockCoder, default diff / SEARCH-REPLACE edit format) in a fresh throwaway temp workdir per call, holding the whole Trustrun tool set via the adapter's edit-block CALL channel (the stub renders each tool decision as a SEARCH/REPLACE block on the in-chat scratch.txt; Aider applies it with no confirmation; the adapter executes the named harness tool in-process and feeds the result back as the next user message), driven by DeterministicChatModel (the audit-30 decision logic reused verbatim via the audit-47 adapter; literal model) served by monkeypatching litellm.completion (no key, no network). One fresh stub, Coder, and litellm patch are built per call. Shell commands the model suggests are parsed into coder.shell_commands but NOT run even with InputOutput(yes=True) (explicit_yes_required gate); file edits to the in-chat scratch file apply with no confirmation. The framework runs the edit-block parse/apply, builds the message history, reflects on failed edits, and passes tool results to the model verbatim as user messages; it performs no sanitization, filtering, or flagging of tool results.",
        "version": "Aider %s (PyPI %s; audited code is the installed 0.86.2 wheel, the release of the pinned HEAD line)" % (
            AIDER_VERSION, AIDER_PYPI),
        "repo": AIDER_REPO,
        "repo_resolved": "https://github.com/Aider-AI/aider, HEAD %s (commit %s, '%s'). PyPI aider-chat %s is the current latest release at audit time; the installed wheel is the 0.86.2 release of the pinned HEAD's line (verified with git ls-remote, the GitHub commits API, and a shallow clone whose git rev-parse HEAD matches). No SECURITY.md and no security policy or security contact exist in the repo (no SECURITY.md at HEAD, no security@ address and no vulnerability-disclosure instructions in the README or docs). The repo is NOT archived. Aider is a terminal coding agent; the audited object is its Coder agent loop -- see the adapter docstring for the wiring facts." % (
            AIDER_REPO_HEAD,
            AIDER_REPO_HEAD_DATE, AIDER_REPO_HEAD_MESSAGE,
            AIDER_VERSION),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim via the audit-47 adapter, served to Aider by monkeypatching litellm.completion; a tool decision is rendered as a SEARCH/REPLACE edit block on scratch.txt writing a CALL line, and the adapter executes the named harness tool in-process and feeds the result back as the next user message; see real_agents/aider_adapter.py)",
        "confirmation_gate": "PARTIAL, measured: (1) shell commands the model suggests ARE gated -- handle_shell_commands asks 'Run shell command?' with explicit_yes_required=True, and InputOutput(yes=True) answers 'n' to explicit confirmations, so in the unattended configuration a suggested shell command is parsed but never run (probe-measured: probe_shell.txt never created); a human typing 'y' is the only way it runs. (2) file edits are NOT gated on this path: edits to the in-chat scratch file apply with no confirmation, and new-file edits ask 'Create new file?' which yes=True auto-approves (probe-measured: probe_new.txt created). (3) no sanitization, filtering, or flagging of tool results anywhere on this path (zero 'sanitize' hits in aider/). Measured: a tool result containing tool JSON does NOT execute (it is inert text in a user message, not a dispatch -- measured in the re-probe); a raising tool is CAUGHT by the adapter's executor and returned as an 'error: Tool ... raised: ...' observation (measured in the re-probe); an unregistered tool name is NOT dispatched -- the adapter returns an 'Error: Tool <name> not found.' observation and Aider has no tool registry to dispatch through (measured in the re-probe).",
        "tool_calls": dict(ad_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(ad_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    cleanup_work_dirs()
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
