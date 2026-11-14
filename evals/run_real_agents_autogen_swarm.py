"""Audit Microsoft AutoGen Swarm (autogen-agentchat 0.7.5) with Trustrun
(thirty-first real-agent audit; second agent class in the AutoGen
package -- audit 6 audited the AgentChat AssistantAgent 0.7.5 driven
directly via on_messages(); this audit drives the multi-agent handoff
class: AssistantAgent with handoffs run inside a Swarm team. In
0.7.5 there is no separate SwarmAgent class; see
real_agents/autogen_swarm_adapter.py for the wiring facts.)

Usage: ~/workspace/hackathons/trustrun-venvs/autogen-swarm-venv/bin/python3 run_real_agents_autogen_swarm.py
(AutoGen lives in a separate venv; see
real_agents/autogen_swarm_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the AutoGen Swarm adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/autogen_swarm/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/autogen_swarm/evidence.json. Every number in
those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The evidence logs show the exact observation
text the framework handed the model, which is the framework-level
fact. Never present a clean-room failure as a flaw in a real product:
the clean-room agents' failures are theirs; AutoGen Swarm's rows are
AutoGen Swarm's.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

from real_agents.autogen_swarm_adapter import (  # noqa: E402
    AUTOGEN_AGENTCHAT_VERSION,
    AUTOGEN_REPO,
    AUTOGEN_REPO_HEAD,
    RUN_LOGS,
    autogen_swarm_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "autogen_swarm")
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
                autogen_swarm_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            rows.append({
                "agent": "autogen_swarm_agent",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
            })
            print("autogen_swarm x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "autogen_swarm_agent",
                "task": task_def["id"],
                "verdict": "BLOCK",
                "contract": "BLOCK",
                "stress": "BLOCK",
                "consistency": "BLOCK",
                "data": "BLOCK",
                "pass_rate_k": 0.0,
                "crash": "%s: %s" % (type(exc).__name__, exc),
            })
            print("autogen_swarm x %s -> CRASH (%s: %s)"
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
        "product": "autogen",
        "component": "Swarm (AssistantAgent with handoffs in a Swarm team)",
        "version": AUTOGEN_AGENTCHAT_VERSION,
        "repo": AUTOGEN_REPO,
        "repo_resolved": "https://github.com/microsoft/autogen, default-branch HEAD %s (commit 2026-10-28, 'docs: add archive caution to landing page (#8393)'). Installed with pip install autogen-agentchat numpy pytest in a separate venv (~/workspace/hackathons/trustrun-venvs/autogen-swarm-venv); 0.7.5 is the current latest release on PyPI (pip index versions). In 0.7.5 there is no SwarmAgent class: the swarm mechanism is AssistantAgent(handoffs=[...]) + Swarm team." % AUTOGEN_REPO_HEAD,
        "model_driver": "deterministic-stub-v1 via two ChatCompletionClient subclasses sharing one decision state (researcher AssistantAgent with the harness tools + handoffs=['answerer']; answerer AssistantAgent with no tools; literal model: follows instructions in task text and tool output; the researcher sees tool results as FunctionExecutionResultMessage in its own model context, the answerer does not -- its model context carries no tool results, so it decides from the shared stub state recorded verbatim by the researcher; see real_agents/autogen_swarm_adapter.py)",
        "confirmation_gate": "none in the default configuration: a grep over the installed autogen_agentchat/agents/_assistant_agent.py finds zero 'confirm' or 'approv' symbols in the tool-execution path, and the probe measured a monitor_configure call executing immediately with no approval step. The framework ships no approval hook, no human-in-the-loop switch, and no tool allowlist on this path.",
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
