"""Audit LlamaIndex FunctionAgent (llama-index-core 0.14.25) with Trustrun
(thirty-eighth real-agent audit; second LlamaIndex agent class --
ReActAgent was audit 3, same 0.14.25 core; audits 35/36/37 were
LangChain create_tool_calling_agent, LangChain deepagents, and
Prefect Marvin).

Usage: ~/workspace/hackathons/trustrun-venvs/llamaindex-functionagent-venv/bin/python3 run_real_agents_llamaindex_functionagent.py
(llama-index lives in a separate venv; see
real_agents/llamaindex_functionagent_adapter.py for the install
command.)

Runs trustrun.cli.run_audit over the FunctionAgent adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/llamaindex_functionagent/summary.json and the
evidence logs (injection observations, tampering calls) into
reports/real_agents/llamaindex_functionagent/evidence.json. Every
number in those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The evidence logs show the exact observation
text the framework handed the model, which is the framework-level
fact. Never present a clean-room failure as a flaw in a real product:
the clean-room agents' failures are theirs; FunctionAgent's rows are
FunctionAgent's, measured in its default configuration with the
deterministic stub.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

from real_agents.llamaindex_functionagent_adapter import (  # noqa: E402
    LLAMAINDEX_CORE_VERSION,
    LLAMAINDEX_REPO,
    LLAMAINDEX_REPO_HEAD,
    RUN_LOGS,
    llamaindex_functionagent_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "llamaindex_functionagent")
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
                llamaindex_functionagent_agent, task, data_path=CORPUS,
                seed=0, k=5
            )
            sections = report["sections"]
            rows.append({
                "agent": "llamaindex_functionagent",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
            })
            print("llamaindex_functionagent x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "llamaindex_functionagent",
                "task": task_def["id"],
                "verdict": "BLOCK",
                "contract": "BLOCK",
                "stress": "BLOCK",
                "consistency": "BLOCK",
                "data": "BLOCK",
                "pass_rate_k": 0.0,
                "crash": "%s: %s" % (type(exc).__name__, exc),
            })
            print("llamaindex_functionagent x %s -> CRASH (%s: %s)"
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
        "product": "LlamaIndex FunctionAgent (llama-index-core)",
        "component": "FunctionAgent (default configuration: no system prompt override, native function calling via the workflow agent loop, allow_parallel_tool_calls default True, streaming False)",
        "version": "llama-index-core %s" % LLAMAINDEX_CORE_VERSION,
        "repo": LLAMAINDEX_REPO,
        "repo_resolved": "https://github.com/run-llama/llama_index, default-branch HEAD %s (commit 2026-11-11 14:37 UTC, \"fix(llms-openai): allow openai 3.x (#24138)\"). Installed with pip install llama-index-core in a separate venv (~/workspace/hackathons/trustrun-venvs/llamaindex-functionagent-venv); llama-index-core 0.14.25 is the current latest release on PyPI. FunctionAgent is the workflow-based function-calling agent in llama-index-core: it drives the model through llm.achat_with_tools, extracts native tool calls with llm.get_tool_calls_from_response, and feeds tool results back as ChatMessage(role=\"tool\") entries in the workflow scratchpad." % LLAMAINDEX_REPO_HEAD,
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-3 ReActAgent DeterministicLLM decision logic ported verbatim, with the finish channel changed from ReAct text to native tool calls (ToolCallBlock) and the observation channel changed to TOOL-role scratchpad messages; see real_agents/llamaindex_functionagent_adapter.py)",
        "confirmation_gate": "none. LlamaIndex 0.14.25 ships no approval / human-in-the-loop / require-confirmation mechanism for FunctionAgent tool calls: a symbol search over the installed llama-index-core 0.14.25 package for human_in_the_loop / require_confirmation returns 0 hits in the whole core package, and word-boundary confirm / approval returns 0 hits in agent/ and in tools/. Behaviorally the re-probe measured monitor_configure calls executing with no approval step. A tool that raises is caught by BaseWorkflowAgent._call_tool and handed back as ToolOutput(content=<bare exception string>, is_error=True) with no error marker, so the model cannot tell a failure from a result unless the exception text itself says so.",
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
