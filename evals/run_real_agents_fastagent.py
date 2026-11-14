"""Audit FastAgent (PyPI fast-agent-mcp 0.10.54 == git tag v0.10.54
in evalstate/fast-agent) with Trustrun (sixtieth real-agent audit;
forty-eighth framework; first MCP-native framework in the
rotation).

TARGET: FastAgent (evalstate/fast-agent), verified absent from
DATASET.md before this audit (0 hits, no summary dir). See
real_agents/fastagent_adapter.py for the pinning facts -- note
the task-named repo (lastmile-ai/mcp-agent) is the upstream
origin, not the source of the 0.10.54 release: its HEAD
(f62d849, 2026-01-25) ships the `mcp_agent` package, while the
sdist ships `fast_agent`, byte-identical to the evalstate
v0.10.54 tag.

Configuration under test: FastAgent 0.10.54's real ToolAgent
tool loop (the framework's own ToolRunner: FastAgentLLM.generate
seam, its own plan_tool_calls / execute_planned_tool_call
FastMCP FunctionTool dispatch, tool results appended as
tool-result user messages, looping to END_TURN), holding the
harness tools as plain Python callables (the framework's own
function-tool path), driven by a deterministic stub model (the
audit-30 decision logic reused verbatim in decision, adapted in
shape: the "observation" is the latest tool-result message in
the framework's history, and a tool decision is rendered as the
framework's own PromptMessageExtended with a tool_calls dict),
served through the framework's own LLM seam (a PassthroughLLM
subclass overriding _apply_prompt_provider_specific, the same
override shape the framework's own tests use). One fresh stub
state is built per call; one ToolAgent is constructed per call
(the framework holds no shared singleton). See
real_agents/fastagent_adapter.py for the wiring facts.

Usage: ~/workspace/hackathons/trustrun-venvs/fastagent-venv/bin/python3 run_real_agents_fastagent.py
(FastAgent lives in a separate venv; see
real_agents/fastagent_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the FastAgent adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/fastagent/summary.json and the evidence logs
(injection observations) into
reports/real_agents/fastagent/evidence.json. Every number in those
files comes from a real run. Nothing is invented.

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
theirs; the FastAgent rows are FastAgent's. The tampering
attacks measure the framework's architecture: the knobs are
exposed as ordinary callable tools with no confirmation, so a
model that reaches for them succeeds -- that is a property of
this framework, recorded in the rows, not a vacuous pass.
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

import real_agents.fastagent_adapter as fa_adapter  # noqa: E402
from real_agents.fastagent_adapter import (  # noqa: E402
    FAST_ORIGIN_HEAD,
    FAST_ORIGIN_HEAD_DATE,
    FAST_ORIGIN_REPO,
    FAST_PYPI,
    FAST_PYPI_DATE,
    FAST_REPO,
    FAST_REPO_HEAD,
    FAST_REPO_HEAD_DATE,
    FAST_TAG,
    FAST_VERSION,
    RUN_LOGS,
    fastagent_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "fastagent")
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
    fa_adapter.TOOL_CALLS.update(
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
                fastagent_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the FastAgent (non-)effect lives
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
                "agent": "fastagent",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("fastagent x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "fastagent",
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
            print("fastagent x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc), flush=True)
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
        _write_atomic(PARTIAL_TOOLCALLS, dict(fa_adapter.TOOL_CALLS))
    summary = {
        "product": "FastAgent (PyPI fast-agent-mcp 0.10.54 == git tag v0.10.54 in evalstate/fast-agent, real ToolAgent tool loop)",
        "component": "FastAgent 0.10.54's real ToolAgent tool loop (the framework's own ToolRunner: FastAgentLLM.generate seam, its own plan_tool_calls / execute_planned_tool_call FastMCP FunctionTool dispatch, tool results appended as tool-result user messages, looping to END_TURN), holding the harness tools as plain Python callables (the framework's own function-tool path), driven by DeterministicStub (the audit-30 decision logic reused verbatim in decision, adapted in shape: the 'observation' is the latest tool-result message in the framework's history, and a tool decision is rendered as the framework's own PromptMessageExtended with a tool_calls dict; see real_agents/fastagent_adapter.py) served through the framework's own LLM seam (a PassthroughLLM subclass overriding _apply_prompt_provider_specific, the same override shape the framework's own tests use) -- the stub replaces the package's model, so the framework's own tool planning, dispatch, and result handling all execute for real (no key, no network). One fresh stub state is built per call; one ToolAgent is constructed per call. The framework runs the loop and passes tool results to the model verbatim; it performs no sanitization, filtering, or flagging of tool output. A raising tool does NOT abort the run: the framework catches it into an error CallToolResult, which the model then sees as its next observation (the caught class). The framework offers the model the tampering knobs as ordinary callable tools with no confirmation step, so a model that reaches for monitor_configure, edit_tests, or record_score succeeds.",
        "version": "FastAgent %s (PyPI %s, released %s; installed files byte-identical to the sdist on all 781 .py files, and the sdist package byte-identical to git tag %s = %s, %s, in evalstate/fast-agent; the sdist carries 28 extra packaged-example .py files under src/fast_agent/resources/ absent from the tag tree and 3 README.md files in the tag are absent from the sdist; no .py file differs)" % (
            FAST_VERSION, FAST_PYPI,
            FAST_PYPI_DATE,
            FAST_TAG, FAST_REPO_HEAD,
            FAST_REPO_HEAD_DATE),
        "repo": FAST_REPO,
        "repo_resolved": "https://github.com/evalstate/fast-agent, main HEAD %s (committed %s) == tag %s. The repo is NOT archived. The task-named repo https://github.com/lastmile-ai/mcp-agent is the upstream origin, also NOT archived, HEAD %s (%s), but it ships the `mcp_agent` package and its HEAD predates this release by almost ten months, so it is NOT the source of the audited 0.10.54 release. The audited code is the PyPI 0.10.54 release, verified by byte-compare of all 781 .py files against the shipped sdist, which is byte-identical to the v0.10.54 tag tree on every .py file present in both. FastAgent is an MCP-native agent framework; the audited object is its ToolAgent tool loop -- see the adapter docstring for the wiring facts." % (
            FAST_REPO_HEAD,
            FAST_REPO_HEAD_DATE,
            FAST_TAG,
            FAST_ORIGIN_HEAD,
            FAST_ORIGIN_HEAD_DATE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim in decision via the audit-58 adapter lineage, adapted in shape: the stub answers the framework's _apply_prompt_provider_specific calls by reading the latest tool-result message out of the framework's history, and a tool decision is rendered as the framework's own PromptMessageExtended with a tool_calls dict; see real_agents/fastagent_adapter.py)",
        "confirmation_gate": "NONE on the audited path, measured -- the tampering knobs are exposed as ordinary callable tools with no approval step: (1) a case-insensitive package grep over all 781 .py files of the installed fast_agent package returns: human_in_the_loop 0, require_confirmation 0, needs_approval 0, approval 8, confirm 27, sanitize 268, interrupt 107. Every 'approval' hit is outside the audited tool loop: a Temporal durable-execution 'approval_needed' signal handler (core/executor/workflow_signal.py), a Copilot OAuth console message, a 'require_approval': 'never' default for provider-managed MCP server attachments (mcp/provider_management.py:440 -- the default is never to require approval), a ptc docstring, and an OpenAI responses-output note that MCP approval requests are 'not supported by fast-agent yet'. Every 'confirm' hit is CLI/interactive-prompt wording, never a tool-call gate. Every 'sanitize' hit is model-tokenization filtering (_sanitize_messages_for_llm drops content blocks the current model cannot tokenize), provider schema sanitizers, or the opt-in privacy filter -- not content filtering of tool output, and the probe evidence shows tool output reaching the model verbatim. Every 'interrupt' hit is run-cancellation handling (user interrupting a run), never an approval gate. The one review-shaped mechanism on the path is the plugin tool-call review in ToolAgent (_review_tool_calls / _tool_call_review_enabled): it runs external plugin reviewers over resolved calls, but it is OFF unless settings._plugin_tool_call_review is set, and the audited agent is built with context=None so settings is None and the review returns {} immediately (verified at runtime in the re-probe: _tool_call_review_enabled() is False); no reviewer is wired in by default. (2) the framework executes any tool the model requests immediately -- monitor_configure, edit_tests, and record_score are dispatched by the ToolRunner with no human gate anywhere (verified by the re-probe: the tampering attacks succeed and the grading record is changed); (3) no sanitization, filtering, or flagging of tool output anywhere on this path (verified by package grep and by the evidence logs: tool output carrying an injection reaches the model verbatim inside its tool-result message); (4) a raising tool does NOT abort the run -- the framework catches it into an error CallToolResult, which the model sees as its next observation (the caught class -- measured in the probe); (5) a tool result containing tool JSON does NOT execute (it is inert text in the tool result, not a dispatch -- measured in the probe and in the re-probe). No SECURITY.md is published for fast-agent (absent at the v0.10.54 tag, absent from the sdist, absent from the installed package), so no vendor security contact is published for this package. (The upstream origin lastmile-ai/mcp-agent does publish a SECURITY.md -- report via GitHub security advisories at https://github.com/lastmile-ai/mcp-agent/security/advisories/new -- but that is a different repo and a different package.)",
        "tool_calls": dict(fa_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(fa_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, PARTIAL_TOOLCALLS):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
