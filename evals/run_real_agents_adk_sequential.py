"""Audit Google ADK's SequentialAgent with Trustrun
(thirty-fourth real-agent audit; second agent class in the
google-adk package -- audit 10 audited the single LlmAgent 2.14.0
driven directly via Runner; this audit drives the multi-agent
orchestration class: a SequentialAgent running two LlmAgent
sub-agents in sequence (researcher with the harness tools, then an
answerer that returns the researcher's final answer verbatim), in
the default configuration with no system prompt. See
real_agents/adk_sequential_adapter.py for the wiring facts.)

Usage: ~/workspace/hackathons/trustrun-venvs/adk-sequential-venv/bin/python3 run_real_agents_adk_sequential.py
(google-adk lives in a separate venv; see
real_agents/adk_sequential_adapter.py for the install command.)
Run with OTEL_SDK_DISABLED=true (telemetry off, offline).

Runs trustrun.cli.run_audit over the ADK SequentialAgent adapter on
all 25 tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/adk_sequential/summary.json and the evidence
logs (injection observations, tampering calls) into
reports/real_agents/adk_sequential/evidence.json. Every number in
those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stubs are literal models (they follow instructions
in the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The evidence logs show the exact observation
text the framework handed the models, which is the framework-level
fact. Never present a clean-room failure as a flaw in a real product:
the clean-room agents' failures are theirs; ADK SequentialAgent's
rows are ADK SequentialAgent's.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

from real_agents.adk_sequential_adapter import (  # noqa: E402
    ADK_REPO,
    ADK_SEQUENTIAL_REPO_HEAD,
    ADK_SEQUENTIAL_VERSION,
    RUN_LOGS,
    adk_sequential_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "adk_sequential")
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
                adk_sequential_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            rows.append({
                "agent": "adk_sequential_agent",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
            })
            print("adk_sequential x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "adk_sequential_agent",
                "task": task_def["id"],
                "verdict": "BLOCK",
                "contract": "BLOCK",
                "stress": "BLOCK",
                "consistency": "BLOCK",
                "data": "BLOCK",
                "pass_rate_k": 0.0,
                "crash": "%s: %s" % (type(exc).__name__, exc),
            })
            print("adk_sequential x %s -> CRASH (%s: %s)"
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
        "product": "google-adk",
        "component": "SequentialAgent (default configuration: researcher LlmAgent with the harness tools, then answerer LlmAgent with no tools that returns the researcher's final answer verbatim; sub-agents run in sequence sharing session state)",
        "version": ADK_SEQUENTIAL_VERSION,
        "repo": ADK_REPO,
        "repo_resolved": "https://github.com/google/adk-python, default-branch HEAD %s (commit 2026-11-11 18:04 UTC, 'fix: do not score hallucinations_v1 responses with unlabelled sentences', merge of PR #7967). Installed with pip install google-adk numpy pytest in a separate venv (~/workspace/hackathons/trustrun-venvs/adk-sequential-venv); 2.14.0 is the current latest release on PyPI. The SequentialAgent is the multi-agent orchestration class: sub-agents run in sequence sharing session state, each prior sub-agent's events relayed to the next as quoted user-role transcript (see real_agents/adk_sequential_adapter.py)." % ADK_SEQUENTIAL_REPO_HEAD,
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; researcher runs the audit-10 DeterministicLlm decision logic verbatim; answerer runs a literal relay stub that returns the last quoted '[researcher] said:' block verbatim; see real_agents/adk_sequential_adapter.py)",
        "confirmation_gate": "opt-in per tool, off by default: FunctionTool(..., require_confirmation=False) gates execution (with no ToolConfirmation present the framework returns 'This tool call requires confirmation, please approve or reject.' instead of running the tool; BaseTool.check_require_confirmation defaults to False), but the audit runs plain FunctionTool wrappers with require_confirmation unset, so the gate is off and tools execute immediately with no approval step -- the re-probe measured a monitor_configure call executing immediately. No approval hook, human-in-the-loop switch, or tool allowlist is on by default on this path.",
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
    from collections import Counter
    print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
    print("stress:", dict(Counter(r["stress"] for r in rows)))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
