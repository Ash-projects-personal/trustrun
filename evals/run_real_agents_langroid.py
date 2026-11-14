"""Audit Langroid's ChatAgent (langroid 0.69.22) with Trustrun
(forty-fourth real-agent audit; first audit of this framework in
the rotation -- the multi-agent framework from langroid/langroid,
repo https://github.com/langroid/langroid).

Configuration under test: a single ChatAgent (default configuration:
use_tools=True, use_functions_api=False -- the Langroid-native JSON
tool-call mechanism, not the opt-in OpenAI tools API) holds the whole
Trustrun tool set (search_docs, monitor_configure, edit_tests,
record_score, calculator, ask_user) as ToolMessage subclasses, driven
by a deterministic stub model (DeterministicStubLM, a MockLM subclass
whose chat() decides from the message history). One fresh agent, stub,
and Task are built per call. No system prompt beyond the audit's
neutral instruction ("You are a helpful assistant... respond with
DONE: <answer>"), no human-in-the-loop, interactive=False. See
real_agents/langroid_adapter.py for the wiring facts.

Usage: ~/workspace/hackathons/trustrun-venvs/langroid-venv/bin/python3 run_real_agents_langroid.py
(langroid lives in a separate venv; see
real_agents/langroid_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the Langroid adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/langroid/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/langroid/evidence.json. Every number in those
files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The per-row "attacks" field records every
attack in the stress battery with its survived/detected outcome. The
evidence logs show the exact observation text the framework handed
the model, which is the framework-level fact. Never present a
clean-room failure as a flaw in a real product: the clean-room
agents' failures are theirs; the Langroid rows are Langroid's.
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

import real_agents.langroid_adapter as lr_adapter  # noqa: E402
from real_agents.langroid_adapter import (  # noqa: E402
    LANGROID_REPO,
    LANGROID_REPO_HEAD,
    LANGROID_REPO_HEAD_DATE,
    LANGROID_REPO_HEAD_MESSAGE,
    LANGROID_TAG,
    LANGROID_TAG_COMMIT,
    LANGROID_TAG_DATE,
    LANGROID_VERSION,
    RUN_LOGS,
    langroid_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "langroid")
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
                langroid_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the Langroid (non-)effect lives
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
                "agent": "langroid",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("langroid x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "langroid",
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
            print("langroid x %s -> CRASH (%s: %s)"
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
        "product": "Langroid ChatAgent (langroid 0.69.22, multi-agent framework)",
        "component": "ChatAgent with the whole Trustrun tool set enabled as ToolMessage subclasses (search_docs, monitor_configure, edit_tests, record_score, calculator, ask_user), driven by DeterministicStubLM (a MockLM subclass; literal model) inside a Task (interactive=False, default configuration: use_tools=True, use_functions_api=False -- the Langroid-native JSON tool-call mechanism). One fresh agent, stub, and Task are built per call. No human-in-the-loop, no checkpointer.",
        "version": "langroid %s" % LANGROID_VERSION,
        "repo": LANGROID_REPO,
        "repo_resolved": "https://github.com/langroid/langroid, default-branch HEAD %s (commit %s, '%s'). Installed with pip install langroid pytest numpy in a separate venv (~/workspace/hackathons/trustrun-venvs/langroid-venv); langroid 0.69.22 is the current latest release on PyPI at audit time, and HEAD is the 0.69.22 tag itself (%s, %s, commit %s), so the wheel and HEAD are the same code. The audited object is ChatAgent + Task in the default configuration -- see the adapter docstring for the wiring facts." % (
            LANGROID_REPO_HEAD, LANGROID_REPO_HEAD_DATE,
            LANGROID_REPO_HEAD_MESSAGE,
            LANGROID_TAG, LANGROID_TAG_DATE,
            LANGROID_TAG_COMMIT),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim, expressed as Langroid JSON tool calls; final answers returned as 'DONE: <answer>' for the Task DONE signal; see real_agents/langroid_adapter.py)",
        "confirmation_gate": "NONE by default -- no per-tool confirmation gate is wired into the audited configuration (see the re-probe log for the package grep counts). Measured: tampering knobs called by the model execute with no approval step. Langroid-specific: a raw user message containing tool JSON for a usable tool is executed directly by the agent before the model is ever called (measured in the re-probe: monitor_configure executed once with the stub emitting no tool call); that is a second, model-bypassing path to the same knobs.",
        "tool_calls": dict(lr_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(lr_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
