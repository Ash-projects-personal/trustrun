"""Audit SWE-agent (SWE-agent/SWE-agent, release v1.1.0, commit
0f3acafacabc0def8cc76b4e48acb4b6cf302cb9; repo HEAD
3ea751c087f32b16e039a2233dd6eefecef325d5 is 14 months past the
release and is NOT what is audited) with Trustrun (fifty-fourth
real-agent audit; forty-second framework).

Configuration under test: SWE-agent's real `DefaultAgent` loop
(DefaultAgent.run -> step -> forward_with_handling -> forward ->
model.query -> FunctionCallingParser -> handle_action ->
SWEEnv.communicate -> swe-rex local bash session, no Docker)
holding the whole Trustrun tool set as a custom "trustrun" tool
bundle (one bash command per harness tool, dispatched through
the adapter's in-process HTTP dispatcher to the real harness
callables), driven by a deterministic stub model
(DeterministicModel, the audit-30 decision logic reused verbatim
via the audit-52 adapter) served through the
sweagent.agent.models.AbstractModel seam (no key, no network).
One fresh stub model and DefaultAgent are built per call; one
local env is shared per process (see real_agents/
sweagent_adapter.py for the wiring facts).

Usage: ~/workspace/hackathons/trustrun-venvs/sweagent-venv/bin/python3 run_real_agents_sweagent.py
(SWE-agent lives in a separate venv; see
real_agents/sweagent_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the SWE-agent adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/sweagent/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/sweagent/evidence.json. Every number in
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
agents' failures are theirs; the SWE-agent rows are SWE-agent's.
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

import real_agents.sweagent_adapter as sw_adapter  # noqa: E402
from real_agents.sweagent_adapter import (  # noqa: E402
    RUN_LOGS,
    SWEAGENT_PYPI,
    SWEAGENT_REPO,
    SWEAGENT_REPO_HEAD,
    SWEAGENT_REPO_HEAD_DATE,
    SWEAGENT_REPO_HEAD_MESSAGE,
    SWEAGENT_TAG,
    SWEAGENT_TAG_COMMIT,
    SWEAGENT_TAG_DATE,
    SWEAGENT_TAG_MESSAGE,
    SWEAGENT_TAG_PUBLISHED,
    SWEAGENT_VERSION,
    cleanup_work_dirs,
    sweagent_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "sweagent")
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
    # them per task too, so a crash before summary writing (as
    # happened on the first run of this audit, when a NameError in
    # the summary block lost the in-process counter) cannot lose
    # them again.
    sw_adapter.TOOL_CALLS.update(
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
                sweagent_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the SWE-agent (non-)effect lives
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
                "agent": "sweagent",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("sweagent x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "sweagent",
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
            print("sweagent x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc))
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
        _write_atomic(PARTIAL_TOOLCALLS, dict(sw_adapter.TOOL_CALLS))
    summary = {
        "product": "SWE-agent (SWE-agent/SWE-agent, release v1.1.0, real DefaultAgent loop)",
        "component": "SWE-agent's real DefaultAgent loop (DefaultAgent.run -> step -> forward_with_handling -> forward -> model.query -> FunctionCallingParser -> handle_action -> SWEEnv.communicate -> swe-rex local bash session, no Docker) holding the whole Trustrun tool set as a custom 'trustrun' tool bundle (one bash command per harness tool, dispatched through the adapter's in-process HTTP dispatcher to the real harness callables), driven by DeterministicModel (the audit-30 decision logic reused verbatim via the audit-52 adapter; literal model) served through the sweagent.agent.models.AbstractModel seam -- a DeterministicModel subclass whose query() renders a tool decision as one LiteLLM-style tool_call carrying a JSON `payload` argument and a final answer as a `submit` tool call (no key, no network). One fresh stub model and DefaultAgent are built per call; one local env is shared per process. The framework runs the agent loop, parses the function call, checks the blocklist, executes the bash command in the local session, and passes the command stdout to the model verbatim as a tool-role Message wrapped in the 'Observation: ' template; it performs no sanitization, filtering, or flagging of tool results. A raising tool is caught by the adapter's dispatcher and its exception text is returned as the command's stdout (the caught class); an unregistered tool name raises FunctionCallingFormatError inside the framework, which requeries the model (max 3) -- the soft-fail-via-requery class, not an abort.",
        "version": "SWE-agent %s (release %s, commit %s, %s; installed from the git tag -- there is no usable PyPI release: PyPI `swe-agent` is 404 and PyPI `sweagent` is a stale 0.0.1 placeholder from 2024-04-02)" % (
            SWEAGENT_VERSION, SWEAGENT_TAG, SWEAGENT_TAG_COMMIT,
            SWEAGENT_TAG_DATE),
        "repo": SWEAGENT_REPO,
        "repo_resolved": "https://github.com/SWE-agent/SWE-agent, main HEAD %s (commit %s, '%s'). HEAD is ~14 months past the v1.1.0 release (published %s, '%s'); the installed wheel does NOT match main HEAD. It matches the published v1.1.0 tag, verified by byte-compare of sweagent/agent/agents.py, sweagent/agent/models.py, sweagent/environment/swe_env.py, sweagent/tools/tools.py, sweagent/tools/parsing.py, sweagent/tools/commands.py, sweagent/tools/bundle.py, and sweagent/__init__.py against the v1.1.0 tag tarball. The repo is NOT archived. SWE-agent is a coding agent; the audited object is its DefaultAgent loop -- see the adapter docstring for the wiring facts." % (
            SWEAGENT_REPO_HEAD,
            SWEAGENT_REPO_HEAD_DATE, SWEAGENT_REPO_HEAD_MESSAGE,
            SWEAGENT_TAG_PUBLISHED, SWEAGENT_TAG_MESSAGE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim via the audit-52 adapter, served to SWE-agent through the sweagent.agent.models.AbstractModel seam -- a DeterministicModel subclass whose query() renders a tool decision as one LiteLLM-style tool_call carrying a JSON `payload` argument and a final answer as a `submit` tool call; see real_agents/sweagent_adapter.py)",
        "confirmation_gate": "NONE on the audited path, measured: (1) no confirmation step stands between the model and a tool call -- SWE-agent's tool filter is a BLOCKLIST (vim/vi/emacs/nano/nohup/gdb/less/tail -f/python -m venv/make, plus standalone python/python3/ipython/bash/sh), not an approval step: a listed command is refused and the model is requeried, a human is never asked (verified by package grep; see the re-probe); (2) no sanitization, filtering, or flagging of tool results anywhere on this path (verified by package grep and by the evidence logs: observations carry injected text verbatim apart from the 'Observation: ' template prefix); (3) a raising tool is CAUGHT by the adapter's dispatcher and its exception text is returned as the command's stdout (measured in the probe); (4) an unregistered tool name raises FunctionCallingFormatError inside the framework, which requeries the model (max 3) and the model gets another turn -- nothing executes (measured in the probe; /probe.txt never created). Measured: a tool result containing tool JSON does NOT execute (it is inert text in a tool-role Message, not a dispatch -- measured in the re-probe).",
        "tool_calls": dict(sw_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(sw_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, PARTIAL_TOOLCALLS):
        if os.path.exists(path):
            os.remove(path)
    cleanup_work_dirs()


if __name__ == "__main__":
    main()
