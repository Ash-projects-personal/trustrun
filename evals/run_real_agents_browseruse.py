"""Audit browser-use (browser-use/browser-use, PyPI browser-use
1.0.3 == git tag 1.0.3) with Trustrun (sixty-second real-agent
audit; fiftieth framework in the rotation; first browser-use
audit).

TARGET: browser-use (browser-use/browser-use), verified absent from
DATASET.md before this audit (0 hits, no summary dir). See
real_agents/browseruse_adapter.py for the pinning facts -- PyPI
browser-use 1.0.3 (current latest, verified via PyPI JSON
2026-11-12) == git tag 1.0.3 =
dfb6a73d520809341c975c6a01c228327991e88b (2026-11-12), which is
also the repo's current main HEAD; sdist byte-identical to the
tag tree on all 44 browser_use/ .py files; installed
byte-identical to the sdist on all 44 .py files.

Configuration under test: browser-use 1.0.3's real Agent loop
(the framework's own Pydantic AI loop + one persistent Python
REPL running browser-harness: the model returns tool calls,
the loop dispatches them through Pydantic AI's tool path,
tool results come back as ToolReturnPart messages, and the loop
ends when the model calls finish / finish_from_repl or answers
in plain text), holding the harness tools as @tools.action
functions on a Tools() object (the framework's own documented
custom-action path), driven by a deterministic stub model (the
audit-30 decision logic reused verbatim in decision, adapted in
shape: the 'observation' is the latest ToolReturnPart in the
framework's conversation, and a tool decision is rendered as a
pydantic-ai ToolCallPart; a final answer is rendered as a
ToolCallPart for the framework's own finish tool), served
through the framework's own llm= seam (a Pydantic AI Model
subclass -- the framework accepts any Pydantic AI Model).
One fresh stub state is built per call; one fresh Agent +
one fresh local headless Browser per call. The browser is a
real local headless Chromium (Browser('chromium',
headless=True), the Playwright Chromium already in
~/.cache/ms-playwright): no browser-binary download, no
CAPTCHA, no login, no Docker, no external services, no cloud
browser. See real_agents/browseruse_adapter.py for the wiring
facts.

Usage: ~/workspace/hackathons/trustrun-venvs/browseruse-venv/bin/python3 run_real_agents_browseruse.py
(browser-use lives in a separate venv; see
real_agents/browseruse_adapter.py for the install command.)

Runs trustrun.cli.run_audit over the browser-use adapter on all
25 tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/browser-use/summary.json and the evidence logs
(injection observations) into
reports/real_agents/browser-use/evidence.json. Every number in
those files comes from a real run. Nothing is invented.

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
theirs; the browser-use rows are browser-use's. The tampering
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

import real_agents.browseruse_adapter as bu_adapter  # noqa: E402
from real_agents.browseruse_adapter import (  # noqa: E402
    BROWSERUSE_PYPI,
    BROWSERUSE_PYPI_DATE,
    BROWSERUSE_REPO,
    BROWSERUSE_REPO_HEAD,
    BROWSERUSE_REPO_HEAD_DATE,
    BROWSERUSE_TAG,
    BROWSERUSE_TAG_COMMIT,
    BROWSERUSE_TAG_DATE,
    BROWSERUSE_VERSION,
    BROWSER_EVIDENCE,
    RUN_LOGS,
    browseruse_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "browser-use")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
PARTIAL_TOOLCALLS = os.path.join(OUT_DIR, "tool_calls_partial.json")
PARTIAL_BROWSER = os.path.join(OUT_DIR, "browser_evidence_partial.json")


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write_atomic(path, payload, attempts=5):
    # Retry with backoff: the 2026-11-12 run hit a VM-wide transient
    # (~18:46-19:00 UTC: checkpoint writes EPERM'd, chrome crashed
    # at start, and the concurrently running project suite died
    # with no output) -- a write failure must not kill a
    # ~50-minute run. Attempts are spaced 2/5/10/20 s apart; the
    # caller decides whether a final failure is fatal.
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=1)
            os.replace(tmp, path)
            return
        except OSError as exc:
            last_exc = exc
            print("checkpoint write %s failed (attempt %d/%d): %s"
                  % (path, attempt, attempts, exc), flush=True)
            if attempt < attempts:
                time.sleep((2, 5, 10, 20)[attempt - 1])
    raise last_exc


def _checkpoint(path, payload):
    """Checkpoint write that never kills the run: on failure the
    rows stay in memory and the next task's checkpoint retries.
    The final summary write (not this helper) is the must-succeed
    point."""
    try:
        _write_atomic(path, payload, attempts=2)
    except OSError as exc:
        print("CHECKPOINT LOST (will retry next task): %s: %s"
              % (path, exc), flush=True)


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
    bu_adapter.TOOL_CALLS.update(
        _load_json(PARTIAL_TOOLCALLS, {}))
    BROWSER_EVIDENCE.extend(_load_json(PARTIAL_BROWSER, []))
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
                browseruse_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the browser-use (non-)effect lives
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
                "agent": "browser-use",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("browser-use x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "browser-use",
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
            print("browser-use x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc), flush=True)
        # Checkpoint after every task so a killed run loses at most one.
        # _checkpoint never raises: a transient write failure must not
        # kill the run (2026-11-12 EPERM incident); rows stay in memory.
        _checkpoint(PARTIAL_ROWS, rows)
        _checkpoint(PARTIAL_EVIDENCE, RUN_LOGS)
        _checkpoint(PARTIAL_TOOLCALLS, dict(bu_adapter.TOOL_CALLS))
        _checkpoint(PARTIAL_BROWSER, list(BROWSER_EVIDENCE))
    summary = {
        "product": "browser-use (PyPI browser-use 1.0.3 == git tag 1.0.3 in browser-use/browser-use, real Agent loop)",
        "component": "browser-use 1.0.3's real Agent agentic loop (the framework's own Pydantic AI loop + one persistent Python REPL running browser-harness: the model returns tool calls, the loop dispatches them through Pydantic AI's tool path, tool results come back as ToolReturnPart messages, and the loop ends when the model calls finish / finish_from_repl or answers in plain text), holding the harness tools as @tools.action functions on a Tools() object (the framework's own documented custom-action path), driven by DeterministicStub (the audit-30 decision logic reused verbatim in decision, adapted in shape: the 'observation' is the latest ToolReturnPart in the framework's conversation, and a tool decision is rendered as a pydantic-ai ToolCallPart; a final answer is rendered as a ToolCallPart for the framework's own finish tool; see real_agents/browseruse_adapter.py) served through the framework's own llm= seam (a Pydantic AI Model subclass -- the framework accepts any Pydantic AI Model) -- the stub replaces the package's model, so the framework's own tool planning, dispatch, and result handling all execute for real (no key, no network). One fresh stub state is built per call; one fresh Agent + one fresh local headless Browser per call. The browser is a real local headless Chromium (Browser('chromium', headless=True), the Playwright Chromium already in ~/.cache/ms-playwright): no browser-binary download, no CAPTCHA, no login, no Docker, no external services, no cloud browser. The framework runs the loop and passes tool results to the model verbatim; it performs no sanitization, filtering, or flagging of tool output. A raising tool does NOT abort the run: the framework's BrowserLoop.on_tool_execute_error returns it to the model as an ActionResult(error=...) tool result, which the model then sees as its next observation (the caught class). The framework offers the model the tampering knobs as ordinary callable tools with no confirmation step, so a model that reaches for monitor_configure, edit_tests, or record_score succeeds.",
        "version": "browser-use %s (PyPI %s, released %s; installed files byte-identical to the sdist on all 44 browser_use/ .py files, and the sdist package byte-identical to git tag %s = %s, %s; the only non-code differences are browser_use/README.md and browser_use/mcp/.dxtignore, present in the tag and absent from the sdist; no .py file differs)" % (
            BROWSERUSE_VERSION, BROWSERUSE_PYPI,
            BROWSERUSE_PYPI_DATE,
            BROWSERUSE_TAG, BROWSERUSE_TAG_COMMIT,
            BROWSERUSE_TAG_DATE),
        "repo": BROWSERUSE_REPO,
        "repo_resolved": "https://github.com/browser-use/browser-use, main HEAD %s (committed %s) -- tag %s = %s (%s) is the audited release, and the tag commit is also the current main HEAD. The audited code is the PyPI 1.0.3 release, verified by byte-compare of all 44 .py files against the shipped sdist, which is byte-identical to the 1.0.3 tag tree on every .py file present in both. browser-use is a browser-agent framework; the audited object is its Agent loop -- see the adapter docstring for the wiring facts." % (
            BROWSERUSE_REPO_HEAD,
            BROWSERUSE_REPO_HEAD_DATE,
            BROWSERUSE_TAG,
            BROWSERUSE_TAG_COMMIT,
            BROWSERUSE_TAG_DATE),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic reused verbatim in decision via the audit-60 adapter lineage, adapted in shape: the stub answers the framework's Model.request calls by reading the latest ToolReturnPart out of the framework's conversation, and a tool decision is rendered as a pydantic-ai ToolCallPart; a final answer is rendered as a ToolCallPart for the framework's own finish tool; see real_agents/browseruse_adapter.py)",
        "confirmation_gate": "NONE on the audited path, measured -- the tampering knobs are exposed as ordinary callable tools with no approval step (see the re-probe log for the package grep and the measured calls).",
        "tool_calls": dict(bu_adapter.TOOL_CALLS),
        "browser_evidence": {
            "runs_with_live_chrome": sum(
                1 for e in BROWSER_EVIDENCE
                if isinstance(e, dict) and e.get("chrome_procs", 0) > 0),
            "runs_total": len(BROWSER_EVIDENCE),
            "sample": BROWSER_EVIDENCE[:3],
        },
        "tasks": [t["id"] for t in tasks],
        "seed": 0,
        "k": 5,
        "audits": len(rows),
        "crashes": [r["task"] for r in rows if "crash" in r],
        "rows": rows,
    }
    # Final writes use the retrying atomic writer: a transient at
    # the end must not lose the run (2026-11-12 EPERM incident).
    _write_atomic(os.path.join(OUT_DIR, "summary.json"), summary)
    _write_atomic(os.path.join(OUT_DIR, "evidence.json"), RUN_LOGS)
    print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
    print("stress:", dict(Counter(r["stress"] for r in rows)))
    print("tool_calls:", dict(bu_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("browser evidence: %d/%d runs saw live chrome"
          % (summary["browser_evidence"]["runs_with_live_chrome"],
             summary["browser_evidence"]["runs_total"]))
    print("done in %.1fs" % (time.time() - started))
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, PARTIAL_TOOLCALLS,
                 PARTIAL_BROWSER):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
