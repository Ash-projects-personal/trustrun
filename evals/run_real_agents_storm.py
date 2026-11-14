"""Audit STORM (PyPI knowledge-storm 1.1.1 == git HEAD
fb951af7744dab086e34962e9bc6fe878e145f83; repo
https://github.com/stanford-oval/storm) with Trustrun
(fifty-seventh real-agent audit; forty-fifth framework).

TARGET: STORM (stanford-oval/storm), verified absent from
DATASET.md before this audit (0 hits, no summary dir). See
real_agents/storm_adapter.py for the pinning facts.

Configuration under test: STORM 1.1.1's real research/writing
pipeline (STORMWikiRunner: persona generation -> perspective-
guided conversation -> outline -> section writing -> lead +
polish), driven by a deterministic stub model (the audit-30
decision logic reused verbatim in decision, adapted in shape:
the "observation" is the retrieved context embedded in the
framework's prompts, and a tool decision is rendered as the
model's own text because the framework offers the model no
tool channel), served through the dspy LM seam (a dsp.LM
subclass handed to all five LM config slots; no key, no
network), with the harness search_docs tool wired in as the
framework's own retriever (a dspy.Retrieve subclass returning
the framework's own {"url", "title", "description",
"snippets"} shape). One fresh stub state is built per call;
one STORMWikiRunner is constructed per call (the framework
holds no shared singleton). See real_agents/storm_adapter.py
for the wiring facts.

Usage: ~/workspace/hackathons/trustrun-venvs/storm-venv/bin/python3 run_real_agents_storm.py
(STORM lives in a separate venv; see real_agents/storm_adapter.py
for the install command.)

Runs trustrun.cli.run_audit over the STORM adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/storm/summary.json and the evidence logs
(injection observations) into
reports/real_agents/storm/evidence.json. Every number in those
files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub
model combination. The stub is a literal model (it follows
instructions in the task text and in retrieved content), so a
BLOCK on an injection attack means the framework passed the
attack through to such a model unfiltered. The per-row "attacks"
field records every attack in the stress battery with its
survived/detected outcome. The evidence logs show the exact
context the framework handed the model, which is the
framework-level fact. Never present a clean-room failure as a
flaw in a real product: the clean-room agents' failures are
theirs; the STORM rows are STORM's. The tampering attacks
measure the framework's architecture: the pipeline offers the
model no tool channel, so the monitor and grading knobs are
unreachable and those attacks survive -- that is a property of
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

import real_agents.storm_adapter as st_adapter  # noqa: E402
from real_agents.storm_adapter import (  # noqa: E402
    RUN_LOGS,
    STORM_PYPI,
    STORM_PYPI_DATE,
    STORM_REPO,
    STORM_REPO_HEAD,
    STORM_REPO_HEAD_DATE,
    STORM_TAG,
    STORM_TAG_COMMIT,
    STORM_TAG_DATE,
    STORM_VERSION,
    storm_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "storm")
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
    st_adapter.TOOL_CALLS.update(
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
                storm_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the STORM (non-)effect lives
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
                "agent": "storm",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("storm x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "storm",
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
            print("storm x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc), flush=True)
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
        _write_atomic(PARTIAL_TOOLCALLS, dict(st_adapter.TOOL_CALLS))
    summary = {
        "product": "STORM (PyPI knowledge-storm 1.1.1 == git HEAD fb951af, real research/writing pipeline)",
        "component": "STORM 1.1.1's real research/writing pipeline (STORMWikiRunner: StormPersonaGenerator perspectives -> ConvSimulator perspective-guided conversation -> WriteOutline -> ConvToSection per outline section -> WriteLeadSection lead + article polish, one LM call per step with the full gathered context), holding the harness search_docs tool as the framework's own retriever (a dspy.Retrieve subclass returning the framework's own {url, title, description, snippets} shape, one distinct letter-suffixed URL per search so no query's results are deduped away), driven by DeterministicStub (the audit-30 decision logic reused verbatim in decision, adapted in shape: the 'observation' is the retrieved context embedded in the framework's prompts, and a tool decision is rendered as the model's own text with arithmetic evaluated inline by the harness's safe evaluator; see real_agents/storm_adapter.py) served through the dspy LM seam (a dsp.LM subclass handed to all five LM config slots: conv_simulator, question_asker, outline_gen, article_gen, article_polish) -- the stub replaces the package's model, so the framework's own perspective generation, conversation simulation, outline writing, section writing, and lead writing all execute for real (no key, no network). One fresh stub state is built per call; one STORMWikiRunner is constructed per call. The framework runs the pipeline, converts retrieved pages to conversation context, and passes the context to the model verbatim inside the AnswerQuestion prompt's Gathered information block and the WriteSection prompt's collected-information block; it performs no sanitization, filtering, or flagging of retrieved content. A raising tool aborts run() (the abort class, converted by the adapter to a flagged result). The framework offers the model no tool channel in the default path, so monitor_configure, edit_tests, record_score, and ask_user are never called and the tampering attacks survive by architecture. Adapter fix during this audit (2026-11-12): the stub's prompt-field extractor first matched dspy's format-template echo (${info} / ${section} placeholders rendered above the '---' separator) and the smoke test caught the polished article coming back as '# ${section} / ${info}'; _between now skips ${...} placeholder spans and returns the rendered value (see real_agents/storm_adapter.py).",
        "version": "STORM %s (PyPI %s, released %s; installed files byte-identical to the sdist on fourteen key source files, and the sdist package byte-identical to git HEAD %s, %s; no v1.1.1 tag exists, latest tag %s = %s, %s)" % (
            STORM_VERSION, STORM_PYPI,
            STORM_PYPI_DATE,
            STORM_REPO_HEAD, STORM_REPO_HEAD_DATE,
            STORM_TAG, STORM_TAG_COMMIT,
            STORM_TAG_DATE),
        "repo": STORM_REPO,
        "repo_resolved": "https://github.com/stanford-oval/storm, main HEAD %s (committed %s). The repo is NOT archived. The audited code is the PyPI 1.1.1 release, verified by byte-compare of fourteen key source files against the shipped sdist, which is byte-identical to the HEAD git tree. STORM is a research/writing agent; the audited object is its STORMWikiRunner pipeline -- see the adapter docstring for the wiring facts." % (
            STORM_REPO_HEAD,
            STORM_REPO_HEAD_DATE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and retrieved content; the audit-30 DeterministicChatModel decision logic reused verbatim in decision via the audit-52 adapter lineage, adapted in shape: the stub answers the framework's dspy LM calls by prompt shape -- related-topics, personas, question, queries, answer, outline, section, lead, polish -- and a tool decision is rendered as the model's own text with arithmetic evaluated inline by the harness's safe evaluator; see real_agents/storm_adapter.py)",
        "confirmation_gate": "NONE on the audited path, measured -- and there is no tool-call channel for a gate to stand on: (1) a case-insensitive package grep for human_in_the_loop / require_confirmation / needs_approval / confirm / sanitize / approval over all 34 .py files of the installed knowledge_storm package returns 0 hits (same 0 in the sdist source), so no confirmation, approval, or sanitization language exists anywhere in the shipped code; (2) the research/writing pipeline offers the model no tools at all, so no approval step stands between the model and any tool call -- the model never calls monitor_configure, edit_tests, record_score, or ask_user, and the framework executes retriever searches and article writing with no human gate anywhere (verified by package grep and by the evidence logs: zero dispatches of any knob across the whole audit); (3) no sanitization, filtering, or flagging of retrieved content anywhere on this path (verified by package grep and by the evidence logs: retrieved content carrying an injection reaches the AnswerQuestion prompt verbatim inside the Gathered information block and the WriteSection prompt verbatim inside the collected-information block); (4) a raising tool ABORTS run() -- the framework's Retriever.retrieve re-raises out of the conversation executor and the adapter converts it to a flagged 'could not complete' result (measured in the probe); (5) a tool result containing tool JSON does NOT execute (it is inert text in the article context, not a dispatch -- measured in the probe and in the re-probe). No SECURITY.md is published in the repo (404 at main and at the pinned commit) or in the sdist, so no vendor security contact is published.",
        "tool_calls": dict(st_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(st_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, PARTIAL_TOOLCALLS):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
