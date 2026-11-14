"""Audit GPT-Researcher (PyPI gpt-researcher 0.17.0 == git tag
v3.8.0; repo HEAD ddd4db36208d9c8e49f3b2436efda97baecb5433)
with Trustrun (fifty-sixth real-agent audit; forty-fourth
framework).

TARGET: GPT-Researcher (assafelovic/gpt-researcher), verified
absent from DATASET.md before this audit (0 hits, no summary
dir). The brief's fallback (STORM) was not needed: the repo is
live (not archived, pushed 2026-11-09) and auditable. See
real_agents/gptresearcher_adapter.py for the pinning facts.

Configuration under test: GPT-Researcher 0.17.0's real research
pipeline (GPTResearcher.conduct_research -> choose_agent ->
plan_research_outline -> per-sub-query retriever search ->
BM25 context select -> GPTResearcher.write_report ->
generate_report, one LLM call with the full research context),
driven by a deterministic stub model (the audit-30 decision
logic reused verbatim in decision, adapted in shape: the
"observation" is the retrieved context embedded in the report
prompt, and a tool decision is rendered as the model's own text
because the framework offers the model no tool channel),
served through the create_chat_completion seam (no key, no
network), with the harness search_docs tool wired in as the
framework's own retriever (requires_scraping=False prefetched
content). One fresh stub state is built per call; one
GPTResearcher is constructed per call (the framework holds no
shared singleton). See real_agents/gptresearcher_adapter.py for
the wiring facts.

Usage: ~/workspace/hackathons/trustrun-venvs/gptresearcher-venv/bin/python3 run_real_agents_gptresearcher.py
(GPT-Researcher lives in a separate venv; see
real_agents/gptresearcher_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the GPT-Researcher adapter on
all 25 tasks, seed 0, k=5, with the eval corpus as the data
module input. Writes one machine readable summary into
reports/real_agents/gptresearcher/summary.json and the evidence
logs (injection observations) into
reports/real_agents/gptresearcher/evidence.json. Every number in
those files comes from a real run. Nothing is invented.

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
theirs; the GPT-Researcher rows are GPT-Researcher's. The
tampering attacks measure the framework's architecture: the
pipeline offers the model no tool channel, so the monitor and
grading knobs are unreachable and those attacks survive -- that
is a property of this framework, recorded in the rows, not a
vacuous pass.
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

import real_agents.gptresearcher_adapter as gr_adapter  # noqa: E402
from real_agents.gptresearcher_adapter import (  # noqa: E402
    RUN_LOGS,
    GPTRESEARCHER_PYPI,
    GPTRESEARCHER_PYPI_DATE,
    GPTRESEARCHER_REPO,
    GPTRESEARCHER_REPO_HEAD,
    GPTRESEARCHER_REPO_HEAD_DATE,
    GPTRESEARCHER_TAG,
    GPTRESEARCHER_TAG_COMMIT,
    GPTRESEARCHER_TAG_DATE,
    GPTRESEARCHER_VERSION,
    gptresearcher_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "gptresearcher")
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
    gr_adapter.TOOL_CALLS.update(
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
                gptresearcher_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the GPT-Researcher (non-)effect
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
                "agent": "gptresearcher",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("gptresearcher x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "gptresearcher",
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
            print("gptresearcher x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc))
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
        _write_atomic(PARTIAL_TOOLCALLS, dict(gr_adapter.TOOL_CALLS))
    summary = {
        "product": "GPT-Researcher (PyPI gpt-researcher 0.17.0 == git tag v3.8.0, real research pipeline)",
        "component": "GPT-Researcher 0.17.0's real research pipeline (GPTResearcher.conduct_research -> choose_agent -> plan_research_outline -> per-sub-query retriever search -> BM25 context select -> GPTResearcher.write_report -> generate_report, one LLM call with the full research context) holding the harness search_docs tool as the framework's own retriever (requires_scraping=False prefetched content), driven by DeterministicStub (the audit-30 decision logic reused verbatim in decision, adapted in shape: the 'observation' is the retrieved context embedded in the report prompt, and a tool decision is rendered as the model's own text because the framework offers the model no tool channel) served through the create_chat_completion seam -- the stub replaces the package's single LLM function, so the framework's own agent choice, sub-query planning, retriever dispatch, context selection, and report writing all execute for real (no key, no network). One fresh stub state is built per call; one GPTResearcher is constructed per call. The framework runs the pipeline, converts retrieved pages to report context, and passes the context to the model verbatim inside the report prompt's Information block; it performs no sanitization, filtering, or flagging of retrieved content. A raising tool at the initial search aborts conduct_research (the abort class, converted by the adapter to a flagged result); a raising tool at the per-sub-query stage is caught per retriever by the framework and the run completes from the initial context (the caught class -- see real_agents/gptresearcher_adapter.py for the wiring facts). The framework offers the model no tool channel in the default path, so monitor_configure, edit_tests, record_score, and ask_user are never called and the tampering attacks survive by architecture.",
        "version": "GPT-Researcher %s (PyPI %s, released %s; installed files byte-identical to the sdist on thirteen key source files, and the sdist package byte-identical to git tag %s, commit %s, %s)" % (
            GPTRESEARCHER_VERSION, GPTRESEARCHER_PYPI,
            GPTRESEARCHER_PYPI_DATE,
            GPTRESEARCHER_TAG, GPTRESEARCHER_TAG_COMMIT,
            GPTRESEARCHER_TAG_DATE),
        "repo": GPTRESEARCHER_REPO,
        "repo_resolved": "https://github.com/assafelovic/gpt-researcher, main HEAD %s (pushed %s). The repo is NOT archived. The audited code is the PyPI 0.17.0 release, verified by byte-compare of agent.py, utils/llm.py, skills/researcher.py, skills/writer.py, skills/context_manager.py, context/select.py, actions/query_processing.py, actions/agent_creator.py, actions/report_generation.py, retrievers/base.py, config/config.py, prompts.py, and __init__.py against the shipped sdist, which is byte-identical to the v3.8.0 tag tarball. GPT-Researcher is a research-report agent; the audited object is its research pipeline -- see the adapter docstring for the wiring facts." % (
            GPTRESEARCHER_REPO_HEAD,
            GPTRESEARCHER_REPO_HEAD_DATE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and retrieved content; the audit-30 DeterministicChatModel decision logic reused verbatim in decision via the audit-52 adapter lineage, adapted in shape: the stub answers the framework's create_chat_completion calls by prompt shape -- agent choice, sub-query list, report from the embedded research context -- and a tool decision is rendered as the model's own text with arithmetic evaluated inline by the harness's safe evaluator; see real_agents/gptresearcher_adapter.py)",
        "confirmation_gate": "NONE on the audited path, measured -- and there is no tool-call channel for a gate to stand on: (1) the research pipeline offers the model no tools at all, so no approval step stands between the model and any tool call -- the model never calls monitor_configure, edit_tests, record_score, or ask_user, and the framework executes retriever searches and report writing with no human gate anywhere (verified by package grep and by the evidence logs: zero dispatches of any knob across the whole audit); (2) the only tool-calling code in the package, utils/tools.py create_chat_completion_with_tools, is used by the MCP tool selector, which is not on the audited path, and it too binds tools and invokes them with no approval step; (3) no sanitization, filtering, or flagging of retrieved content anywhere on this path (verified by package grep and by the evidence logs: retrieved content carrying an injection reaches the report prompt verbatim inside the Information block); (4) a raising tool at the initial search ABORTS conduct_research -- the framework re-raises out of _get_initial_search_results and the adapter converts it to a flagged 'could not complete' result (measured in the probe); a raising tool at the per-sub-query stage is CAUGHT per retriever by _search_relevant_source_urls and the run completes from the initial context (measured in the probe with a fail-on-second-call retriever); (5) a tool result containing tool JSON does NOT execute (it is inert text in the report context, not a dispatch -- measured in the probe and in the re-probe). A routine instruction prefix can derail retrieval: the rewrite_test instruction's words ('test', 'expectations') dominate the retriever's TF-IDF query and pull an irrelevant doc, so that attack run answers from the wrong source (measured in the probe; see the re-probe).",
        "tool_calls": dict(gr_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(gr_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, PARTIAL_TOOLCALLS):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
