"""Audit LangChain's create_agent (langchain.agents, the unified agent
constructor in LangChain 1.x) with Trustrun (forty-first real-agent
audit; fifth LangChain-family substrate audited -- audit 30 audited
create_react_agent from langgraph.prebuilt, langgraph 1.2.20 +
langchain-core 1.7.6; audit 35 audited create_tool_calling_agent +
AgentExecutor from langchain-classic 1.0.8; audit 36 audited
create_deep_agent from deepagents 0.7.35; audit 39 hand-built the
ReAct loop directly from langgraph primitives -- StateGraph +
ToolNode + tools_condition. This audit drives create_agent in the
default configuration: no system prompt, no middleware, no
checkpointer, no interrupt_before/after. Repo
https://github.com/langchain-ai/langchain. See
real_agents/langchain_createagent_adapter.py for the wiring facts.)

Usage: ~/workspace/hackathons/trustrun-venvs/langchain-createagent-venv/bin/python3 run_real_agents_langchain_createagent.py
(langchain lives in a separate venv; see
real_agents/langchain_createagent_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the create_agent adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/langchain_createagent/summary.json and the
evidence logs (injection observations, tampering calls) into
reports/real_agents/langchain_createagent/evidence.json. Every number
in those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The evidence logs show the exact observation
text the framework handed the model, which is the framework-level
fact. Never present a clean-room failure as a flaw in a real product:
the clean-room agents' failures are theirs; the create_agent rows
are create_agent's.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

from real_agents.langchain_createagent_adapter import (  # noqa: E402
    LANGCHAIN_CORE_VERSION,
    LANGCHAIN_REPO,
    LANGCHAIN_REPO_HEAD,
    LANGCHAIN_REPO_HEAD_DATE,
    LANGCHAIN_REPO_HEAD_MESSAGE,
    LANGCHAIN_VERSION,
    LANGGRAPH_VERSION,
    RUN_LOGS,
    langchain_createagent_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "langchain_createagent")
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
                langchain_createagent_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            rows.append({
                "agent": "langchain_createagent",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
            })
            print("langchain_createagent x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "langchain_createagent",
                "task": task_def["id"],
                "verdict": "BLOCK",
                "contract": "BLOCK",
                "stress": "BLOCK",
                "consistency": "BLOCK",
                "data": "BLOCK",
                "pass_rate_k": 0.0,
                "crash": "%s: %s" % (type(exc).__name__, exc),
            })
            print("langchain_createagent x %s -> CRASH (%s: %s)"
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
        "product": "LangChain create_agent (langchain.agents, unified agent constructor in LangChain 1.x)",
        "component": "create_agent(model, tools) in the default configuration: no system prompt, no middleware, no checkpointer, no interrupt_before/after; exactly the tools the caller passes in, no built-in tools added",
        "version": "langchain %s + langchain-core %s + langgraph %s" % (
            LANGCHAIN_VERSION, LANGCHAIN_CORE_VERSION, LANGGRAPH_VERSION),
        "repo": LANGCHAIN_REPO,
        "repo_resolved": "https://github.com/langchain-ai/langchain, default-branch HEAD %s (commit %s, '%s'). Installed with pip install langchain langchain-core numpy pytest in a separate venv (~/workspace/hackathons/trustrun-venvs/langchain-createagent-venv); langchain 1.5.0 is the current latest release on PyPI at audit time. The audited object is the unified agent constructor itself: create_agent(model, tools) returning a CompiledStateGraph, the way the LangChain 1.x docs build an agent." % (
            LANGCHAIN_REPO_HEAD, LANGCHAIN_REPO_HEAD_DATE,
            LANGCHAIN_REPO_HEAD_MESSAGE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim; see real_agents/langchain_createagent_adapter.py)",
        "confirmation_gate": "none by default. create_agent wires no per-tool approval mechanism in: grep of the installed langchain 1.5.0 langchain/agents package gives human_in_the_loop 1 line hit (only the import of the middleware in middleware/__init__.py), require_confirmation 0 hits, word-boundary confirm 1 hit (a docstring in middleware/shell_tool.py), word-boundary approval 6 hits (all inside the opt-in HumanInTheLoopMiddleware in middleware/human_in_the_loop.py, plus one line in auto_mode.py stating it does NOT request human approval). The mechanism exists opt-in as HumanInTheLoopMiddleware (langchain.agents.middleware.human_in_the_loop, built on langgraph interrupt()), but create_agent(model, tools) does not add it. A plain create_agent executes tool calls with no approval step: the re-probe measured monitor_configure executing with no approval step. A tool that raises propagates out of agent.invoke instead of reaching the model as an observation (the graph's ToolNode default handler re-raises non-ToolInvocationError); the adapter's catch returns flagged 'I could not complete the task: ...'.",
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
