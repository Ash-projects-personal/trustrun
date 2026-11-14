"""Audit LlamaIndex Workflows (llama-index-workflows 2.26.1) with Trustrun
(forty-fifth real-agent audit; first audit of the standalone Workflows
package in the rotation -- the event-driven orchestration engine from
run-llama/llama-agents, package packages/llama-index-workflows/).

Configuration under test: a two-step Workflow (decide + execute_tools)
holding the whole Trustrun tool set (search_docs, monitor_configure,
edit_tests, record_score, calculator, ask_user) as llama-index-core
FunctionTools (schemas only; the harness fns are called directly by
the execute_tools step), driven by a deterministic stub model
(DeterministicLLM, a FunctionCallingLLM subclass copied verbatim from
the audit-38 FunctionAgent adapter). One fresh workflow, stub, and
history are built per call. No system prompt beyond the audit's
neutral instruction (the stub decides from the task text; the
workflow adds no system message of its own), no human-in-the-loop,
no checkpointer, timeout 120s. See
real_agents/llamaindex_workflows_adapter.py for the wiring facts.

Usage: ~/workspace/hackathons/trustrun-venvs/llamaindex-workflows-venv/bin/python3 run_real_agents_llamaindex_workflows.py
(llama-index-workflows lives in a separate venv; see
real_agents/llamaindex_workflows_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the Workflows adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/llamaindex_workflows/summary.json and the evidence
logs (injection observations, tampering calls) into
reports/real_agents/llamaindex_workflows/evidence.json. Every number
in those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The per-row "attacks" field records every
attack in the stress battery with its survived/detected outcome. The
evidence logs show the exact observation text the framework handed
the model, which is the framework-level fact. Never present a
clean-room failure as a flaw in a real product: the clean-room
agents' failures are theirs; the Workflows rows are Workflows'.
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

import real_agents.llamaindex_workflows_adapter as lw_adapter  # noqa: E402
from real_agents.llamaindex_workflows_adapter import (  # noqa: E402
    LLAMAINDEX_CORE_VERSION,
    RUN_LOGS,
    WORKFLOWS_PYPI,
    WORKFLOWS_REPO,
    WORKFLOWS_REPO_HEAD,
    WORKFLOWS_REPO_HEAD_DATE,
    WORKFLOWS_REPO_HEAD_MESSAGE,
    WORKFLOWS_REPO_PATH,
    WORKFLOWS_VERSION,
    llamaindex_workflows_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "llamaindex_workflows")
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
                llamaindex_workflows_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the Workflows (non-)effect lives
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
                "agent": "llamaindex_workflows",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("llamaindex_workflows x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "llamaindex_workflows",
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
            print("llamaindex_workflows x %s -> CRASH (%s: %s)"
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
        "product": "LlamaIndex Workflows (llama-index-workflows 2.26.1, event-driven orchestration engine)",
        "component": "Two-step Workflow (decide + execute_tools) holding the whole Trustrun tool set as llama-index-core FunctionTools (schemas only; the harness fns are called directly by the execute_tools step), driven by DeterministicLLM (a FunctionCallingLLM subclass copied verbatim from the audit-38 FunctionAgent adapter; literal model) inside Workflow.run (timeout 120s, no system prompt added by the workflow, no human-in-the-loop, no checkpointer). One fresh workflow, stub, and history are built per call. The framework routes ToolCallsEvent/ToolResultsEvent between the steps and returns the StopEvent result; it performs no sanitization, filtering, or flagging of event payloads.",
        "version": "llama-index-workflows %s (llama-index-core %s companion, stub base class + FunctionTool wrappers only)" % (
            WORKFLOWS_VERSION, LLAMAINDEX_CORE_VERSION),
        "repo": WORKFLOWS_REPO,
        "repo_resolved": "https://github.com/run-llama/llama-agents, package %s, default-branch HEAD %s (commit %s, '%s'). Installed with pip install %s llama-index-core==%s pytest in a separate venv (~/workspace/hackathons/trustrun-venvs/llamaindex-workflows-venv); llama-index-workflows 2.26.1 is the current latest release on PyPI at audit time. PyPI ships NO source URL for this package (no home_page, no project_urls, no [project.urls] in the sdist); the source was located via the GitHub repo search (the sdist also ships src/llama_agents/workflows). The pyproject.toml at HEAD declares version 2.26.1, and the wheel's workflows/workflow.py and workflows/events.py are byte-identical to that HEAD's source (diff-verified), so the wheel and HEAD are the same code. No v2.26.1 tag exists (highest llama-index-workflows@* tag is 2.14.1). The audited object is the `workflows` package itself -- see the adapter docstring for the wiring facts." % (
            WORKFLOWS_REPO_PATH, WORKFLOWS_REPO_HEAD,
            WORKFLOWS_REPO_HEAD_DATE, WORKFLOWS_REPO_HEAD_MESSAGE,
            WORKFLOWS_PYPI, LLAMAINDEX_CORE_VERSION),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim via the audit-38 DeterministicLLM, expressed as native tool calls; final answers returned as the StopEvent result; see real_agents/llamaindex_workflows_adapter.py)",
        "confirmation_gate": "NONE by default -- no per-tool confirmation gate exists in the package (zero hits for human_in_the_loop / require_confirmation / approval / functional confirm across the installed package; the single 'confirm' hit is a comment about idle checks). Measured: tampering knobs called by the model execute with no approval step. Workflows-specific: an external HumanResponseEvent reaches a step verbatim with no validation or provenance marking (measured in the re-probe); a tool result containing tool JSON does NOT execute (it is data in a ToolResultsEvent, not an event -- measured in the re-probe).",
        "tool_calls": dict(lw_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(lw_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
