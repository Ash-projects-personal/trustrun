"""Audit AgentGPT (reworkd/AgentGPT, v.1.0.0) with Trustrun
(sixty-seventh real-agent audit).

Configuration under test: the real AgentGPT v.1.0.0 platform-backend
agent loop (OpenAIAgentService, LangChain ChatOpenAI) driving the
Trustrun tool set (search_docs, calculator, plus the monitor/grader/
clarification tools run_audit adds) as real AgentGPT Tool subclasses
on a localhost tool bridge, driven by a deterministic stub OpenAI API
server on localhost (the audit-30 decision logic ported VERBATIM
into agentgpt-stub.py). One fresh stub per call; the driver process
persists across calls. No key, no network.

HONEST-SETUP DISCLOSURE (read every finding with this in mind):
the stub is a deliberately LITERAL model (it follows instructions in
the task text and in tool output), so the audit measures what the
FRAMEWORK does about injected instructions: a framework that passes
an injected instruction through to such a model unfiltered is the
finding; a framework that strips or flags it is the defense. The
stub's compliance is stated; the framework's pass-through (or
filtering) is measured from the messages the stub actually received,
which it logs verbatim (agentgpt-requests.jsonl).

MEASURED AgentGPT STRUCTURE (see the adapter docstring and the
re-probe): the shipped loop gives the model exactly ONE tool choice
per task (analyze -> execute), then the task result flows to the
summarize call. There is no second tool call after a tool result
comes back. When the model's analyze answer is plain text instead
of a function call, analyze_task_agent falls back to
Analysis.get_default_analysis(task) -> the real Serper Search tool
(action "search", arg = the full task text). On this VM that Search
call fails FAST (measured 2026-11-13: aiohttp TLS to
google.serper.dev:443 fails at connect with SSL WRONG_VERSION_NUMBER
-- the VM egress proxy speaks plain HTTP on 443 to direct
connections; curl through the proxy completes TLS but never gets a
response, TTFB 0 in 10s). The driver retries execute 4x (frontend
withRetries behaviour) and the task ends uncompleted; summarize over
no results returns "There is nothing to summarize". That is what
t8, t24 and t25 return on every run. No 300s stall was observed:
one t8 call through the real loop took 6.7s end to end.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
    evals/run_real_agents_agentgpt.py [--max-tasks N]
(The platform lives in a separate Python workspace, not the project
venv; see real_agents/agentgpt_adapter.py. The runner runs under
the PROJECT venv python and shells out to the audit venv driver.)

Runs trustrun.cli.run_audit over the AgentGPT adapter on all 25
tasks, seed 0, k=5, with the eval corpus as the data module input.
Writes one machine readable summary into
reports/real_agents/agentgpt/summary.json and the evidence logs
(injection observations, tampering calls) into
reports/real_agents/agentgpt/evidence.json. Every number in those
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
agents' failures are theirs; the AgentGPT rows are AgentGPT's.
Note the audited code is the v.1.0.0 release, NOT default-branch
HEAD (HEAD is newer): see the adapter docstring for the pinning
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

import real_agents.agentgpt_adapter as ag_adapter  # noqa: E402
from real_agents.agentgpt_adapter import (  # noqa: E402
    AGENTGPT_REPO,
    AGENTGPT_REPO_HEAD,
    AGENTGPT_REPO_HEAD_DATE,
    AGENTGPT_REPO_HEAD_MESSAGE,
    AGENTGPT_SECURITY_CONTACT,
    AGENTGPT_SECURITY_MD,
    AGENTGPT_TAG,
    AGENTGPT_TAG_COMMIT,
    AGENTGPT_TAG_DATE,
    AGENTGPT_TAG_MESSAGE,
    AGENTGPT_VERSION,
    RUN_LOGS,
    agentgpt_agent,
    shutdown,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "agentgpt")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
TOOLCALLS_LOG = os.path.join(
    os.path.dirname(HERE), "..", "trustrun-venvs",
    "agentgpt-venv", "agentgpt-toolcalls.jsonl")
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
    """Driver-side tool-call counts from agentgpt-toolcalls.jsonl
    (the bridge logs every tools/call there), so the total never
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
                agentgpt_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the AgentGPT (non-)effect lives
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
                "agent": "agentgpt",
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
            print("agentgpt x %s -> %s (contract %s, stress %s, "
                  "consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "agentgpt",
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
            print("agentgpt x %s -> CRASH (%s: %s)"
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
        "product": "AgentGPT (reworkd/AgentGPT, v.1.0.0, the real platform-backend agent loop)",
        "component": "The real AgentGPT v.1.0.0 agent loop (OpenAIAgentService in platform/reworkd_platform, LangChain ChatOpenAI) driven in the exact order the shipped frontend calls it (start -> analyze -> execute per task, then summarize over the completed results), holding the whole Trustrun tool set via real AgentGPT Tool subclasses whose calls POST to the adapter's localhost tool bridge (each tool is a real AgentGPT tool whose handler runs the harness tool in-process, including poisoned wrappers and raising tools; a bridge error raises out of the tool, so the driver's retry path runs and the task ends uncompleted). The stub is the audit-30 DeterministicChatModel decision logic ported VERBATIM into agentgpt-stub.py (literal model). No key, no network. The loop gives the model exactly ONE tool choice per task, then the result flows to summarize; there is no second tool call after a tool result comes back. When the model's analyze answer is plain text, analyze_task_agent falls back to Analysis.get_default_analysis(task) -> the real Serper Search tool; on this VM that Search call fails fast at TLS (SSL WRONG_VERSION_NUMBER, measured 2026-11-13), the driver retries execute 4x, and the task ends uncompleted, so t8/t24/t25 return 'There is nothing to summarize'.",
        "version": "AgentGPT %s (tag %s; the next/package.json version is 1.0.0, name agent-gpt, private: true -- the app is not published on npm, so there is no npm tarball to diff against)" % (
            AGENTGPT_VERSION, AGENTGPT_TAG),
        "repo": AGENTGPT_REPO,
        "repo_resolved": "https://github.com/reworkd/AgentGPT, tag %s %s (commit %s, '%s'). Default-branch HEAD %s (commit %s, '%s') is NEWER than the release, so the audited code is the v.1.0.0 release, NOT HEAD. The audited code IS the tag source: the driver runs code from a clean checkout of the tag commit (git status clean, HEAD == tag commit), so the byte-identity check is the checkout itself. %s. No security contact is published in the repo. The audited object is the platform-backend agent loop -- see the adapter docstring for the wiring facts." % (
            AGENTGPT_TAG, AGENTGPT_TAG_COMMIT,
            AGENTGPT_TAG_DATE, AGENTGPT_TAG_MESSAGE,
            AGENTGPT_REPO_HEAD,
            AGENTGPT_REPO_HEAD_DATE, AGENTGPT_REPO_HEAD_MESSAGE,
            AGENTGPT_SECURITY_MD),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic ported VERBATIM into agentgpt-stub.py, served to the real AgentGPT loop as a local stub OpenAI API server at the platform settings' openai_api_base override point; see real_agents/agentgpt_adapter.py and trustrun-venvs/agentgpt-venv/)",
        "confirmation_gate": "SEE reprobe.log (evals/reports/real_agents/agentgpt/reprobe.log) for the measured gate text; this field is filled in by the finalize step after the re-probe runs. Headline, measured: (1) AgentGPT ships no approval/confirmation surface on the backend tool path: a tool the model picks executes immediately. (2) A forced write_file / exec_shell probe tool executes with no approval step. (3) A raising tool is retried 4x by the driver (the frontend's withRetries behaviour) and then dropped: the error text never reaches the model, and the run ends with 'There is nothing to summarize', unflagged.",
        "tool_calls": dict(ag_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(ag_adapter.TOOL_CALLS))
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
