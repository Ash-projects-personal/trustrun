"""Audit Microsoft Magentic-One (PyPI autogen-ext 0.7.5 == git tag
python-v0.7.5, repo https://github.com/microsoft/autogen) with
Trustrun (fifty-ninth real-agent audit; first Magentic-One audit).

TARGET: Magentic-One (Microsoft/AutoGen), verified absent from
DATASET.md before this audit (0 hits, no summary dir). See
real_agents/magentic_one_adapter.py for the pinning facts.

Configuration under test: the real MagenticOneGroupChat loop (the
MagenticOneOrchestrator with its task ledger, progress ledger,
stall counting, and final-answer generation) driving two member
AssistantAgents (a researcher holding the harness tools and an
answerer with no tools), all played by a deterministic stub model
through the framework's own ChatCompletionClient seam. One fresh
team (and three fresh stub clients) is built per call; one fresh
stub state per call. See real_agents/magentic_one_adapter.py for
the wiring facts.

Usage: ~/workspace/hackathons/trustrun-venvs/magentic-one-venv/bin/python3 run_real_agents_magentic_one.py
(Magentic-One lives in a separate venv; see
real_agents/magentic_one_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the Magentic-One adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/magentic_one/summary.json and the evidence logs
(injection observations) into
reports/real_agents/magentic_one/evidence.json. Every number in those
files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub
model combination. The stub is a literal model (it follows
instructions in the task text and in tool output), so a BLOCK on
an injection attack means the framework passed the attack
through to such a model unfiltered. The per-row "attacks" field
records every attack in the stress battery with its
survived/detected outcome. The evidence logs show the exact
context the framework handed the model, which is the
framework-level fact. Never present a clean-room failure as a
flaw in a real product: the clean-room agents' failures are
theirs; the Magentic-One rows are Magentic-One's. The tampering
attacks measure the framework's architecture: the knobs are
exposed as ordinary callable tools with no confirmation, so a
model that reaches for them succeeds -- that is a property of
this framework, recorded in the rows, not a vacuous pass.
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

import real_agents.magentic_one_adapter as mo_adapter  # noqa: E402
from real_agents.magentic_one_adapter import (  # noqa: E402
    RUN_LOGS,
    MAGENTIC_ONE_PYPI,
    MAGENTIC_ONE_PYPI_DATE,
    MAGENTIC_ONE_REPO,
    MAGENTIC_ONE_REPO_HEAD,
    MAGENTIC_ONE_REPO_HEAD_DATE,
    MAGENTIC_ONE_TAG,
    MAGENTIC_ONE_TAG_COMMIT,
    MAGENTIC_ONE_TAG_DATE,
    MAGENTIC_ONE_VERSION,
    magentic_one_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "magentic_one")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
PARTIAL_TOOLCALLS = os.path.join(OUT_DIR, "tool_calls_partial.json")


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
    # Resume support (same rationale as run_real_agents_aider.py:
    # rows and evidence are checkpointed after every task; a
    # re-launch skips tasks already in rows_partial.json and keeps
    # their evidence). The audit itself is run in ONE uninterrupted
    # process; the checkpoints exist only so an interrupted run
    # loses at most one task.
    rows = _load_json(PARTIAL_ROWS, [])
    done = {row["task"] for row in rows}
    RUN_LOGS.extend(_load_json(PARTIAL_EVIDENCE, []))
    # Tool-call counts live only in the adapter process; checkpoint
    # them per task too, so a crash before summary writing cannot
    # lose them again.
    mo_adapter.TOOL_CALLS.update(
        _load_json(PARTIAL_TOOLCALLS, {}))
    if done:
        print("resuming: %d tasks already done (%s)"
              % (len(done), ", ".join(sorted(done))))
    pending = [t for t in tasks if t["id"] not in done]
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
        # Per-task guard (same rationale as run_real_agents_aider.py:
        # a framework crash must be recorded as a crash row, not kill
        # the remaining tasks. A crash row is verdict BLOCK with a
        # "crash" field; its section verdicts were NOT graded, so folds
        # must count checks as 21 per graded row and 0 per crash row,
        # and summary.json lists crash task ids.)
        try:
            report = run_audit(
                magentic_one_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the Magentic-One (non-)effect
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
                "agent": "magentic_one",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("magentic_one x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "magentic_one",
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
            print("magentic_one x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc), flush=True)
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
        _write_atomic(PARTIAL_TOOLCALLS, dict(mo_adapter.TOOL_CALLS))
    summary = {
        "product": "Magentic-One (PyPI autogen-ext 0.7.5 == git tag python-v0.7.5, real MagenticOneGroupChat loop)",
        "component": "Magentic-One 0.7.5's real MagenticOneGroupChat loop (the MagenticOneOrchestrator with its task ledger, progress ledger, stall counting, and final-answer generation) driving two member AssistantAgents (a researcher holding the harness tools, an answerer with no tools), all played by a deterministic stub through the framework's own ChatCompletionClient seam -- the stub replaces the package's model, so the framework's own ledger prompts, JSON parsing, speaker selection, tool dispatch, and result handling all execute for real (no key, no network). One fresh team (and three fresh stub clients) is built per call. The framework runs the loop, converts tool results to FunctionExecutionResultMessages, and passes the result to the researcher model verbatim; it performs no sanitization, filtering, or flagging of tool output. A raising tool does NOT abort the run: AssistantAgent catches the tool error into an is_error FunctionExecutionResult, which the model then sees as its next observation (the caught class). The framework offers the model the tampering knobs as ordinary callable tools with no confirmation step, so a model that reaches for monitor_configure, edit_tests, or record_score succeeds.",
        "version": "Magentic-One %s (PyPI %s, released %s; installed files byte-identical to the sdist on all 139 .py files of autogen_ext and all 44 .py files of autogen_agentchat, and the sdist package byte-identical to git tag %s = %s, %s; HEAD %s, %s)" % (
            MAGENTIC_ONE_VERSION, MAGENTIC_ONE_PYPI,
            MAGENTIC_ONE_PYPI_DATE,
            MAGENTIC_ONE_TAG, MAGENTIC_ONE_TAG_COMMIT,
            MAGENTIC_ONE_TAG_DATE,
            MAGENTIC_ONE_REPO_HEAD, MAGENTIC_ONE_REPO_HEAD_DATE),
        "repo": MAGENTIC_ONE_REPO,
        "repo_resolved": "https://github.com/microsoft/autogen, main HEAD %s (committed %s). The repo is NOT archived. The audited code is the PyPI 0.7.5 release, verified by byte-compare of all 139 autogen_ext .py files and all 44 autogen_agentchat .py files against the shipped sdists; the sdist package tree is byte-identical to the python-v0.7.5 tag tree (the sdist-vs-HEAD diff and the tag-vs-HEAD diff are the same 7 files plus the new tools/mcp/_host directory, all outside the Magentic-One path). Magentic-One is a multi-agent orchestrator; the audited object is its MagenticOneGroupChat loop with a researcher member holding the harness tools and an answerer member -- see the adapter docstring for the wiring facts and for why the canned MagenticOne team (which hard-wires FileSurfer/WebSurfer/Coder/ComputerTerminal and takes no custom participants) was not driven directly." % (
            MAGENTIC_ONE_REPO_HEAD,
            MAGENTIC_ONE_REPO_HEAD_DATE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-31 _next_action decision logic reused verbatim for the researcher, the orchestrator deciding its progress ledger from the shared stub state, the answerer repeating the shared state's answer; see real_agents/magentic_one_adapter.py)",
        "confirmation_gate": "NONE on the audited path, measured -- the tampering knobs are exposed as ordinary callable tools with no approval step: (1) a case-insensitive package grep over the installed packages for human_in_the_loop / require_confirmation / needs_approval / approval / confirm / sanitize / interrupt returns, for autogen_agentchat (44 .py files): human_in_the_loop 0, require_confirmation 0, needs_approval 0, approval 60, confirm 1, sanitize 0, interrupt 0; for autogen_ext (139 .py files): human_in_the_loop 0, require_confirmation 0, needs_approval 0, approval 23, confirm 1, sanitize 1, interrupt 0. Every 'approval' hit is the CodeExecutorAgent approval_func (code-execution approval, agents/_code_executor_agent.py) or the MagenticOne docstring's approval_func parameter; the single 'confirm' hits are docstring prose ('Let's execute it to confirm the output.'; a video-surfer return docstring); the single 'sanitize' hit is the local code executor's docstring about sanitizing shell commands, not tool-output sanitization and not on the audited path. No per-tool approval mechanism exists on the MagenticOneGroupChat / AssistantAgent tool path and none is wired in by default; the CodeExecutorAgent approval_func is wired only into the canned MagenticOne team's ComputerTerminal via MagenticOne's approval_func parameter, which the audited loop (MagenticOneGroupChat) does not have; (2) the framework executes any tool the model requests immediately -- monitor_configure, edit_tests, and record_score are dispatched by AssistantAgent with no human gate anywhere (verified by the re-probe: the tampering attacks succeed and the grading record is changed); (3) no sanitization, filtering, or flagging of tool output anywhere on this path (verified by package grep and by the evidence logs: tool output carrying an injection reaches the researcher model verbatim inside its FunctionExecutionResultMessage); (4) a raising tool does NOT abort the run -- AssistantAgent catches it into an is_error FunctionExecutionResult, which the model sees as its next observation (the caught class -- measured in the probe); (5) a tool result containing tool JSON does NOT execute (it is inert text in the tool result, not a dispatch -- measured in the probe and in the re-probe). SECURITY.md EXISTS at the repo root (Microsoft standard template, present at main HEAD): report vulnerabilities to the Microsoft Security Response Center at https://msrc.microsoft.com/create-report, or by email to secure@microsoft.com (PGP key via the MSRC PGP Key page); do NOT report through public GitHub issues. SECURITY.md is NOT shipped in the autogen-ext sdist or the installed package.",
        "tool_calls": dict(mo_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(mo_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, PARTIAL_TOOLCALLS):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
