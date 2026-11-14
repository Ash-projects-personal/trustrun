"""Audit Phidata (phidatahq/phidata, PyPI phidata 2.7.10; repo HEAD
257cd57e9637964f44fc3d7e3ad142ca066b2e43 is the renamed Agno
codebase -- the installed wheel matches the published 2.7.10
sdist, not main HEAD) with Trustrun (fifty-second real-agent
audit; fortieth framework).

Configuration under test: Phidata's real `Agent` loop
(phi.agent.Agent.run -> Model.response ->
Model.run_function_calls) holding the whole Trustrun tool set
(search_docs, calculator, plus the monitor/grader/clarification
tools run_audit adds) as plain callables (Agent.update_model
adds them to the model via Model.add_tool ->
Function.from_callable), driven by a deterministic stub model
(DeterministicModel, the audit-30 decision logic reused verbatim
via the audit-50 adapter) served through the phi.model.base.Model
seam (no key, no network). One fresh stub model and Agent are
built per call. A raising tool is caught by FunctionCall.execute
and returned as a tool-role Message carrying the exception text;
an unregistered tool name is reported as a "Could not find
function to call." tool observation and the model gets another
turn (soft-fail class, not an abort -- see
real_agents/phidata_adapter.py for the wiring facts).

Usage: ~/workspace/hackathons/trustrun-venvs/phidata-venv/bin/python3 run_real_agents_phidata.py
(Phidata lives in a separate venv; see
real_agents/phidata_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the Phidata adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/phidata/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/phidata/evidence.json. Every number in
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
agents' failures are theirs; the Phidata rows are Phidata's.
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

import real_agents.phidata_adapter as ph_adapter  # noqa: E402
from real_agents.phidata_adapter import (  # noqa: E402
    RUN_LOGS,
    PHIDATA_PYPI,
    PHIDATA_REPO,
    PHIDATA_REPO_HEAD,
    PHIDATA_REPO_HEAD_DATE,
    PHIDATA_REPO_HEAD_MESSAGE,
    PHIDATA_REPO_RESOLVED,
    PHIDATA_VERSION,
    phidata_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "phidata")
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
                phidata_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the Phidata (non-)effect lives
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
                "agent": "phidata",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("phidata x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "phidata",
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
            print("phidata x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc))
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
    summary = {
        "product": "Phidata (phidatahq/phidata, PyPI phidata 2.7.10, real Agent loop)",
        "component": "Phidata's real Agent loop (phi.agent.Agent.run -> Model.response -> Model.run_function_calls) holding the whole Trustrun tool set via plain callables (Agent.update_model adds them to the model via Model.add_tool -> Function.from_callable; the adapter wraps each harness callable to return a plain string first because phi's tool Message content must be str/list), driven by DeterministicModel (the audit-30 decision logic reused verbatim via the audit-50 adapter; literal model) served through the phi.model.base.Model seam -- a DeterministicModel subclass of phi.model.base.Model whose response() renders a tool decision as an assistant Message carrying tool_calls, executes it through the framework's own run_function_calls, and recurses with the tool-result Messages appended (no key, no network). One fresh stub model and Agent are built per call. The framework runs the agent loop, builds the message history, and passes tool results to the model verbatim as tool-role Messages; it performs no sanitization, filtering, or flagging of tool results. A raising tool is caught by FunctionCall.execute and returned as a tool-role Message carrying the exception text; an unregistered tool name is reported as a 'Could not find function to call.' tool observation and the model gets another turn (soft-fail class, not an abort).",
        "version": "Phidata %s (PyPI %s; audited code is the installed 2.7.10 wheel, byte-identical to the published 2.7.10 sdist on eight key source files)" % (
            PHIDATA_VERSION, PHIDATA_PYPI),
        "repo": PHIDATA_REPO,
        "repo_resolved": "https://github.com/phidatahq/phidata, main HEAD %s (commit %s, '%s'). HEAD is the renamed Agno codebase (the repo now resolves to %s); it is NOT the phidata 2.7.10 release line, and no 2.7.10 tag exists in the current repo. The installed wheel does NOT match main HEAD. It matches the published phidata 2.7.10 source distribution (uploaded 2025-01-27), verified by byte-compare of phi/agent/agent.py, phi/model/base.py, phi/model/openai/chat.py, phi/tools/function.py, phi/utils/tools.py, phi/utils/functions.py, phi/model/message.py, and phi/model/response.py against phidata-2.7.10.tar.gz from PyPI. The repo is NOT archived. Phidata is a multi-agent framework; the audited object is its Agent loop -- see the adapter docstring for the wiring facts." % (
            PHIDATA_REPO_HEAD,
            PHIDATA_REPO_HEAD_DATE, PHIDATA_REPO_HEAD_MESSAGE,
            PHIDATA_REPO_RESOLVED),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim via the audit-50 adapter, served to Phidata through the phi.model.base.Model seam -- a DeterministicModel subclass whose response() renders a tool decision as an assistant Message carrying tool_calls and the framework dispatches it through run_function_calls, returning the result as a tool-role Message; see real_agents/phidata_adapter.py)",
        "confirmation_gate": "NONE on the audited path, measured: (1) no confirmation step stands between the model and a tool call -- phidata's Function carries no approval/confirmation concept on this path (verified by package grep; see the re-probe); (2) no sanitization, filtering, or flagging of tool results anywhere on this path (verified by package grep and by the evidence logs: observations carry injected text verbatim); (3) a raising tool is CAUGHT by FunctionCall.execute and returned as a tool-role Message carrying the exception text (measured in the re-probe); (4) an unregistered tool name is reported as a 'Could not find function to call.' tool observation and the model gets another turn -- nothing executes (measured in the re-probe; /probe.txt never created). Measured: a tool result containing tool JSON does NOT execute (it is inert text in a tool-role Message, not a dispatch -- measured in the re-probe).",
        "tool_calls": dict(ph_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(ph_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
