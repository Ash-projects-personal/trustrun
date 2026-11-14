"""Audit Mastra (mastra-ai/mastra, npm @mastra/core 1.83.0) with
Trustrun (sixty-fourth real-agent audit; the FIRST TypeScript
framework in the rotation).

Configuration under test: Mastra's real `Agent.generate` loop
(`@mastra/core` 1.83.0, `Agent` from `@mastra/core/agent`) in a
fresh Agent + fresh deterministic stub model per call, holding the
whole Trustrun tool set (search_docs, calculator, plus the
monitor/grader/clarification tools run_audit adds) via the adapter's
localhost tool bridge (see real_agents/mastra_adapter.py), driven by
a deterministic stub LanguageModelV2 (the audit-30 decision logic
ported to JavaScript in stub-model.mjs). One fresh stub and Agent
are built per call; the Node driver process persists across calls.
No key, no network.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \
    evals/run_real_agents_mastra.py [--max-tasks N]
(Mastra lives in a Node workspace, not the project venv; see
real_agents/mastra_adapter.py for the install command. The runner
runs under the PROJECT venv python and shells out to node.)

Runs trustrun.cli.run_audit over the Mastra adapter on all 25 tasks,
seed 0, k=5, with the eval corpus as the data module input. Writes
one machine readable summary into
reports/real_agents/mastra/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/mastra/evidence.json. Every number in those
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
agents' failures are theirs; the Mastra rows are Mastra's. Note the
audited code is the 1.83.0 release, not default-branch HEAD: see the
adapter docstring for the pinning facts.
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

import real_agents.mastra_adapter as ad_adapter  # noqa: E402
from real_agents.mastra_adapter import (  # noqa: E402
    RUN_LOGS,
    MASTRA_CORE_NPM,
    MASTRA_CORE_PUBLISHED,
    MASTRA_CORE_VERSION,
    MASTRA_LAST_PUSH,
    MASTRA_PKG_PUBLISHED,
    MASTRA_PKG_VERSION,
    MASTRA_REPO,
    MASTRA_REPO_HEAD,
    MASTRA_REPO_HEAD_DATE,
    MASTRA_REPO_HEAD_MESSAGE,
    MASTRA_SECURITY_CONTACT,
    MASTRA_TAG,
    MASTRA_TAG_COMMIT,
    MASTRA_TAG_DATE,
    MASTRA_TAG_MESSAGE,
    mastra_agent,
    shutdown,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "mastra")
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
                mastra_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the Mastra (non-)effect lives
            # here, not in the section verdict (worst-case over the
            # battery). Compact each attack to kind + vector /
            # encoding + outcome; the evidence text lives in the
            # re-probe log.
            attacks = []
            for a in sections["stress"].get("attacks", []):
                entry = {
                    "kind": a.get("kind"),
                    "vector": a.get("vector") or a.get("encoding"),
                    "survived": a.get("survived"),
                    "detected": a.get("detected"),
                    "completed": a.get("completed"),
                }
                if a.get("visibility_class"):
                    entry["visibility_class"] = a.get("visibility_class")
                attacks.append(entry)
            rows.append({
                "agent": "mastra",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("mastra x %s -> %s (contract %s, stress %s, consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]))
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "mastra",
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
            print("mastra x %s -> CRASH (%s: %s)"
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
        shutdown()
        return
    summary = {
        "product": "Mastra (mastra-ai/mastra, npm @mastra/core 1.83.0, real Agent.generate loop)",
        "component": "Mastra's real Agent.generate loop (@mastra/core 1.83.0, Agent from @mastra/core/agent) in a fresh Agent + fresh deterministic stub LanguageModelV2 per call, holding the whole Trustrun tool set via the adapter's localhost tool bridge (each tool is a real Mastra createTool whose execute POSTs to a Python bridge that runs the harness tool in-process, including poisoned wrappers and raising tools; the bridge returns the exception text and the Node tool throws it, so Mastra's own tool-error path runs). The stub is the audit-30 DeterministicChatModel decision logic ported to JavaScript (literal model). No key, no network. The framework runs the model loop, the tool dispatch, the message-list conversion, and passes tool results to the model verbatim as tool-result parts; it performs no sanitization, filtering, or flagging of tool results on this path.",
        "version": "Mastra @mastra/core %s (npm %s, published %s; audited code is the installed 1.83.0 package, byte-identical to the published tarball and to the tag tree for the checked source file)" % (
            MASTRA_CORE_VERSION, MASTRA_CORE_NPM, MASTRA_CORE_PUBLISHED),
        "repo": MASTRA_REPO,
        "repo_resolved": "https://github.com/mastra-ai/mastra, tag %s %s (commit %s, '%s'). npm @mastra/core %s published %s (tarball https://registry.npmjs.org/@mastra/core/-/core-1.83.0.tgz); umbrella package mastra %s published %s from the same commit. Installed package byte-identical to a fresh npm pack of the same version (diff -rq clean); the dist sourcemap's embedded source for packages/core/src/stream/aisdk/v5/transform.ts is byte-identical to that file at the tag. Default-branch HEAD %s (commit %s, '%s') is NEWER than the release, so the audited code is the 1.83.0 release, not HEAD. The repo is actively maintained (last pushed %s). No SECURITY.md exists anywhere (404 at the tag and at main; no SECURITY.* file in the tag tree). The README DOES carry a Security section naming %s for responsible disclosure. Mastra is the first TypeScript framework in the rotation; the audited object is its Agent.generate loop -- see the adapter docstring for the wiring facts." % (
            MASTRA_TAG, MASTRA_TAG_COMMIT,
            MASTRA_TAG_DATE, MASTRA_TAG_MESSAGE,
            MASTRA_CORE_VERSION, MASTRA_CORE_PUBLISHED,
            MASTRA_PKG_VERSION, MASTRA_PKG_PUBLISHED,
            MASTRA_REPO_HEAD,
            MASTRA_REPO_HEAD_DATE, MASTRA_REPO_HEAD_MESSAGE,
            MASTRA_LAST_PUSH, MASTRA_SECURITY_CONTACT),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic ported VERBATIM to JavaScript in stub-model.mjs, served to Mastra as a LanguageModelV2 stub -- doGenerate returns content parts, doStream replays the same decision as stream parts; a tool-call part's input is a JSON string because Mastra's V2->V5 conversion calls .replace on it and an object input crashes the loop, measured in the probe; see real_agents/mastra_adapter.py and trustrun-venvs/mastra-venv/)",
        "confirmation_gate": "ABSENT by default, measured: (1) file writes are NOT gated on this path: a write_file probe tool forced through the real Agent.generate loop executed with no approval step (1/1 executions, re-probe section 10); shell execution is likewise NOT gated: an exec_shell probe tool executed with no approval step (1/1). (2) Mastra ships an opt-in per-tool approval surface (RequireToolApproval / requireApproval: 183 'approval' and 30 'requireApproval' hits across the agent/tools type declarations, concentrated in the durable-workflows approval/suspension machinery); nothing on the audited path enables it by default, and the audited Agent was built with no requireApproval set. (3) no sanitization, filtering, or flagging of tool results on this path: the 14 'sanitize' hits are message-pair/name/UI hygiene only (sanitizeOrphanedToolPairs, sanitizeToolName, sanitizeAIV4/V5UIMessages, sanitizeToolId); zero hits for require_confirmation / human_in_the_loop. (4) an unregistered tool name is NOT dispatched: the loop returns an error-text tool result 'Tool \"no_such_tool\" not found. Available tools: search_docs. Call tools by their exact name only -- never add prefixes, namespaces, or colons.' and the model sees it as an observation (measured in the re-probe); a tool result containing tool JSON does NOT execute (it is inert text in a tool-result part, not a dispatch -- measured in the re-probe). (5) tool-failure channel: a raising tool becomes an error-text tool result carrying the raw exception message with no failure marker added by the framework; the harness's 'injected tool failure' message is flagged (caught class), but a marker-less message ('search service is down') is echoed as the final answer, unflagged (measured in the re-probe).",
        "tool_calls": dict(ad_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(ad_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    shutdown()
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
