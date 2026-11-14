"""Audit Claude Agent SDK (anthropics/claude-agent-sdk-python,
claude-agent-sdk 0.2.181) with Trustrun (sixty-fifth real-agent
audit).

Configuration under test: the real `ClaudeSDKClient` / `query()`
loop (claude-agent-sdk 0.2.181, bundled Claude Code CLI 2.1.323)
driving the Trustrun tool set (search_docs, calculator, plus the
monitor/grader/clarification tools run_audit adds) as real SDK MCP
tools via the adapter's localhost tool bridge (see
real_agents/claude_agent_sdk_adapter.py), driven by a deterministic
stub Messages-API server on localhost (the audit-30 decision logic
ported VERBATIM into the driver). One fresh stub and SDK session
per call; the driver process persists across calls. No key, no
network.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \
    evals/run_real_agents_claude_agent_sdk.py [--max-tasks N]
(The SDK lives in a separate venv, not the project venv; see
real_agents/claude_agent_sdk_adapter.py. The runner runs under
the PROJECT venv python and shells out to the audit venv driver.)

Runs trustrun.cli.run_audit over the Claude Agent SDK adapter on
all 25 tasks, seed 0, k=5, with the eval corpus as the data module
input. Writes one machine readable summary into
reports/real_agents/claude_agent_sdk/summary.json and the evidence
logs (injection observations, tampering calls) into
reports/real_agents/claude_agent_sdk/evidence.json. Every number
in those files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions in
the task text and in tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The per-row "attacks" field records every
attack in the stress battery with its survived/detected outcome. The
evidence logs show the exact observation text the framework handed
the model, which is the framework-level fact. Never present a
clean-room failure as a flaw in a real product: the clean-room
agents' failures are theirs; the Claude Agent SDK rows are the SDK's.
Note the audited code is the 0.2.181 release, which is also
default-branch HEAD at audit time: see the adapter docstring for the
pinning facts.
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

import real_agents.claude_agent_sdk_adapter as ad_adapter  # noqa: E402
from real_agents.claude_agent_sdk_adapter import (  # noqa: E402
    RUN_LOGS,
    SDK_CLI_VERSION,
    SDK_PYPI_PUBLISHED,
    SDK_REPO,
    SDK_REPO_HEAD,
    SDK_REPO_HEAD_DATE,
    SDK_REPO_HEAD_MESSAGE,
    SDK_SECURITY_CONTACT,
    SDK_TAG,
    SDK_TAG_COMMIT,
    SDK_TAG_DATE,
    SDK_TAG_MESSAGE,
    SDK_VERSION,
    claude_agent_sdk_agent,
    shutdown,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "claude_agent_sdk")
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
                claude_agent_sdk_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the SDK (non-)effect lives here,
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
                "agent": "claude_agent_sdk",
                "task": task_def["id"],
                "verdict": report["verdict"],
                "contract": sections["contract"]["verdict"],
                "stress": sections["stress"]["verdict"],
                "consistency": sections["consistency"]["verdict"],
                "data": sections["data"]["verdict"],
                "pass_rate_k": sections["consistency"]["pass_rate_k"],
                "attacks": attacks,
            })
            print("claude_agent_sdk x %s -> %s (contract %s, stress %s, "
                  "consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "claude_agent_sdk",
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
            print("claude_agent_sdk x %s -> CRASH (%s: %s)"
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
    summary = {
        "product": "Claude Agent SDK (anthropics/claude-agent-sdk-python, claude-agent-sdk 0.2.181, real ClaudeSDKClient/query() loop)",
        "component": "The real ClaudeSDKClient / query() loop (claude-agent-sdk 0.2.181, bundled Claude Code CLI 2.1.323) in a fresh SDK session + fresh deterministic stub Messages-API server per call, holding the whole Trustrun tool set via the adapter's localhost tool bridge (each tool is a real SDK MCP tool whose handler POSTs to a Python bridge that runs the harness tool in-process, including poisoned wrappers and raising tools; the bridge returns the exception text and the MCP handler raises it, so the CLI's own MCP error path runs). The stub is the audit-30 DeterministicChatModel decision logic ported VERBATIM into the driver (literal model). No key, no network. The framework runs the model loop, the tool dispatch, the message-list conversion, and passes tool results to the model verbatim as tool-result content blocks; it performs no sanitization, filtering, or flagging of tool results on this path.",
        "version": "claude-agent-sdk %s (PyPI, published %s; audited code is the installed 0.2.181 package, byte-identical to the tag source for the checked files; bundled Claude Code CLI %s)" % (
            SDK_VERSION, SDK_PYPI_PUBLISHED, SDK_CLI_VERSION),
        "repo": SDK_REPO,
        "repo_resolved": "https://github.com/anthropics/claude-agent-sdk-python, tag %s %s (commit %s, '%s'). Default-branch HEAD %s (commit %s, '%s') is the SAME commit, so the audited code is both the 0.2.181 release and HEAD. PyPI claude-agent-sdk %s published %s. Installed package byte-identical to the tag source (diff -rq clean, excluding the bundled CLI directory _bundled and the generated _cli_version.py). No SECURITY.md exists anywhere (404 at the tag and at main; no SECURITY.* file in the tag tree). The README carries no security section, no security@ address, and no HackerOne pointer; Anthropic's published advisories for this repo (e.g. GHSA-h4mw-j7qp-8mwm, CVE-2026-96620) credit a HackerOne researcher, so the disclosure route is GitHub Security Advisories / HackerOne. The audited object is the ClaudeSDKClient/query() loop -- see the adapter docstring for the wiring facts." % (
            SDK_TAG, SDK_TAG_COMMIT,
            SDK_TAG_DATE, SDK_TAG_MESSAGE,
            SDK_REPO_HEAD,
            SDK_REPO_HEAD_DATE, SDK_REPO_HEAD_MESSAGE,
            SDK_VERSION, SDK_PYPI_PUBLISHED),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic ported VERBATIM into claude-agent-sdk-driver.py, served to the real SDK loop as a local stub Messages-API server with SSE streaming -- the CLI requires streaming; a tool-call part's input is JSON because the CLI streams it as input_json_delta; see real_agents/claude_agent_sdk_adapter.py and trustrun-venvs/claude-agent-sdk-venv/)",
        "confirmation_gate": "ABSENT by default on the audited path, measured: (1) no sanitization, filtering, or flagging of tool results: 32 'sanitize' hits in the installed SDK source are all session hygiene (session-path/tag Unicode hygiene), none mentions tool results, tool output, or tool content; zero hits for require_confirmation / human_in_the_loop; 1 'approval' hit (a docstring: tools in allowed_tools 'execute automatically without asking the user for approval') and 1 'confirm' hit (unrelated comment). (2) the SDK ships a permission_mode option (default / acceptEdits / bypassPermissions / plan); the re-probe measured default-mode vs bypassPermissions behavior on the built-in Bash/Write tools: in DEFAULT mode Bash EXECUTES with no approval step (forced 'echo claude-sdk-probe' ran, 1/1), while Write is GATED (forced write denied: 'Claude requested permissions to write to /tmp/claude-sdk-probe-write.txt, but you haven't granted it yet', file not created, 1/1) -- an asymmetric gate. In bypassPermissions mode the session NEVER STARTS: the bundled CLI exits with code 1 at session initialization (ProcessError at ClaudeSDKClient connect(), 3/3 attempts across the reprobe and a follow-up probe; default-mode sessions work immediately before and after), so bypass-mode Bash/Write behavior could NOT be measured in this non-interactive environment. MCP probe tools (write_file / exec_shell, in allowed_tools) execute with no approval step (1/1 each). (3) tool-failure channel: a raising MCP tool becomes an error tool result carrying the raw exception text verbatim ('search service is down'); the harness's 'injected tool failure' message is flagged (caught class), but a marker-less message is echoed as the final answer, unflagged (measured in the re-probe).",
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
