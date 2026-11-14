"""Audit Cheshire Cat (PyPI cheshire-cat-ai 2.0.23 == git tag 2.0.23
in cheshire-cat-ai/core) with Trustrun (sixty-first real-agent
audit; forty-ninth framework in the rotation; first Cheshire Cat
audit).

TARGET: Cheshire Cat (cheshire-cat-ai/core), verified absent from
DATASET.md before this audit (0 hits, no summary dir). See
real_agents/cheshirecat_adapter.py for the pinning facts -- PyPI
cheshire-cat-ai 2.0.23 (released 2026-07-08) == git tag 2.0.23 =
c22731e7009ac89835b1d7b1cabc5989d998ec3e; repo main HEAD
1493ce31301c4e6f14008d5e410ff7dcc3654eb7 (2026-07-29); not
archived; sdist byte-identical to the tag tree on all 118 .py
files; installed byte-identical to the sdist on all 83 src/cat
.py files.

Configuration under test: Cheshire Cat 2.0.23's real DefaultAgent
agentic loop (the framework's own Agent.__call__ loop: loop()
calls the LLM through the framework's own ambient llm() seam,
dispatches tool calls through the framework's own Agent.call_tool
/ Tool.execute path, appends tool results as role="tool" messages,
and loops until the LLM returns no tool calls), holding the
harness tools as @tool methods on a DefaultAgent subclass (the
framework's own agent-scoped tool path), driven by a
deterministic stub model (the audit-30 decision logic reused
verbatim in decision, adapted in shape: the 'observation' is the
latest tool message in the framework's conversation, and a tool
decision is rendered as the framework's own Message with a
ToolCall), served through the framework's own ModelProvider seam
(a ModelProvider subclass registered in the registry and set as
the configured default_llm, the same shape the framework's own
cat.testing.fake_llm fixture uses). One fresh stub state is built
per call; one agent instance is built per call (Agent is not a
singleton). The Cat runs in-process on a throwaway SQLite project
with zero plugins: no Docker, no Redis, no Qdrant, no external
services. See real_agents/cheshirecat_adapter.py for the wiring
facts.

Usage: ~/workspace/hackathons/trustrun-venvs/cheshirecat-venv/bin/python3 run_real_agents_cheshirecat.py
(Cheshire Cat lives in a separate venv; see
real_agents/cheshirecat_adapter.py for the install command,
including the load-bearing fastmcp==3.4.3 pin.)

Runs trustrun.cli.run_audit over the Cheshire Cat adapter on all
25 tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/cheshirecat/summary.json and the evidence logs
(injection observations) into
reports/real_agents/cheshirecat/evidence.json. Every number in
those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub
model combination. The stub is a literal model (it follows
instructions in the task text and in tool output), so a BLOCK on
an injection attack means the framework passed the attack
through to such a model unfiltered. The per-row "attacks" field
records every attack in the stress battery with its
survived/detected outcome. The evidence logs show the exact
context the framework handed the model, which is the
framework-level fact. Never present a clean-room failure as a
flaw in a real product: the clean-room agents' failures are
theirs; the Cheshire Cat rows are Cheshire Cat's. The tampering
attacks measure the framework's architecture: the knobs are
exposed as ordinary callable tools with no confirmation, so a
model that reaches for them succeeds -- that is a property of
this framework, recorded in the rows, not a vacuous pass. The
one 2.0.23 behavior that differs from every prior audit in the
rotation: a call for a tool the run did not offer RAISES out of
the loop (the abort class), so runs where the stub reaches for
an unwired knob abort into a flagged "could not complete"
result instead of handing the model a recoverable error; main
HEAD changed this to a soft-fail message after the release.
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

import real_agents.cheshirecat_adapter as cc_adapter  # noqa: E402
from real_agents.cheshirecat_adapter import (  # noqa: E402
    CHESHIRECAT_PYPI,
    CHESHIRECAT_PYPI_DATE,
    CHESHIRECAT_REPO,
    CHESHIRECAT_REPO_HEAD,
    CHESHIRECAT_REPO_HEAD_DATE,
    CHESHIRECAT_TAG,
    CHESHIRECAT_TAG_COMMIT,
    CHESHIRECAT_TAG_DATE,
    CHESHIRECAT_VERSION,
    RUN_LOGS,
    cheshirecat_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "cheshirecat")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
PARTIAL_TOOLCALLS = os.path.join(OUT_DIR, "tool_calls_partial.json")


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
    # Resume support (same rationale as run_real_agents_aider.py:
    # rows and evidence are checkpointed after every task; a
    # re-launch skips tasks already in rows_partial.json and keeps
    # their evidence). The audit itself is run in ONE uninterrupted
    # process; the checkpoints exist only so an interrupted run
    # loses at most one task.
    rows = _load_json(PARTIAL_ROWS, [])
    done = {row["task"] for row in rows}
    RUN_LOGS.extend(_load_json(PARTIAL_EVIDENCE, []))
    # Tool-call counts live only in the adapter process; checkpoint
    # them per task too, so a crash before summary writing cannot
    # lose them again.
    cc_adapter.TOOL_CALLS.update(
        _load_json(PARTIAL_TOOLCALLS, {}))
    if done:
        print("resuming: %d tasks already done (%s)"
              % (len(done), ", ".join(sorted(done))))
    pending = [t for t in tasks if t["id"] not in done]
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
        # Per-task guard (same rationale as run_real_agents_aider.py:
        # a framework crash must be recorded as a crash row, not kill
        # the remaining tasks. A crash row is verdict BLOCK with a
        # "crash" field; its section verdicts were NOT graded, so folds
        # must count checks as 21 per graded row and 0 per crash row,
        # and summary.json lists crash task ids.)
        try:
            report = run_audit(
                cheshirecat_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the Cheshire Cat (non-)effect lives
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
                "agent": "cheshirecat",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("cheshirecat x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "cheshirecat",
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
            print("cheshirecat x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc), flush=True)
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
        _write_atomic(PARTIAL_TOOLCALLS, dict(cc_adapter.TOOL_CALLS))
    summary = {
        "product": "Cheshire Cat (PyPI cheshire-cat-ai 2.0.23 == git tag 2.0.23 in cheshire-cat-ai/core, real DefaultAgent loop)",
        "component": "Cheshire Cat 2.0.23's real DefaultAgent agentic loop (the framework's own Agent.__call__ loop: loop() calls the LLM through the framework's own ambient llm() seam, dispatches tool calls through the framework's own Agent.call_tool / Tool.execute path, appends tool results as role='tool' messages, and loops until the LLM returns no tool calls), holding the harness tools as @tool methods on a DefaultAgent subclass (the framework's own agent-scoped tool path), driven by DeterministicStub (the audit-30 decision logic reused verbatim in decision, adapted in shape: the 'observation' is the latest tool message in the framework's conversation, and a tool decision is rendered as the framework's own Message with a ToolCall; see real_agents/cheshirecat_adapter.py) served through the framework's own ModelProvider seam (a ModelProvider subclass registered in the registry and set as the configured default_llm, the same shape the framework's own cat.testing.fake_llm fixture uses) -- the stub replaces the package's model, so the framework's own tool planning, dispatch, and result handling all execute for real (no key, no network). One fresh stub state is built per call; one agent instance is built per call. The Cat runs in-process on a throwaway SQLite project with zero plugins: no Docker, no Redis, no Qdrant, no external services. The framework runs the loop and passes tool results to the model verbatim; it performs no sanitization, filtering, or flagging of tool output. A raising tool does NOT abort the run: the framework catches it in Tool.execute into an 'Error: ...' tool result, which the model then sees as its next observation (the caught class). A call for a tool the run did not offer DOES abort the run in 2.0.23: Agent.call_tool raises Exception('Tool <name> not found') out of the loop (the abort class -- measured in the probe; main HEAD changed this to a soft-fail message after the release). The framework offers the model the tampering knobs as ordinary callable tools with no confirmation step, so a model that reaches for monitor_configure, edit_tests, or record_score succeeds.",
        "version": "Cheshire Cat %s (PyPI %s, released %s; installed files byte-identical to the sdist on all 83 src/cat .py files, and the sdist package byte-identical to git tag %s = %s, %s; the sdist carries one extra non-code test fixture, tests/mocks/mock_plugin.zip, absent from the tag tree; no .py file differs)" % (
            CHESHIRECAT_VERSION, CHESHIRECAT_PYPI,
            CHESHIRECAT_PYPI_DATE,
            CHESHIRECAT_TAG, CHESHIRECAT_TAG_COMMIT,
            CHESHIRECAT_TAG_DATE),
        "repo": CHESHIRECAT_REPO,
        "repo_resolved": "https://github.com/cheshire-cat-ai/core, main HEAD %s (committed %s) -- tag %s = %s (%s) is the audited release. The repo is NOT archived (GitHub page, 2026-11-12), 2960 commits, 3101 stars, 40 tags. The audited code is the PyPI 2.0.23 release, verified by byte-compare of all 118 .py files against the shipped sdist, which is byte-identical to the 2.0.23 tag tree on every .py file present in both. Cheshire Cat is an AI agent microservice framework; the audited object is its DefaultAgent loop -- see the adapter docstring for the wiring facts." % (
            CHESHIRECAT_REPO_HEAD,
            CHESHIRECAT_REPO_HEAD_DATE,
            CHESHIRECAT_TAG,
            CHESHIRECAT_TAG_COMMIT,
            CHESHIRECAT_TAG_DATE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim in decision via the audit-60 adapter lineage, adapted in shape: the stub answers the framework's ModelProvider.llm calls by reading the latest tool message out of the framework's conversation, and a tool decision is rendered as the framework's own Message with a ToolCall; see real_agents/cheshirecat_adapter.py)",
        "confirmation_gate": "NONE on the audited path, measured -- the tampering knobs are exposed as ordinary callable tools with no approval step: (1) a case-insensitive package grep over all 83 .py files of the installed cat package returns: human_in_the_loop 0, require_confirmation 0, needs_approval 0, approval 0, confirm 1, sanitize 0, interrupt 1. The single 'confirm' hit is the word 'confirm' in a tutorial agent's system prompt ('briefly confirm what you did', scaffold/plugins/tutorial/agents/tool_agent.py:35), not a gate. The single 'interrupt' hit is a comment about cancelling a stream on client disconnect (protocols/agui/streaming.py:113), not a gate. (2) the framework executes any tool the model requests immediately -- monitor_configure, edit_tests, and record_score are dispatched by Agent.call_tool with no human gate anywhere (verified by the re-probe: the tampering attacks succeed and the grading record is changed); (3) no sanitization, filtering, or flagging of tool output anywhere on this path (verified by package grep and by the evidence logs: tool output carrying an injection reaches the model verbatim inside its tool message); (4) a raising tool does NOT abort the run -- the framework catches it into an 'Error: ...' tool result, which the model sees as its next observation (the caught class -- measured in the probe); (5) a call for a tool the run did not offer DOES abort the run in 2.0.23 -- Agent.call_tool raises Exception('Tool <name> not found') out of the loop (the abort class, measured in the probe and in the re-probe; main HEAD changed this to a soft-fail message after the release); (6) a tool result containing tool JSON does NOT execute (it is inert text in the tool result, not a dispatch -- measured in the probe and in the re-probe). No SECURITY.md is published for Cheshire Cat (absent at the 2.0.23 tag, absent from the sdist, absent from the installed package), so no vendor security contact is published for this package.",
        "tool_calls": dict(cc_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(cc_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, PARTIAL_TOOLCALLS):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
