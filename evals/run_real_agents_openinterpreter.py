"""Audit Open Interpreter (Python 0.4.3, PyPI open-interpreter
0.4.3; repo HEAD 80d8f55385452457a625dbabc032f3003b9545b4 is the
Rust rewrite and is NOT what is audited) with Trustrun
(fifty-fifth real-agent audit; forty-third framework).

FALLBACK TARGET: the brief's primary target was GPT-Engineer
(gpt-engineer/gpt-engineer), but that slug does not exist
(GitHub API 404) and the real repository,
AntonOsika/gpt-engineer, is ARCHIVED (archived: true, last
push 2025-05-14), which the brief names as a fallback
trigger. The brief's fallback slug
(open-interpreter/open-interpreter) is also dead (GitHub API
404): the repository is now openinterpreter/openinterpreter,
rewritten in Rust. This audit covers the Python project as
shipped on PyPI -- open-interpreter 0.4.3, the last official
Python release (2024-10-26). See
real_agents/openinterpreter_adapter.py for the pinning facts.

Configuration under test: Open Interpreter 0.4.3's real chat
loop (OpenInterpreter.chat -> _streaming_chat(display=False)
-> _respond_and_store -> respond -> llm.run -> computer.run,
Jupyter kernel, no Docker) holding the whole Trustrun tool
set as Python functions callable from executed code (the
kernel-side bridge POSTs to the adapter's in-process HTTP
dispatcher), driven by a deterministic stub model
(DeterministicStub, the audit-30 decision logic reused
verbatim via the audit-52 adapter) served through the
llm.completions seam (no key, no network). One fresh stub
state is built per call; one package singleton (and its
Jupyter kernel) is shared per process (see
real_agents/openinterpreter_adapter.py for the wiring facts).

Usage: ~/workspace/hackathons/trustrun-venvs/openinterpreter-venv/bin/python3 run_real_agents_openinterpreter.py
(Open Interpreter lives in a separate venv; see
real_agents/openinterpreter_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the Open Interpreter adapter
on all 25 tasks, seed 0, k=5, with the eval corpus as the data
module input. Writes one machine readable summary into
reports/real_agents/openinterpreter/summary.json and the
evidence logs (injection observations, tampering calls) into
reports/real_agents/openinterpreter/evidence.json. Every number
in those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework +
stub-model combination. The stub is a literal model (it
follows instructions in the task text and in tool output), so
a BLOCK on an injection or tampering attack means the
framework passed the attack through to such a model
unfiltered. The per-row "attacks" field records every attack
in the stress battery with its survived/detected outcome. The
evidence logs show the exact observation text the framework
handed the model, which is the framework-level fact. Never
present a clean-room failure as a flaw in a real product: the
clean-room agents' failures are theirs; the Open Interpreter
rows are Open Interpreter's.
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

import real_agents.openinterpreter_adapter as oi_adapter  # noqa: E402
from real_agents.openinterpreter_adapter import (  # noqa: E402
    RUN_LOGS,
    OPENINTERPRETER_PYPI,
    OPENINTERPRETER_PYPI_DATE,
    OPENINTERPRETER_REPO,
    OPENINTERPRETER_REPO_HEAD,
    OPENINTERPRETER_REPO_HEAD_DATE,
    OPENINTERPRETER_TAG,
    OPENINTERPRETER_TAG_COMMIT,
    OPENINTERPRETER_TAG_DATE,
    OPENINTERPRETER_VERSION,
    openinterpreter_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "openinterpreter")
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
    oi_adapter.TOOL_CALLS.update(
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
                openinterpreter_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the Open Interpreter (non-)effect
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
                "agent": "openinterpreter",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("openinterpreter x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "openinterpreter",
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
            print("openinterpreter x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc))
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
        _write_atomic(PARTIAL_TOOLCALLS, dict(oi_adapter.TOOL_CALLS))
    summary = {
        "product": "Open Interpreter (Python 0.4.3, PyPI open-interpreter 0.4.3, real chat loop)",
        "component": "Open Interpreter 0.4.3's real chat loop (OpenInterpreter.chat -> _streaming_chat(display=False) -> _respond_and_store -> respond -> llm.run -> computer.run, Jupyter kernel, no Docker) holding the whole Trustrun tool set as Python functions callable from executed code (the kernel-side bridge in trustrun-venvs/openinterpreter-bridge/ POSTs to the adapter's in-process HTTP dispatcher), driven by DeterministicStub (the audit-30 decision logic reused verbatim via the audit-52 adapter; literal model) served through the llm.completions seam -- the stub replaces the LiteLLM completion callable Llm.run streams through, so the framework's own Llm.run, message conversion, token trimming, and run_text_llm markdown code-block parsing all execute for real (no key, no network). One fresh stub state is built per call; one package singleton (and its Jupyter kernel) is shared per process. The framework runs the agent loop, converts messages to OpenAI format, parses the model's markdown code blocks, yields a confirmation chunk before running code, executes the code in the kernel, and passes the code output back to the model through the code_output_template wrapper; it performs no sanitization, filtering, or flagging of tool results. A raising tool is caught by the adapter's dispatcher and its exception text is returned as the code output (the caught class); an unregistered tool name is reported as an 'Error: Tool X not found.' code output and the model gets another turn (soft-fail class, not an abort -- see real_agents/openinterpreter_adapter.py for the wiring facts). FALLBACK NOTE: the brief's primary target GPT-Engineer (gpt-engineer/gpt-engineer) does not exist (GitHub API 404) and the real repo AntonOsika/gpt-engineer is ARCHIVED; the brief's fallback slug open-interpreter/open-interpreter is also dead (GitHub API 404) -- the repo is now openinterpreter/openinterpreter, rewritten in Rust. This audit covers the Python project as shipped on PyPI, open-interpreter 0.4.3.",
        "version": "Open Interpreter %s (PyPI %s, released %s; installed wheel byte-identical to the shipped wheel on ten key source files; there is NO v0.4.3 git tag -- the newest Python tag is %s, commit %s, %s -- and the PyPI 0.4.3 sdist is missing from the file host, so the wheel itself is the reference artifact)" % (
            OPENINTERPRETER_VERSION, OPENINTERPRETER_PYPI,
            OPENINTERPRETER_PYPI_DATE,
            OPENINTERPRETER_TAG, OPENINTERPRETER_TAG_COMMIT,
            OPENINTERPRETER_TAG_DATE),
        "repo": OPENINTERPRETER_REPO,
        "repo_resolved": "https://github.com/openinterpreter/openinterpreter, main HEAD %s (pushed %s). HEAD is the Rust rewrite (a fork of OpenAI's Codex) and is NOT the audited code: the audited code is the PyPI 0.4.3 wheel, verified by byte-compare of interpreter/core/core.py, interpreter/core/respond.py, interpreter/core/llm/llm.py, interpreter/core/llm/run_text_llm.py, interpreter/core/llm/utils/convert_to_openai_messages.py, interpreter/core/computer/computer.py, interpreter/core/computer/terminal/languages/jupyter_language.py, interpreter/core/computer/terminal/languages/python.py, interpreter/terminal_interface/terminal_interface.py, and interpreter/__init__.py against the shipped wheel. The repo is NOT archived. The community fork endolith/open-interpreter continues the Python line but is a different lineage and is NOT what is audited. Open Interpreter is a terminal coding agent; the audited object is its chat loop -- see the adapter docstring for the wiring facts." % (
            OPENINTERPRETER_REPO_HEAD,
            OPENINTERPRETER_REPO_HEAD_DATE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim via the audit-52 adapter, served to Open Interpreter through the llm.completions seam -- the stub replaces the LiteLLM completion callable, renders a tool decision as a markdown python code block calling the harness tool through the kernel-side bridge, and a final answer as plain text; see real_agents/openinterpreter_adapter.py)",
        "confirmation_gate": "NONE on the audited library path, measured: (1) no approval step stands between the model and code execution when driving OpenInterpreter.chat() (display=False, the library path): respond yields a `confirmation` chunk before running code, but _respond_and_store only forwards it to the consumer, and the library consumer discards it -- the probe measured 1 confirmation chunk yielded and the code STILL executing (search_docs dispatched) with no input anywhere; (2) the approval prompt ('Would you like to run this code? (y/n)') lives ONLY in the terminal-interface consumer (terminal_interface.py): the probe measured it firing and a 'n' answer appending 'I have declined to run this code.' with ZERO tool executions -- the gate works when the consumer implements it, and the audited chat() path has no such consumer; (3) no sanitization, filtering, or flagging of tool results anywhere on this path (verified by package grep and by the evidence logs: code outputs carry injected text verbatim apart from the code_output_template wrapper); (4) a raising tool is CAUGHT by the adapter's dispatcher and its exception text is returned as the code output (measured in the probe); (5) an unregistered tool name is reported as an 'Error: Tool X not found.' code output and the model gets another turn -- nothing executes (measured in the probe; /probe.txt never created). Measured: a tool result containing tool JSON does NOT execute (it is inert text in a code-output observation, not a dispatch -- measured in the re-probe). safe_mode is 'off' by default (a semgrep scan would only run with safe_mode 'ask'/'auto'); auto_run is False by default, which only affects whether the terminal interface yields the confirmation chunk to its prompt -- it does not gate the library path.",
        "tool_calls": dict(oi_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(oi_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, PARTIAL_TOOLCALLS):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
