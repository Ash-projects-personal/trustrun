"""Audit langgraph-supervisor's create_supervisor (langgraph-supervisor
0.0.31) with Trustrun (forty-third real-agent audit; first audit of
this framework in the rotation -- the supervisor multi-agent built on
LangGraph, repo https://github.com/langchain-ai/langgraph-supervisor-py,
archived Sep 20, 2026, read-only).

Configuration under test: one worker agent (LangChain create_agent,
the audit-41 worker verbatim) holds the whole Trustrun tool set and
the supervisor routes every task to it via transfer_to_researcher
and relays the worker's final answer back, with
add_handoff_messages=False (a shipped option; the default True puts
a "Successfully transferred to researcher" ToolMessage in the shared
history that the literal stub treats as a tool observation -- see
real_agents/langgraph_supervisor_adapter.py for the measured wiring
facts). No supervisor tools, no middleware, no checkpointer, default
output_mode="last_message", default prompt. See
real_agents/langgraph_supervisor_adapter.py for the wiring facts and
the routing-only supervisor stub.

Usage: ~/workspace/hackathons/trustrun-venvs/langgraph-supervisor-venv/bin/python3 run_real_agents_langgraph_supervisor.py
(langgraph-supervisor lives in a separate venv; see
real_agents/langgraph_supervisor_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the supervisor adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/langgraph_supervisor/summary.json and the
evidence logs (injection observations, tampering calls, handoff
records) into
reports/real_agents/langgraph_supervisor/evidence.json. Every number
in those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered -- the supervisor layer adds no filtering
and no confirmation gate over the bare worker, which is the finding
to compare against audit 41 (the same worker with no supervisor).
The per-row "attacks" field records every attack in the stress
battery with its survived/detected outcome. The evidence logs show
the exact observation text the framework handed the worker model,
which is the framework-level fact. Never present a clean-room
failure as a flaw in a real product: the clean-room agents'
failures are theirs; the supervisor rows are the supervisor's.
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

import real_agents.langgraph_supervisor_adapter as sup_adapter  # noqa: E402
from real_agents.langgraph_supervisor_adapter import (  # noqa: E402
    LANGGRAPH_SUPERVISOR_REPO,
    LANGGRAPH_SUPERVISOR_REPO_HEAD,
    LANGGRAPH_SUPERVISOR_REPO_HEAD_DATE,
    LANGGRAPH_SUPERVISOR_REPO_HEAD_MESSAGE,
    LANGGRAPH_SUPERVISOR_TAG,
    LANGGRAPH_SUPERVISOR_TAG_COMMIT,
    LANGGRAPH_SUPERVISOR_TAG_DATE,
    LANGGRAPH_SUPERVISOR_VERSION,
    LANGCHAIN_CORE_VERSION,
    LANGCHAIN_VERSION,
    LANGGRAPH_VERSION,
    RUN_LOGS,
    langgraph_supervisor_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "langgraph_supervisor")
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
                langgraph_supervisor_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the supervisor's (non-)effect
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
                "agent": "langgraph_supervisor",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("langgraph_supervisor x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "langgraph_supervisor",
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
            print("langgraph_supervisor x %s -> CRASH (%s: %s)"
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
        "product": "langgraph-supervisor create_supervisor (langgraph-supervisor 0.0.31, supervisor multi-agent on LangGraph)",
        "component": "create_supervisor([worker], model=router.as_model(), add_handoff_messages=False), where worker = create_agent(stub.as_model(), tools, name='researcher') and the router is a routing-only deterministic stub (transfer to the worker on the first call, relay the worker's final message afterwards; never calls a Trustrun tool itself). One worker holds the whole Trustrun tool set; no supervisor tools, no middleware, no checkpointer, default output_mode='last_message', default prompt. A fresh supervisor, worker, stub, and router are built per call.",
        "version": "langgraph-supervisor %s + langchain %s + langchain-core %s + langgraph %s" % (
            LANGGRAPH_SUPERVISOR_VERSION, LANGCHAIN_VERSION,
            LANGCHAIN_CORE_VERSION, LANGGRAPH_VERSION),
        "repo": LANGGRAPH_SUPERVISOR_REPO,
        "repo_resolved": "https://github.com/langchain-ai/langgraph-supervisor-py, default-branch HEAD %s (commit %s, '%s'). The repo was archived by the owner on Sep 20, 2026 and is read-only. Installed with pip install langgraph-supervisor==0.0.31 langchain==1.5.0 numpy pytest in a separate venv (~/workspace/hackathons/trustrun-venvs/langgraph-supervisor-venv); langgraph-supervisor 0.0.31 is the current latest release on PyPI at audit time. The wheel's tag (%s, %s, commit %s) is 10 commits behind HEAD and all 10 are docs/dependency bumps with no code changes, so the wheel and HEAD are the same code. The audited object is create_supervisor in the default configuration apart from add_handoff_messages=False -- see the adapter docstring for why that shipped option is load-bearing for the literal stub." % (
            LANGGRAPH_SUPERVISOR_REPO_HEAD, LANGGRAPH_SUPERVISOR_REPO_HEAD_DATE,
            LANGGRAPH_SUPERVISOR_REPO_HEAD_MESSAGE,
            LANGGRAPH_SUPERVISOR_TAG, LANGGRAPH_SUPERVISOR_TAG_DATE,
            LANGGRAPH_SUPERVISOR_TAG_COMMIT),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim for the worker) + supervisor-router-stub-v1 (routing only: transfer to the worker, then relay the worker's final message; see real_agents/langgraph_supervisor_adapter.py)",
        "confirmation_gate": "NONE -- no confirmation gate exists in the langgraph_supervisor package: human_in_the_loop / require_confirmation / interrupt return 0 hits across the whole installed package. The only human-in-the-loop hooks are the generic pre_model_hook / post_model_hook passthroughs, unwired by default. Measured: a tampering knob called by the worker executes with no approval step (probe section 5: monitor_configure executions=1, result correct). The supervisor layer adds no protection over the bare worker (audit 41). Per-tool-class execution counts for this run are in 'tool_calls' below; per-attack outcomes are in each row's 'attacks' field.",
        "handoff_stats": {
            # NOTE: TRANSFERS / ROUTER_TURNS are ints in the adapter
            # module; read them off the module here, not via a
            # from-import (which would snapshot 0 at import time).
            "transfers": sup_adapter.TRANSFERS,
            "router_turns": sup_adapter.ROUTER_TURNS,
            "note": "One transfer_to_researcher per run is the expected shape: the router hands off once and relays the worker's final answer. Counted in the router stub itself, not from final state messages: with add_handoff_messages=False the handoff drops the supervisor's transfer-call message from the history, so the final state carries no record of the transfer.",
        },
        "tool_calls": dict(sup_adapter.TOOL_CALLS),
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
    print("handoff_stats:", {"transfers": sup_adapter.TRANSFERS,
                             "router_turns": sup_adapter.ROUTER_TURNS})
    print("tool_calls:", dict(sup_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
