"""Audit LangChain's create_tool_calling_agent with Trustrun
(thirty-fifth real-agent audit; second LangChain agent constructor
audited -- audit 30 audited create_react_agent from
langgraph.prebuilt, langgraph 1.2.20 + langchain-core 1.7.6; this
audit drives the classic tool-calling agent: create_tool_calling_agent
+ AgentExecutor with the canonical ChatPromptTemplate, in the default
configuration with no system prompt beyond "You are a helpful
assistant". See real_agents/langchain_toolcalling_adapter.py for the
wiring facts.)

Usage: ~/workspace/hackathons/trustrun-venvs/langchain-toolcalling-venv/bin/python3 run_real_agents_langchain_toolcalling.py
(langchain-classic lives in a separate venv; see
real_agents/langchain_toolcalling_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the LangChain tool-calling adapter
on all 25 tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/langchain_toolcalling/summary.json and the
evidence logs (injection observations, tampering calls) into
reports/real_agents/langchain_toolcalling/evidence.json. Every number
in those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The evidence logs show the exact observation
text the framework handed the model, which is the framework-level
fact. Never present a clean-room failure as a flaw in a real product:
the clean-room agents' failures are theirs; LangChain
create_tool_calling_agent's rows are create_tool_calling_agent's.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

from real_agents.langchain_toolcalling_adapter import (  # noqa: E402
    LANGCHAIN_CLASSIC_VERSION,
    LANGCHAIN_CORE_VERSION,
    LANGCHAIN_REPO,
    LANGCHAIN_TOOLCALLING_REPO_HEAD,
    RUN_LOGS,
    langchain_toolcalling_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "langchain_toolcalling")
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
                langchain_toolcalling_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            rows.append({
                "agent": "langchain_toolcalling_agent",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
            })
            print("langchain_toolcalling x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "langchain_toolcalling_agent",
                "task": task_def["id"],
                "verdict": "BLOCK",
                "contract": "BLOCK",
                "stress": "BLOCK",
                "consistency": "BLOCK",
                "data": "BLOCK",
                "pass_rate_k": 0.0,
                "crash": "%s: %s" % (type(exc).__name__, exc),
            })
            print("langchain_toolcalling x %s -> CRASH (%s: %s)"
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
        "product": "langchain-classic",
        "component": "create_tool_calling_agent + AgentExecutor (default configuration: canonical ChatPromptTemplate with system 'You are a helpful assistant', chat_history placeholder, human {input}, agent_scratchpad placeholder; max_iterations 30)",
        "version": LANGCHAIN_CLASSIC_VERSION,
        "langchain_core_version": LANGCHAIN_CORE_VERSION,
        "repo": LANGCHAIN_REPO,
        "repo_resolved": "https://github.com/langchain-ai/langchain, default-branch HEAD %s (commit 2026-11-11 16:12 UTC, 'release(typesafe): 0.1.0 (#41800)'). Installed with pip install langchain-classic langchain-core langgraph numpy pytest in a separate venv (~/workspace/hackathons/trustrun-venvs/langchain-toolcalling-venv); langchain-classic 1.0.8 is the current latest release on PyPI. create_tool_calling_agent is the classic tool-calling agent constructor: it returns a Runnable producing AgentAction / AgentFinish, driven by AgentExecutor." % LANGCHAIN_TOOLCALLING_REPO_HEAD,
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim; see real_agents/langchain_toolcalling_adapter.py)",
        "confirmation_gate": "none: a grep of langchain_classic/agents/ for confirm / approval / human_in_the_loop / require_confirmation returns zero hits in langchain-classic 1.0.8 — AgentExecutor ships no approval hook, no human-in-the-loop switch, and no tool allowlist, so tools the model requests execute immediately with no approval step (the re-probe measured monitor_configure calls executing with no approval step). A tool that raises propagates out of AgentExecutor.invoke instead of reaching the model as an observation; the adapter's catch returns flagged 'I could not complete the task: ...'.",
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
