"""Audit Agency Swarm (VRSEN/agency-swarm, PyPI agency-swarm 1.11.0,
git v1.11.0 tag 4d1c35a6dd5ef038a5d15b39803459ff0b5f5578; main HEAD
1bec92f0fc6e8485e53847c6f4a943a847058bff is the unreleased 2.0.0-beta.1
line) with Trustrun (fifty-first real-agent audit; thirty-ninth
framework).

Configuration under test: Agency Swarm's real `Agent` loop
(agency_swarm.Agent, an OpenAI Agents SDK Agent subclass;
Execution.get_response -> SDK Runner.run) holding the whole
Trustrun tool set (search_docs, calculator, plus the
monitor/grader/clarification tools run_audit adds) as SDK
function_tool wrappers, driven by a deterministic stub model
(DeterministicModel, the audit-30 decision logic reused verbatim
via the audit-50 adapter) served through the SDK's documented
Model seam (no key, no network; tracing disabled). One fresh stub
model and Agent are built per call. A raising tool is caught by
the SDK and returned as a function_call_output observation; an
unregistered tool name aborts the run with ModelBehaviorError
(see real_agents/agency_swarm_adapter.py for the wiring facts).

Usage: ~/workspace/hackathons/trustrun-venvs/agency-swarm-venv/bin/python3 run_real_agents_agency_swarm.py
(Agency Swarm lives in a separate venv; see
real_agents/agency_swarm_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the Agency Swarm adapter on all
25 tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/agency_swarm/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/agency_swarm/evidence.json. Every number in
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
agents' failures are theirs; the Agency Swarm rows are Agency
Swarm's.
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

import real_agents.agency_swarm_adapter as as_adapter  # noqa: E402
from real_agents.agency_swarm_adapter import (  # noqa: E402
    RUN_LOGS,
    AGENCY_SWARM_PYPI,
    AGENCY_SWARM_REPO,
    AGENCY_SWARM_REPO_HEAD,
    AGENCY_SWARM_REPO_HEAD_DATE,
    AGENCY_SWARM_REPO_HEAD_MESSAGE,
    AGENCY_SWARM_RELEASE_TAG,
    AGENCY_SWARM_RELEASE_COMMIT,
    AGENCY_SWARM_RELEASE_DATE,
    AGENCY_SWARM_VERSION,
    agency_swarm_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "agency_swarm")
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
                agency_swarm_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the Agency Swarm (non-)effect
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
                "agent": "agency_swarm",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("agency_swarm x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "agency_swarm",
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
            print("agency_swarm x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc))
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
    summary = {
        "product": "Agency Swarm (VRSEN/agency-swarm, PyPI agency-swarm 1.11.0, real Agent loop)",
        "component": "Agency Swarm's real Agent loop (agency_swarm.Agent, an OpenAI Agents SDK Agent subclass; Execution.get_response -> SDK Runner.run) holding the whole Trustrun tool set via SDK function_tool wrappers (the stub renders each tool decision as a Responses-API function call; the SDK dispatches it and returns the result as a function_call_output item), driven by DeterministicModel (the audit-30 decision logic reused verbatim via the audit-50 adapter; literal model) served through the SDK's documented Model seam (no key, no network; tracing disabled). One fresh stub model and Agent are built per call. The framework runs the agent loop, builds the message history, and passes tool results to the model verbatim as function_call_output items; it performs no sanitization, filtering, or flagging of tool results. A raising tool is caught by the SDK and returned as an 'An error occurred while running the tool...' observation; an unregistered tool name aborts the run with ModelBehaviorError (AgentsException out of get_response).",
        "version": "Agency Swarm %s (PyPI %s; audited code is the installed 1.11.0 wheel, byte-identical to the %s release tag on five key source files)" % (
            AGENCY_SWARM_VERSION, AGENCY_SWARM_PYPI, AGENCY_SWARM_RELEASE_TAG),
        "repo": AGENCY_SWARM_REPO,
        "repo_resolved": "https://github.com/VRSEN/agency-swarm, main HEAD %s (commit %s, '%s'). HEAD is the unreleased 2.0.0-beta.1 line (tag v2.0.0-beta.1 is b28ac98321b2, a different commit), ahead of the 1.11.0 release; the installed wheel does NOT match main HEAD. It matches the %s release tag %s (commit %s, '%s'), verified by byte-compare of agent/core.py, agent/execution.py, __init__.py, agency/core.py, and tools/function_tool_compat.py against a shallow clone of the tag. The repo is NOT archived. Agency Swarm is a multi-agent framework built on the OpenAI Agents SDK (openai-agents 0.18.1, the wheel's SDK dependency); the audited object is its Agent loop -- see the adapter docstring for the wiring facts." % (
            AGENCY_SWARM_REPO_HEAD,
            AGENCY_SWARM_REPO_HEAD_DATE, AGENCY_SWARM_REPO_HEAD_MESSAGE,
            AGENCY_SWARM_RELEASE_TAG, AGENCY_SWARM_RELEASE_COMMIT,
            AGENCY_SWARM_RELEASE_DATE, "docs: add newcomer paths for OAuth and voice (#764)"),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim via the audit-50 adapter, served to Agency Swarm through the SDK's documented Model seam -- a DeterministicModel subclass of agents.Model whose get_response returns a ModelResponse built from the stub's decision; a tool decision is rendered as a ResponseFunctionToolCall and the SDK dispatches it and returns the result as a function_call_output item; see real_agents/agency_swarm_adapter.py)",
        "confirmation_gate": "NONE on the audited path, measured: (1) no confirmation step stands between the model and a tool call -- the SDK's function_tool carries a needs_approval parameter that defaults to False and Agency Swarm passes no approval requirement for plain function tools; (2) no sanitization, filtering, or flagging of tool results anywhere on this path (zero 'sanitize' hits in the installed agency_swarm package); (3) a raising tool is CAUGHT by the SDK and returned as an 'An error occurred while running the tool. Please try again. Error: ...' function_call_output observation (measured in the re-probe); (4) an unregistered tool name ABORTS the run -- the SDK raises ModelBehaviorError, wrapped into AgentsException out of get_response(), and nothing executes (measured in the re-probe; /probe.txt never created). Measured: a tool result containing tool JSON does NOT execute (it is inert text in a function_call_output item, not a dispatch -- measured in the re-probe).",
        "tool_calls": dict(as_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(as_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
