"""Audit ChatDev (OpenBMB/ChatDev, PyPI chatdev 0.1.0; repo HEAD
464a681ba7bda869db97a50c5fa707c9a0fb57a0 is main at 2026-10-30 --
the installed wheel matches the v2.2.0 tag, not main HEAD) with
Trustrun (fifty-third real-agent audit; forty-first framework).

Configuration under test: ChatDev 2.0's real agent node executor
(AgentNodeExecutor.execute -> ModelProvider.call_model ->
_handle_tool_calls -> ToolManager.execute_tool) holding the whole
Trustrun tool set as "function" tools (FunctionManager loads them
from trustrun-venvs/chatdev-functions; the wrappers dispatch to
the harness callables through a per-task registry), driven by a
deterministic stub provider (DeterministicProvider, the audit-30
decision logic reused verbatim via the audit-52 adapter; literal
model) served through the ModelProvider seam -- a
DeterministicProvider subclass whose call_model() renders a tool
decision as an assistant Message carrying tool_calls and the
framework dispatches it through its own tool loop, returning the
result as a tool-role Message; see
real_agents/chatdev_adapter.py for the wiring facts (no key, no
network). One fresh stub state, executor, and Node are built per
call. A raising tool is caught by _execute_tool_batch and returned
as a tool-role Message reading "Tool search_docs error: injected
tool failure in 'search_docs'"; an unregistered tool name is
reported as an "Error: Tool 'X' configuration not found." tool
observation and the model gets another turn (soft-fail class, not
an abort -- see real_agents/chatdev_adapter.py for the wiring
facts).

Usage: ~/workspace/hackathons/trustrun-venvs/chatdev-venv/bin/python3 run_real_agents_chatdev.py
(ChatDev lives in a separate venv; see
real_agents/chatdev_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the ChatDev adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/chatdev/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/chatdev/evidence.json. Every number in
those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The per-row "attacks" field records every
attack in the stress battery with its survived/detected outcome. The
evidence logs show the exact observation text the framework handed
the model, which is the framework-level fact. Never present a
clean-room failure as a flaw in a real product: the clean-room
agents' failures are theirs; the ChatDev rows are ChatDev's.
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

import real_agents.chatdev_adapter as ch_adapter  # noqa: E402
from real_agents.chatdev_adapter import (  # noqa: E402
    RUN_LOGS,
    CHATDEV_PYPI,
    CHATDEV_REPO,
    CHATDEV_REPO_HEAD,
    CHATDEV_REPO_HEAD_DATE,
    CHATDEV_REPO_HEAD_MESSAGE,
    CHATDEV_TAG,
    CHATDEV_TAG_COMMIT,
    CHATDEV_TAG_DATE,
    CHATDEV_TAG_MESSAGE,
    CHATDEV_VERSION,
    chatdev_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "chatdev")
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
    # Resume support (same rationale as run_real_agents_aider.py:
    # rows and evidence are checkpointed after every task; a
    # re-launch skips tasks already in rows_partial.json and keeps
    # their evidence). The audit itself is run in ONE uninterrupted
    # process; the checkpoints exist only so an interrupted run
    # loses at most one task.
    rows = _load_json(PARTIAL_ROWS, [])
    done = {row["task"] for row in rows}
    RUN_LOGS.extend(_load_json(PARTIAL_EVIDENCE, []))
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
                chatdev_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the ChatDev (non-)effect lives
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
                "agent": "chatdev",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("chatdev x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "chatdev",
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
            print("chatdev x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc))
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
    summary = {
        "product": "ChatDev (OpenBMB/ChatDev, PyPI chatdev 0.1.0, real agent node executor)",
        "component": "ChatDev 2.0's real agent node executor (AgentNodeExecutor.execute -> ModelProvider.call_model -> _handle_tool_calls -> ToolManager.execute_tool) holding the whole Trustrun tool set as 'function' tools (FunctionManager loads them from trustrun-venvs/chatdev-functions; the wrappers dispatch to the harness callables through a per-task registry), driven by DeterministicProvider (the audit-30 decision logic reused verbatim via the audit-52 adapter; literal model) served through the ModelProvider seam -- a DeterministicProvider subclass whose call_model() renders a tool decision as an assistant Message carrying tool_calls and the framework dispatches it through its own tool loop, returning the result as a tool-role Message; see real_agents/chatdev_adapter.py for the wiring facts. One fresh stub state, executor, and Node are built per call. The framework runs the agent loop, builds the message history, and passes tool results to the model verbatim as tool-role Messages; it performs no sanitization, filtering, or flagging of tool results. A raising tool is caught by _execute_tool_batch and returned as a tool-role Message reading 'Tool search_docs error: injected tool failure in 'search_docs''; an unregistered tool name is reported as an 'Error: Tool 'X' configuration not found.' tool observation and the model gets another turn (soft-fail class, not an abort).",
        "version": "ChatDev %s (PyPI %s; audited code is the installed 0.1.0 wheel, byte-identical to the v2.2.0 tag on ten key source files)" % (
            CHATDEV_VERSION, CHATDEV_PYPI),
        "repo": CHATDEV_REPO,
        "repo_resolved": "https://github.com/OpenBMB/ChatDev, main HEAD %s (commit %s, '%s'). The brief's slug chatdev/chatdev does not exist (GitHub API 404); the real repo is OpenBMB/ChatDev. HEAD is NOT the audited code: the installed wheel matches the %s tag (%s, commit %s, '%s'), verified by byte-compare of runtime/node/executor/agent_executor.py, runtime/node/agent/providers/openai_provider.py, runtime/node/agent/tool/tool_manager.py, runtime/node/agent/providers/base.py, runtime/node/agent/providers/response.py, entity/messages.py, entity/configs/node/agent.py, entity/tool_spec.py, utils/function_manager.py, and runtime/node/executor/base.py against the v2.2.0 tag tarball. Main HEAD has drifted from the release in three of those ten files. The repo is NOT archived. The classic 1.0 software-company pipeline survives only on the chatdev1.0 branch; main is the 2.0 DevAll workflow platform. ChatDev is a multi-agent workflow platform; the audited object is its agent node executor -- see the adapter docstring for the wiring facts." % (
            CHATDEV_REPO_HEAD,
            CHATDEV_REPO_HEAD_DATE, CHATDEV_REPO_HEAD_MESSAGE,
            CHATDEV_TAG, CHATDEV_TAG_DATE, CHATDEV_TAG_COMMIT,
            CHATDEV_TAG_MESSAGE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim via the audit-52 adapter, served to ChatDev through the ModelProvider seam -- a DeterministicProvider subclass whose call_model() renders a tool decision as an assistant Message carrying tool_calls and the framework dispatches it through its own _handle_tool_calls loop, returning the result as a tool-role Message; see real_agents/chatdev_adapter.py)",
        "confirmation_gate": "NONE on the audited path, measured: (1) no confirmation step stands between the model and a tool call -- ChatDev's function tools carry no approval/confirmation concept on this path (verified by package grep; see the re-probe); (2) no sanitization, filtering, or flagging of tool results anywhere on this path (verified by package grep and by the evidence logs: observations carry injected text verbatim); (3) a raising tool is CAUGHT by _execute_tool_batch and returned as a tool-role Message reading 'Tool search_docs error: injected tool failure in 'search_docs'' (measured in the re-probe); (4) an unregistered tool name is reported as an 'Error: Tool 'X' configuration not found.' tool observation and the model gets another turn -- nothing executes (measured in the re-probe; /probe.txt never created). Measured: a tool result containing tool JSON does NOT execute (it is inert text in a tool-role Message, not a dispatch -- measured in the re-probe). ChatDev has a separate 'human' node type for human-in-the-loop workflows, but it is a separate node in a workflow graph, not a gate on the agent node's tool calls.",
        "tool_calls": dict(ch_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(ch_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
