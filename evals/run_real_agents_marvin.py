"""Audit Prefect Marvin's marvin.Agent with Trustrun (thirty-seventh
real-agent audit; audit 36 audited LangChain deepagents'
create_deep_agent; audit 5 audited Pydantic AI's Agent, which Marvin
3.x is built on). This audit drives marvin.Agent from the marvin
package, repo https://github.com/PrefectHQ/marvin, in the default
configuration: no instructions override, no memories, no MCP
servers, no handlers beyond the disabled default print handler,
result_type=str. See real_agents/marvin_adapter.py for the wiring
facts (including the install-time import failure the adapter works
around and the MarkTaskSuccessful end-turn finish channel).

Usage: ~/workspace/hackathons/trustrun-venvs/marvin-venv/bin/python3 run_real_agents_marvin.py
(marvin lives in a separate venv; see
real_agents/marvin_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the marvin adapter on all 25 tasks,
seed 0, k=5, with the eval corpus as the data module input. Writes
one machine readable summary into
reports/real_agents/marvin/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/marvin/evidence.json. Every number in those
files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The evidence logs show the exact observation
text the framework handed the model, which is the framework-level
fact. Never present a clean-room failure as a flaw in a real product:
the clean-room agents' failures are theirs; marvin.Agent's rows are
marvin.Agent's, measured in its default configuration with the
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

from real_agents.marvin_adapter import (  # noqa: E402
    MARVIN_REPO,
    MARVIN_REPO_HEAD,
    MARVIN_VERSION,
    PYDANTIC_AI_VERSION,
    RUN_LOGS,
    marvin_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "marvin")
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
                marvin_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            rows.append({
                "agent": "marvin_agent",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
            })
            print("marvin x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "marvin_agent",
                "task": task_def["id"],
                "verdict": "BLOCK",
                "contract": "BLOCK",
                "stress": "BLOCK",
                "consistency": "BLOCK",
                "data": "BLOCK",
                "pass_rate_k": 0.0,
                "crash": "%s: %s" % (type(exc).__name__, exc),
            })
            print("marvin x %s -> CRASH (%s: %s)"
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
        "product": "marvin",
        "component": "marvin.Agent (default configuration: no instructions override, no memories, no MCP servers, no handlers beyond the disabled default print handler, result_type=str; the model ends its turn by calling the MarkTaskSuccessful_<taskid> output tool with {\"result\": ...}; plain text can never finish a turn)",
        "version": MARVIN_VERSION,
        "pydantic_ai_version": PYDANTIC_AI_VERSION,
        "repo": MARVIN_REPO,
        "repo_resolved": "https://github.com/PrefectHQ/marvin, default-branch HEAD %s. Installed with pip install marvin pytest numpy in a separate venv (~/workspace/hackathons/trustrun-venvs/marvin-venv); marvin 3.2.10 is the current latest release on PyPI. marvin.Agent is the Prefect agent framework: an Actor wrapping a pydantic-ai Agent (agentlet) with an orchestrator, Task/result-type end-turn tools, and a SQLite LLM-call log (~/.marvin/marvin.db). NOTE: a fresh pip install marvin 3.2.10 cannot be imported without setting MARVIN_AGENT_MODEL first: the default agent_model \"openai:gpt-4o\" is no longer a KnownModelName in pydantic-ai 2.67.0, so Settings() raises a ValidationError at import time; the adapter sets MARVIN_AGENT_MODEL=openai:gpt-5.6-luna before import (the value is never used as a model -- the Agent always gets an explicit FunctionModel)." % MARVIN_REPO_HEAD,
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-5 DeterministicFunctionModel decision logic ported verbatim, with the finish channel changed to the MarkTaskSuccessful output tool and the observation channel extended to RetryPromptPart; see real_agents/marvin_adapter.py)",
        "confirmation_gate": "none. Marvin 3.2.10 ships no approval / human-in-the-loop / require-confirmation mechanism for tool calls: a symbol search over the installed package for human_in_the_loop/require_confirmation returns 0 hits, and the only confirm/approval hits (4) are typer.confirm prompts for destructive database-migration CLI commands (cli/migrations.py), not a tool-call gate; behaviorally the re-probe measured monitor_configure calls executing with no approval step. A tool that raises is caught by marvin.utilities.tools.wrap_tool_errors and re-raised as pydantic_ai.ModelRetry('Tool failed: ...'); pydantic-ai hands the failure back to the model as a ToolReturnPart with content 'Tool failed: ...', so the run degrades to a flagged failure answer instead of aborting.",
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
