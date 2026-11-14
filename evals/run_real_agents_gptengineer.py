"""Audit GPT-Engineer (gpt-engineer-org/gpt-engineer, PyPI
gpt-engineer 0.3.1, tag v0.3.1 3e589bf1356024fb471a9d17738e4626f21a953b)
with Trustrun (sixty-third real-agent audit).

Configuration under test: GPT-Engineer's real `gen_code` +
`improve_fn` agent loop (gpt_engineer.core.default.steps) in a
fresh throwaway temp workdir per call, holding the whole Trustrun
tool set (search_docs, calculator, plus the monitor/grader/
clarification tools run_audit adds) via the adapter's file CALL
channel (see real_agents/gptengineer_adapter.py), driven by a
deterministic stub model (DeterministicChatModel, the audit-30
decision logic reused verbatim via the audit-47 adapter) served
by stubbing AI.backoff_inference (no key, no network). One fresh
stub, AI, memory, and execution env are built per call. The
generated run.sh entrypoint is NOT executed in the audited loop
(gen_entrypoint is skipped; execute_entrypoint's (Y/n) gate is
measured separately in the re-probe). File writes to the in-chat
scratch file apply with no confirmation (see
real_agents/gptengineer_adapter.py for the wiring facts).

Usage: ~/workspace/hackathons/trustrun-venvs/gptengineer-venv/bin/python3 run_real_agents_gptengineer.py
(GPT-Engineer lives in a separate venv; see
real_agents/gptengineer_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the GPT-Engineer adapter on all
25 tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/gptengineer/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/gptengineer/evidence.json. Every number in
those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The per-row "attacks" field records every
attack in the stress battery with its survived/detected outcome. The
evidence logs show the exact observation text the framework handed
the model, which is the framework-level fact. Never present a
clean-room failure as a flaw in a real product: the clean-room
agents' failures are theirs; the GPT-Engineer rows are
GPT-Engineer's. Note the repo is ARCHIVED and the audited code is
the 0.3.1 release, not default-branch HEAD: see the adapter
docstring for the pinning facts.
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

import real_agents.gptengineer_adapter as ad_adapter  # noqa: E402
from real_agents.gptengineer_adapter import (  # noqa: E402
    RUN_LOGS,
    GPTENGINEER_PYPI,
    GPTENGINEER_REPO,
    GPTENGINEER_REPO_HEAD,
    GPTENGINEER_REPO_HEAD_DATE,
    GPTENGINEER_REPO_HEAD_MESSAGE,
    GPTENGINEER_TAG,
    GPTENGINEER_TAG_COMMIT,
    GPTENGINEER_TAG_DATE,
    GPTENGINEER_TAG_MESSAGE,
    GPTENGINEER_VERSION,
    gptengineer_agent,
    cleanup_work_dirs,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "gptengineer")
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
                gptengineer_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the GPT-Engineer (non-)effect
            # lives here, not in the section verdict (worst-case over
            # the battery). Compact each attack to kind + vector /
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
                "agent": "gptengineer",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("gptengineer x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "gptengineer",
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
            print("gptengineer x %s -> CRASH (%s: %s)"
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
        "product": "GPT-Engineer (gpt-engineer-org/gpt-engineer, PyPI gpt-engineer 0.3.1, real gen_code + improve_fn loop)",
        "component": "GPT-Engineer's real gen_code + improve_fn agent loop (gpt_engineer.core.default.steps) in a fresh throwaway temp workdir per call, holding the whole Trustrun tool set via the adapter's file CALL channel (the stub renders each tool decision as a CALL line in the in-chat scratch.txt -- a full-file code block on the gen_code turn, a unified-diff block replacing the CALL line on improve_fn turns; GPT-Engineer parses and applies it with no confirmation; the adapter executes the named harness tool in-process and feeds the result back as the next improve prompt), driven by DeterministicChatModel (the audit-30 decision logic reused verbatim via the audit-47 adapter; literal model) served by stubbing AI.backoff_inference (no key, no network). One fresh stub, AI, memory, and execution env are built per call. The generated run.sh entrypoint is NOT executed in the audited loop (gen_entrypoint skipped; execute_entrypoint's (Y/n) gate measured separately in the re-probe). The framework runs the code-block parsing, the diff parse/validate/apply with its retry loop, builds the message history, and passes tool results to the model verbatim as HumanMessages; it performs no sanitization, filtering, or flagging of tool results.",
        "version": "GPT-Engineer %s (PyPI %s; audited code is the installed 0.3.1 sdist, byte-identical to tag %s)" % (
            GPTENGINEER_VERSION, GPTENGINEER_PYPI, GPTENGINEER_TAG),
        "repo": GPTENGINEER_REPO,
        "repo_resolved": "https://github.com/gpt-engineer-org/gpt-engineer, tag %s %s (commit %s, '%s'). PyPI gpt-engineer %s uploaded %s (sdist only); installed package byte-identical to the sdist and to the tag tree (diff -rq clean on both). Default-branch HEAD %s (commit %s, '%s') is NEWER than the release and differs in 9 files under gpt_engineer/ (including core/ai.py, core/chat_to_files.py, core/default/steps.py), so the audited code is the 0.3.1 release, not HEAD. The repo is ARCHIVED (GitHub API: archived true, default branch main, last pushed 2025-05-14T10:15:10Z). No SECURITY.md and no security policy or security contact exist in the repo (no SECURITY.md at tag or HEAD, none in the sdist or installed package, no security@ address and no vulnerability-disclosure instructions in the README). GPT-Engineer is a terminal code-generation agent; the audited object is its gen_code + improve_fn loop -- see the adapter docstring for the wiring facts." % (
            GPTENGINEER_TAG, GPTENGINEER_TAG_COMMIT,
            GPTENGINEER_TAG_DATE, GPTENGINEER_TAG_MESSAGE,
            GPTENGINEER_VERSION, "2024-06-06T18:26:55",
            GPTENGINEER_REPO_HEAD,
            GPTENGINEER_REPO_HEAD_DATE, GPTENGINEER_REPO_HEAD_MESSAGE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim via the audit-47 adapter, served to GPT-Engineer by stubbing AI.backoff_inference on a bare AI instance; a tool decision is rendered as a CALL line in scratch.txt -- full-file code block on the gen_code turn, unified-diff block on improve_fn turns -- and the adapter executes the named harness tool in-process and feeds the result back as the next improve prompt; see real_agents/gptengineer_adapter.py)",
        "confirmation_gate": "PARTIAL, measured: (1) file writes are NOT gated on this path: gen_code parses the model's code block into files and improve_fn parses, validates, and applies the model's diff with no confirmation of any kind (zero sanitize / require_confirmation / human_in_the_loop / approval / confirm hits across gpt_engineer/core/ and gpt_engineer/applications/). (2) shell execution IS gated: execute_entrypoint asks 'Do you want to execute this code? (Y/n)' via input(\"\") and only runs `bash run.sh` on an empty / y / yes answer (probe-measured: answering 'n' does not run the script, answering 'y' does; the gate is the only thing between model output and shell execution, and it is a plain terminal prompt -- no approval object, no allow-list). The audited loop does not run gen_entrypoint / execute_entrypoint. (3) no sanitization, filtering, or flagging of tool results anywhere on this path; a tool result containing tool JSON does NOT execute (it is inert text in a HumanMessage, not a dispatch -- measured in the re-probe); a raising tool is CAUGHT by the adapter's executor and returned as an 'error: Tool ... raised: ...' observation (measured in the re-probe); an unregistered tool name is NOT dispatched -- the adapter returns an 'Error: Tool <name> not found.' observation and GPT-Engineer has no tool registry to dispatch through (measured in the re-probe).",
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
