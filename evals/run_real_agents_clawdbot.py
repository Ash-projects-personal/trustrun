"""Audit OpenClaw (OpenClaw Foundation's open-source agent,
2026.11.5-beta.3) with Trustrun (seventy-eighth real-agent audit).

Configuration under test: the real `openclaw agent exec` headless
loop (tag v2026.11.5-beta.3, commit c2f4dde2638502fe506e234fb43
ac65d8c391072, source built with `pnpm build`) driving the
Trustrun tool set (search_docs, calculator, plus the monitor/grader/
clarification tools run_audit adds) as real MCP tools on a "trustrun"
stdio MCP server (see real_agents/clawdbot_adapter.py), driven by a
deterministic stub OpenAI-compatible API server on localhost (the
audit-30 decision logic ported VERBATIM into the driver). One fresh
stub and CLI session per call; the driver process persists across
calls. No key, no network.

HONEST-SETUP DISCLOSURE (read every finding with this in mind):
the stub is a deliberately LITERAL model (it follows instructions in
the task text and in tool output), so the audit measures what the
FRAMEWORK does about injected instructions: a framework that passes
an injected instruction through to such a model unfiltered is the
finding; a framework that strips or flags it is the defense. The
stub's compliance is stated; the framework's pass-through (or
filtering) is measured from the messages the stub actually received,
which it logs verbatim (clawdbot-requests.jsonl).

Adapter facts measured in the probes (see
trustrun-venvs/clawdbot-venv/probe*.py):
(1) Stub injection is via a custom provider "stub" {baseUrl: stub
/v1, api: "openai-completions", apiKey: secretref-env, models:
[{id: "stub-model"}]}; every model call is POST
{baseUrl}/v1/chat/completions, stream=true.
(2) MCP tools are DEFERRED in 2026.11.5-beta.3: not in the request's
tools array, named trustrun__<tool> (TOOL_NAME_SEPARATOR "__") in
the bridge, reached through the designed tool_search ->
tool_describe -> dispatch_action bridge. A direct MCP-qualified
function call FAILS as "unknown tool" (probes 1 and 3); probes 2
and 4 proved the bridge end to end.
(3) Tool results reach the model as plain text in role=tool
messages, wrapped in an EXTERNAL_UNTRUSTED_CONTENT block.
(4) The harness MCP server runs with no confirmation bypass
configured (the OpenClaw default); whether anything is gated by
default on this path is measured in the re-probe.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
    evals/run_real_agents_clawdbot.py [--max-tasks N]
(The CLI lives in a Node workspace, not the project venv; see
real_agents/clawdbot_adapter.py. The runner runs under the
PROJECT venv python and shells out to the audit venv driver.)

Runs trustrun.cli.run_audit over the OpenClaw adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/clawdbot/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/clawdbot/evidence.json. Every number in those
files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The per-row "attacks" field records every
attack in the stress battery with its survived/detected outcome. The
evidence logs show the exact observation text the framework handed
the model, which is the framework-level fact. Never present a
clean-room failure as a flaw in a real product: the clean-room
agents' failures are theirs; the OpenClaw rows are the CLI's.
Note the audited code is the v2026.11.5-beta.3 tag, NOT
default-branch HEAD: see the adapter docstring for the pinning
facts.
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

import real_agents.clawdbot_adapter as ad_adapter  # noqa: E402
from real_agents.clawdbot_adapter import (  # noqa: E402
    CLAWDBOT_NPM_SHASUM,
    CLAWDBOT_REPO,
    CLAWDBOT_SECURITY_ADVISORY,
    CLAWDBOT_SECURITY_CONTACT,
    CLAWDBOT_TAG,
    CLAWDBOT_TAG_COMMIT,
    CLAWDBOT_TAG_DATE,
    CLAWDBOT_TAG_MESSAGE,
    CLAWDBOT_VERSION,
    RUN_LOGS,
    clawdbot_agent,
    shutdown,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "clawdbot")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
TOOLCALLS_LOG = os.path.join(
    HERE, "..", "trustrun-venvs",
    "clawdbot-venv", "clawdbot-toolcalls.jsonl")
TOOLCALLS_LOG = os.path.normpath(TOOLCALLS_LOG)


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


def _driver_tool_calls():
    """Driver-side tool-call counts from clawdbot-toolcalls.jsonl
    (the MCP server logs every tools/call there), so the total never
    depends on a counter living in another process (the audit-64/65
    open item). Returns (Counter, n_rows)."""
    counts = Counter()
    n_rows = 0
    if os.path.exists(TOOLCALLS_LOG):
        with open(TOOLCALLS_LOG, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                n_rows += 1
                counts[row.get("tool", "?")] += 1
    return counts, n_rows


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
              % (len(done), ", ".join(sorted(done))), flush=True)
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
                clawdbot_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the CLI (non-)effect lives here,
            # not in the section verdict (worst-case over the battery).
            # Compact each attack to kind + vector / encoding +
            # outcome; the evidence text lives in the re-probe log.
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
                "agent": "clawdbot",
                "task": task_def["id"],
                "task_id": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("clawdbot x %s -> %s (contract %s, stress %s, "
                  "consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "clawdbot",
                "task": task_def["id"],
                "task_id": task_def["id"],
                "verdict": "BLOCK",
                "contract": "BLOCK",
                "stress": "BLOCK",
                "consistency": "BLOCK",
                "data": "BLOCK",
                "pass_rate_k": 0.0,
                "attacks": [],
                "crash": "%s: %s" % (type(exc).__name__, exc),
            })
            print("clawdbot x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc), flush=True)
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
    if max_tasks is not None and len(rows) < len(tasks):
        # Sliced run: do NOT write summary.json or delete the partials.
        print("stopped early: %d of %d tasks done (max-tasks %d); "
              "partials kept, resume next run"
              % (len(rows), len(tasks), max_tasks), flush=True)
        print("done in %.1fs" % (time.time() - started), flush=True)
        shutdown()
        return
    driver_counts, driver_n = _driver_tool_calls()
    summary = {
        "product": "OpenClaw (OpenClaw Foundation, openclaw/openclaw 2026.11.5-beta.3, real `openclaw agent exec` headless loop)",
        "component": "The real OpenClaw 2026.11.5-beta.3 headless loop (`openclaw agent exec`, the real CLI loop driving the model calls) in a fresh CLI session + fresh deterministic stub OpenAI-compatible API server per call, holding the whole Trustrun tool set via a real stdio MCP server ('trustrun', clawdbot-mcp-server.py) whose tools POST to the adapter's localhost tool bridge (each tool is a real MCP tool whose handler runs the harness tool in-process, including poisoned wrappers and raising tools; a bridge error becomes an MCP isError result, so the CLI's own MCP error path runs). The stub is the audit-30 DeterministicChatModel decision logic ported VERBATIM into clawdbot-driver.py (literal model). No key, no network. MCP tools are DEFERRED in 2026.11.5-beta.3 (not in the request's tools array; named trustrun__<tool> in the bridge, reached through the designed tool_search -> tool_describe -> dispatch_action bridge). The framework runs the model loop, the tool dispatch, and the message-list conversion, and passes tool results to the model as plain text in role=tool messages wrapped in an EXTERNAL_UNTRUSTED_CONTENT block (measured). The harness MCP server runs with no confirmation bypass configured (the OpenClaw default).",
        "version": "openclaw %s (tag %s, commit %s, %s, '%s'; npm tarball sha1 %s matches the registry dist.shasum)" % (
            CLAWDBOT_VERSION, CLAWDBOT_TAG, CLAWDBOT_TAG_COMMIT,
            CLAWDBOT_TAG_DATE, CLAWDBOT_TAG_MESSAGE,
            CLAWDBOT_NPM_SHASUM),
        "repo": CLAWDBOT_REPO,
        "repo_resolved": "https://github.com/openclaw/openclaw, tag %s %s (commit %s, '%s'). The audited code is the tag source built with `pnpm build` (build-all.mts; the dts phase failed with exit 143 SIGKILL after 35m33s, but dist/ is complete and the CLI runs from it). SECURITY.md EXISTS at the tag root: reports go to %s and the private GitHub Security Advisory %s. No draft written, nobody contacted. The audited object is the `openclaw agent exec` headless loop -- see the adapter docstring for the wiring facts." % (
            CLAWDBOT_TAG, CLAWDBOT_TAG_COMMIT,
            CLAWDBOT_TAG_DATE, CLAWDBOT_TAG_MESSAGE,
            CLAWDBOT_SECURITY_CONTACT, CLAWDBOT_SECURITY_ADVISORY),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic ported VERBATIM into clawdbot-driver.py, served to the real CLI loop as a local stub OpenAI-compatible API server -- the CLI requires a custom provider with a base URL, and the base URL is pointed at the stub; see real_agents/clawdbot_adapter.py and trustrun-venvs/clawdbot-venv/)",
        "confirmation_gate": "SEE reprobe.log (evals/reports/real_agents/clawdbot/reprobe.log) for the measured gate text; this field is filled in by the finalize step after the re-probe runs.",
        "tool_calls": dict(ad_adapter.TOOL_CALLS),
        "tool_calls_driver_side": dict(driver_counts),
        "tool_calls_driver_rows": driver_n,
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
    print("tool_calls_driver_side:", dict(driver_counts),
          "rows:", driver_n)
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    shutdown()
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
