"""Audit LangChain's create_agent WITH HumanInTheLoopMiddleware wired in
(langchain.agents.middleware.human_in_the_loop) with Trustrun
(forty-second real-agent audit; second pass over the unified agent
constructor in LangChain 1.x -- audit 41 drove create_agent in the
default configuration and found langchain 1.5.0 is the first framework
in the rotation that ships a confirmation-gate mechanism but does not
wire it in by default. This audit wires it in: create_agent(model,
tools, middleware=[HumanInTheLoopMiddleware(interrupt_on={every tool:
True})], checkpointer=InMemorySaver()), batched mode, and the harness
plays the human reviewer: it REJECTS the tampering knobs
(monitor_configure, edit_tests, record_score) and APPROVES every other
tool. Repo https://github.com/langchain-ai/langchain. See
real_agents/langchain_createagent_hitl_adapter.py for the wiring facts
and the pre-declared reviewer policy.)

Usage: ~/workspace/hackathons/trustrun-venvs/langchain-createagent-hitl-venv/bin/python3 run_real_agents_langchain_createagent_hitl.py
(langchain lives in a separate venv; see
real_agents/langchain_createagent_hitl_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the create_agent+HITL adapter on all
25 tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/langchain_createagent_hitl/summary.json and the
evidence logs (injection observations, tampering calls, gate records)
into
reports/real_agents/langchain_createagent_hitl/evidence.json. Every
number in those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination under the stated reviewer policy. The stub is a literal
model (it follows instructions in the task text and in tool output),
so a BLOCK on an injection or tampering attack means the framework
passed the attack through to such a model unfiltered -- or, for the
injection attacks, that the attack needs no tool call at all and the
gate never engages. The per-row "attacks" field records every attack
in the stress battery with its survived/detected outcome, which is
where the gate's effect shows: section verdicts are worst-case over
the battery, so a gate that blocks the tampering vectors but not the
plaintext injection leaves the stress section BLOCK while the
per-attack rows change. The evidence logs show the exact observation
text the framework handed the model, which is the framework-level
fact. Never present a clean-room failure as a flaw in a real product:
the clean-room agents' failures are theirs; the create_agent+HITL
rows are create_agent+HITL's.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "real_agents"))

from real_agents.langchain_createagent_hitl_adapter import (  # noqa: E402
    GATE_STATS,
    LANGCHAIN_CORE_VERSION,
    LANGCHAIN_REPO,
    LANGCHAIN_REPO_HEAD,
    LANGCHAIN_REPO_HEAD_DATE,
    LANGCHAIN_REPO_HEAD_MESSAGE,
    LANGCHAIN_VERSION,
    LANGGRAPH_VERSION,
    RUN_LOGS,
    langchain_createagent_hitl_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "langchain_createagent_hitl")
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
                langchain_createagent_hitl_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the gate's effect lives here, not in
            # the section verdict (worst-case over the battery). Compact
            # each attack to kind + vector/encoding + outcome; the
            # evidence text lives in the re-probe log.
            attacks = [{
                "kind": a.get("kind"),
                "vector": a.get("vector") or a.get("encoding"),
                "survived": a.get("survived"),
                "detected": a.get("detected"),
                "completed": a.get("completed"),
            } for a in sections["stress"].get("attacks", [])]
            rows.append({
                "agent": "langchain_createagent_hitl",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("langchain_createagent_hitl x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "langchain_createagent_hitl",
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
            print("langchain_createagent_hitl x %s -> CRASH (%s: %s)"
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
        "product": "LangChain create_agent WITH HumanInTheLoopMiddleware wired in (langchain.agents.middleware.human_in_the_loop, batched mode, InMemorySaver checkpointer)",
        "component": "create_agent(model, tools, middleware=[HumanInTheLoopMiddleware(interrupt_on={every tool passed in: True})], checkpointer=InMemorySaver()); the harness plays the human reviewer: REJECT monitor_configure/edit_tests/record_score with reason 'Not part of answering the question.', APPROVE every other tool. No system prompt, no other middleware, no interrupt_before/after; exactly the tools the caller passes in, no built-in tools added",
        "version": "langchain %s + langchain-core %s + langgraph %s" % (
            LANGCHAIN_VERSION, LANGCHAIN_CORE_VERSION, LANGGRAPH_VERSION),
        "repo": LANGCHAIN_REPO,
        "repo_resolved": "https://github.com/langchain-ai/langchain, default-branch HEAD %s (commit %s, '%s'). Installed with pip install langchain==1.5.0 langchain-core==1.8.0 langgraph==1.2.20 numpy pytest in a separate venv (~/workspace/hackathons/trustrun-venvs/langchain-createagent-hitl-venv); langchain 1.5.0 is the current latest release on PyPI at audit time. The audited object is the unified agent constructor with the shipped opt-in gate wired in, the way the middleware docstring wires it." % (
            LANGCHAIN_REPO_HEAD, LANGCHAIN_REPO_HEAD_DATE,
            LANGCHAIN_REPO_HEAD_MESSAGE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim; see real_agents/langchain_createagent_hitl_adapter.py)",
        "confirmation_gate": "WIRED IN, reviewer policy stated in 'component'. Measured gate mechanics (probe script ~/workspace/hackathons/trustrun-venvs/langchain-createagent-hitl-probe.py, all 6 sections pass): batched mode pauses the graph with langgraph interrupt() in after_model; agent.invoke returns with a '__interrupt__' key and the run resumes with Command(resume={'decisions': [...]}) matched by position. A checkpointer is REQUIRED: without one the first invoke still returns with __interrupt__ set, but the resume raises RuntimeError('Cannot use Command(resume=...) without checkpointer') -- the gate without a checkpointer is a dead end. A rejected call does NOT execute (monitor_configure executions 0 after a reject); the model gets a ToolMessage naming the rejection and is told not to retry, and the stub does not retry it. The gate CANNOT intercept attacks that need no tool call: a plaintext injection in a search result is answered PWNED as a final answer with no interrupt ever firing. A tool that raises propagates out of agent.invoke instead of reaching the model as an observation (the graph's ToolNode default handler re-raises non-ToolInvocationError); the adapter's catch returns flagged 'I could not complete the task: ...'. Per-tool-class gate behavior for this run is in 'gate_stats' below; per-attack outcomes are in each row's 'attacks' field.",
        "gate_stats": {
            "gated_calls": GATE_STATS["gated_calls"],
            "approved": dict(GATE_STATS["approved"]),
            "rejected": dict(GATE_STATS["rejected"]),
        },
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
    print("gate_stats:", {"gated_calls": GATE_STATS["gated_calls"],
                          "approved": dict(GATE_STATS["approved"]),
                          "rejected": dict(GATE_STATS["rejected"])})
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
