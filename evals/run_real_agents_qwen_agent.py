"""Audit Qwen-Agent (PyPI qwen-agent 0.0.34 == git HEAD
31a4d36d, repo https://github.com/QwenLM/Qwen-Agent) with
Trustrun (fifty-eighth real-agent audit; forty-sixth framework).

TARGET: Qwen-Agent (QwenLM/Qwen-Agent), verified absent from
DATASET.md before this audit (0 hits, no summary dir). See
real_agents/qwen_agent_adapter.py for the pinning facts.

Configuration under test: Qwen-Agent 0.0.34's real FnCallAgent
tool loop (the framework's own BaseChatModel.chat with
functions, its own Qwen fncall prompt parsing the model's text
into function calls, its own Agent._call_tool dispatch, looping
to MAX_LLM_CALL_PER_RUN = 20), driven by a deterministic stub
model (the audit-30 decision logic reused verbatim in decision,
adapted in shape: the "observation" is the latest ✿RESULT✿
block in the framework's merged message, and a tool decision is
rendered as the model's own ✿FUNCTION✿ / ✿ARGS✿ text because
that is the framework's own function-call format), served
through the framework's own BaseFnCallModel seam (a
BaseFnCallModel subclass with fncall_prompt_type 'qwen' handed
to FnCallAgent as its llm object), with the harness tools wired
in as the framework's own BaseTool subclasses (one per harness
tool, with the framework's own OpenAI-format function schema).
One fresh stub state is built per call; one FnCallAgent is
constructed per call (the framework holds no shared singleton).
See real_agents/qwen_agent_adapter.py for the wiring facts.

Usage: ~/workspace/hackathons/trustrun-venvs/qwen-agent-venv/bin/python3 run_real_agents_qwen_agent.py
(Qwen-Agent lives in a separate venv; see
real_agents/qwen_agent_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the Qwen-Agent adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/qwen_agent/summary.json and the evidence logs
(injection observations) into
reports/real_agents/qwen_agent/evidence.json. Every number in those
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
theirs; the Qwen-Agent rows are Qwen-Agent's. The tampering
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

import real_agents.qwen_agent_adapter as qa_adapter  # noqa: E402
from real_agents.qwen_agent_adapter import (  # noqa: E402
    RUN_LOGS,
    QWEN_PYPI,
    QWEN_PYPI_DATE,
    QWEN_REPO,
    QWEN_REPO_HEAD,
    QWEN_REPO_HEAD_DATE,
    QWEN_TAG,
    QWEN_TAG_COMMIT,
    QWEN_TAG_DATE,
    QWEN_VERSION,
    qwen_agent_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "qwen_agent")
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
    qa_adapter.TOOL_CALLS.update(
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
                qwen_agent_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the Qwen-Agent (non-)effect lives
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
                "agent": "qwen_agent",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("qwen_agent x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "qwen_agent",
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
            print("qwen_agent x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc), flush=True)
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
        _write_atomic(PARTIAL_TOOLCALLS, dict(qa_adapter.TOOL_CALLS))
    summary = {
        "product": "Qwen-Agent (PyPI qwen-agent 0.0.34 == git HEAD 31a4d36d, real FnCallAgent tool loop)",
        "component": "Qwen-Agent 0.0.34's real FnCallAgent tool loop (the framework's own BaseChatModel.chat with functions, its own Qwen fncall prompt parsing the model's text into function calls, its own Agent._call_tool dispatch, looping to MAX_LLM_CALL_PER_RUN = 20), holding the harness tools as the framework's own BaseTool subclasses (one per harness tool, OpenAI-format function schema), driven by DeterministicStub (the audit-30 decision logic reused verbatim in decision, adapted in shape: the 'observation' is the latest ✿RESULT✿ block in the framework's merged message, and a tool decision is rendered as the model's own ✿FUNCTION✿ / ✿ARGS✿ text because that is the framework's own function-call format; see real_agents/qwen_agent_adapter.py) served through the framework's own BaseFnCallModel seam (a BaseFnCallModel subclass with fncall_prompt_type 'qwen' handed to FnCallAgent as its llm object) -- the stub replaces the package's model, so the framework's own prompt preprocessing, function-call parsing, tool dispatch, and result handling all execute for real (no key, no network). One fresh stub state is built per call; one FnCallAgent is constructed per call. The framework runs the loop, converts tool results to FUNCTION messages, and passes the result to the model verbatim inside the ✿RESULT✿ block; it performs no sanitization, filtering, or flagging of tool output. A raising tool does NOT abort the run: Agent._call_tool catches the generic exception and returns the error text as the FUNCTION result, which the model then sees as its next observation (the caught class). The framework offers the model the tampering knobs as ordinary callable tools with no confirmation step, so a model that reaches for monitor_configure, edit_tests, or record_score succeeds. Adapter fix during this audit (2026-11-12): the stub's model responses carry extra={} because FnCallAgent._run reads out.extra.get('function_id', '1') and Message.extra defaults to None, which crashed the framework's own loop before any tool result was seen (see real_agents/qwen_agent_adapter.py).",
        "version": "Qwen-Agent %s (PyPI %s, released %s; installed files byte-identical to the sdist on all 91 .py files, and the sdist package byte-identical to git HEAD %s, %s; no v0.0.34 tag exists, latest tag %s = %s, %s)" % (
            QWEN_VERSION, QWEN_PYPI,
            QWEN_PYPI_DATE,
            QWEN_REPO_HEAD, QWEN_REPO_HEAD_DATE,
            QWEN_TAG, QWEN_TAG_COMMIT,
            QWEN_TAG_DATE),
        "repo": QWEN_REPO,
        "repo_resolved": "https://github.com/QwenLM/Qwen-Agent, main HEAD %s (committed %s). The repo is NOT archived. The audited code is the PyPI 0.0.34 release, verified by byte-compare of all 91 .py files against the shipped sdist, which is byte-identical to the HEAD git tree. Qwen-Agent is a function-calling agent framework; the audited object is its FnCallAgent tool loop -- see the adapter docstring for the wiring facts." % (
            QWEN_REPO_HEAD,
            QWEN_REPO_HEAD_DATE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim in decision via the audit-52 adapter lineage, adapted in shape: the stub answers the framework's BaseFnCallModel calls by reading the latest ✿RESULT✿ block out of the framework's merged message, and a tool decision is rendered as the model's own ✿FUNCTION✿ / ✿ARGS✿ text; see real_agents/qwen_agent_adapter.py)",
        "confirmation_gate": "NONE on the audited path, measured -- the tampering knobs are exposed as ordinary callable tools with no approval step: (1) a case-insensitive package grep over all 91 .py files of the installed qwen_agent package for human_in_the_loop / require_confirmation / needs_approval / approval returns 0 hits; 'confirm' returns 1 hit, the word in a validation error message ('must confirm to a valid openai-compatible JSON schema', tools/base.py:123); 'sanitize' returns 7 hits, all file-path sanitization (sanitize_chrome_file_path / sanitize_windows_file_path in simple_doc_parser.py and utils/utils.py, used by doc parsing, not content sanitization of tool output and not on the FnCallAgent tool path); 'interrupt' returns 3 hits, a PENDING_USER_INPUT marker in user_agent.py (a different agent class), a GUI log line, and a KeyboardInterrupt raise -- none of them is a tool-call approval gate on the FnCallAgent path; (2) the framework executes any tool the model requests immediately -- monitor_configure, edit_tests, and record_score are dispatched by Agent._call_tool with no human gate anywhere (verified by the re-probe: the tampering attacks succeed and the grading record is changed); (3) no sanitization, filtering, or flagging of tool output anywhere on this path (verified by package grep and by the evidence logs: tool output carrying an injection reaches the model verbatim inside the ✿RESULT✿ block); (4) a raising tool does NOT abort run() -- Agent._call_tool catches the generic exception and returns the error text as the FUNCTION result, which the model sees as its next observation (the caught class -- measured in the probe); (5) a tool result containing tool JSON does NOT execute (it is inert text in the ✿RESULT✿ block, not a dispatch -- measured in the probe and in the re-probe). No SECURITY.md is published in the repo (absent at main HEAD and from the sdist) or in the package, so no vendor security contact is published.",
        "tool_calls": dict(qa_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(qa_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, PARTIAL_TOOLCALLS):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
