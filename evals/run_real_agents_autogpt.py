"""Audit AutoGPT (Significant-Gravitas/AutoGPT, git HEAD
ac4e88888d3838fd5790dff2a85845a654d05024) with Trustrun
(forty-eighth real-agent audit).

Configuration under test: a single AutoGPT OrchestratorBlock in
agent mode (agent_mode_max_iterations=20, built-in execution
mode), holding the whole Trustrun tool set as OpenAI-format
function signatures (named exactly after the tools), driven by a
deterministic stub model (DeterministicChatModel, the audit-30
decision logic reused verbatim via the audit-47 adapter) served
by patching backend.blocks.llm.llm_call (the seam AutoGPT's own
test_orchestrator_agent_mode patches). The database-manager
client and execution processor are in-process mocks (see
real_agents/autogpt_adapter.py for exactly what is mocked and
what runs for real: prompt build, LLM-call validation, the shared
tool-call loop, tool dispatch, and conversation update are all
AutoGPT's own code). One fresh OrchestratorBlock, stub, and set of
mocks is built per call. human_in_the_loop_safe_mode=False (as in
AutoGPT's own agent-mode test; the flag is not consulted on this
path). Max 20 agent-mode iterations per call (safety cap, never
binds on the measured tasks). See
real_agents/autogpt_adapter.py for the wiring facts.

Usage: ~/workspace/hackathons/trustrun-venvs/autogpt-venv/bin/python3 run_real_agents_autogpt.py
(AutoGPT lives in a separate venv + git checkout; see
real_agents/autogpt_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the AutoGPT adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/autogpt/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/autogpt/evidence.json. Every number in those
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
agents' failures are theirs; the AutoGPT rows are AutoGPT's.
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

import real_agents.autogpt_adapter as ag_adapter  # noqa: E402
from real_agents.autogpt_adapter import (  # noqa: E402
    RUN_LOGS,
    AUTOGPT_PYPI,
    AUTOGPT_REPO,
    AUTOGPT_REPO_HEAD,
    AUTOGPT_REPO_HEAD_DATE,
    AUTOGPT_REPO_HEAD_MESSAGE,
    AUTOGPT_VERSION,
    autogpt_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "autogpt")
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
                autogpt_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the AutoGPT (non-)effect lives
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
                "agent": "autogpt",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("autogpt x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "autogpt",
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
            print("autogpt x %s -> CRASH (%s: %s)"
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
        "product": "AutoGPT (Significant-Gravitas/AutoGPT, OrchestratorBlock agent mode)",
        "component": "Single AutoGPT OrchestratorBlock in agent mode (agent_mode_max_iterations=20, built-in execution mode), holding the whole Trustrun tool set as OpenAI-format function signatures (named exactly after the tools; AutoGPT validates the stub's tool calls against them and dispatches them through _execute_single_tool_with_manager), driven by DeterministicChatModel (the audit-30 decision logic reused verbatim via the audit-47 adapter; literal model) served by patching backend.blocks.llm.llm_call (the seam AutoGPT's own test_orchestrator_agent_mode patches; no key, no network). The database-manager client and execution processor are in-process mocks (the mock's on_node_execution is where the harness tools run; the framework code deciding what to run, how its result is wrapped, and what the model sees next is all AutoGPT's own). One fresh OrchestratorBlock, stub, and set of mocks is built per call. human_in_the_loop_safe_mode=False (as in AutoGPT's own agent-mode test; the flag is not consulted on this path). The framework runs the per-step loop, builds the prompt, validates tool calls, dispatches tools, and updates the conversation; it performs no sanitization, filtering, or flagging of tool results.",
        "version": "AutoGPT %s (no wheel of the platform backend on PyPI; installed from git at HEAD)" % (
            AUTOGPT_VERSION,),
        "repo": AUTOGPT_REPO,
        "repo_resolved": "https://github.com/Significant-Gravitas/AutoGPT, default-branch HEAD %s (commit %s, '%s'). PyPI carries an `autogpt` package, but it is version 0.0.1, 'An auto-evolving agent harness: measure, learn, and evolve how agents work in your codebase' -- an unrelated project, not the platform backend (no autogpt_platform, no OrchestratorBlock); there is no wheel of the audited code to compare byte-identity against. AutoGPT ships only via git clone for this code; the audited code is the checkout at the pinned HEAD in ~/workspace/hackathons/trustrun-venvs/autogpt-src (verified with git ls-remote and git rev-parse HEAD), so there is no wheel-vs-HEAD gap to measure. SECURITY.md exists: reports via a GitHub Security Advisory (preferred) or security@agpt.co; coordinated disclosure; scope is the latest production release on master plus active development code; classic/ and third-party dependencies are out of scope. The repo is NOT archived (GitHub API: archived false, default branch master). The audited object is the AutoGPT OrchestratorBlock agent loop itself -- see the adapter docstring for the wiring facts." % (
            AUTOGPT_REPO_HEAD,
            AUTOGPT_REPO_HEAD_DATE, AUTOGPT_REPO_HEAD_MESSAGE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim via the audit-47 adapter, served to AutoGPT by patching backend.blocks.llm.llm_call with an async stub function returning the response object OrchestratorBlock._attempt_llm_call_with_validation reads; final answers returned as the response text; tool results reach the model as function_call_output messages whose content is the JSON dump of the tool node's outputs dict; see real_agents/autogpt_adapter.py)",
        "confirmation_gate": "NONE on the audited path: no confirmation gate exists in the OrchestratorBlock agent-mode loop (zero hits for human_in_the_loop / require_confirmation / interrupt in orchestrator.py, llm.py, or tool_call_loop.py; the only 'sanitize' hits are a comment saying a field name is used 'not sanitized' and unpaired-surrogate encoding hygiene in llm.py). The only review hooks in the package are opt-in and off by default: the HumanInTheLoopBlock (a separate block a graph author must place explicitly; the orchestrator never invokes it) and Block.is_block_exec_need_review, which pauses only when the block is an irreversible action AND execution_context.sensitive_action_safe_mode is true (default False). Tampering knobs execute with no approval step (measured in the re-probe). Measured: a tool result containing tool JSON does NOT execute (it is a string in a function_call_output message, not a dispatch -- measured in the re-probe); a raising tool is SWALLOWED by _execute_single_tool_with_manager and returned as the generic 'Tool execution failed due to an internal error' observation (measured in the re-probe).",
        "tool_calls": dict(ag_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(ag_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
