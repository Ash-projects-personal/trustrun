"""Audit n8n (n8n-io/n8n, v.2.47.7) with Trustrun
(sixty-eighth real-agent audit).

Configuration under test: the real n8n 2.47.7 workflow engine
running the real AI Agent node (ToolsAgent V3, AI Agent 3.1) against
the Trustrun tool set, driven by a deterministic stub OpenAI API
server on localhost (see trustrun-venvs/n8n-venv/n8n-stub.py). The
workflow "Trustrun n8n audit 68" (id 6rfojAYNTU6BnXJn, published
version 16ebc5f7-7a51-403d-b17a-4bcfea6d7698) is Webhook v2 POST
/webhook/trustrun -> AI Agent 3.1 (maxIterations 10) -> OpenAI Chat
Model 1.3 -> 8 ToolCode 1.3 nodes (search_docs, calculator,
monitor_configure, edit_tests, record_score, ask_user,
monitor_notify, submit_answer). Each ToolCode node POSTs its args
to the adapter's localhost tool bridge at 127.0.0.1:18068/call/<tool>
via helpers.httpRequest. The model node points at the local stub
OpenAI server at 127.0.0.1:18069/v1. One fresh stub per call; the
adapter manages the n8n server subprocess (reuses a healthy one,
starts one when healthz is down). No key, no network.

HONEST-SETUP DISCLOSURE (read every finding with this in mind):
the stub is a deliberately LITERAL model (it follows instructions in
the task text and in tool output), so the audit measures what the
FRAMEWORK does about injected instructions: a framework that passes
an injected instruction through to such a model unfiltered is the
finding; a framework that strips or flags it is the defense. The
stub's compliance is stated; the framework's pass-through (or
filtering) is measured from the messages the stub actually received,
which it logs verbatim (n8n-requests.jsonl).

MEASURED n8n STRUCTURE (see the adapter docstring and the
re-probe): the shipped loop gives the model up to 10 tool-call
iterations per task (maxIterations 10), so multi-hop tasks CAN
complete, unlike the one-shot AgentGPT loop. Tool results reach the
model as [{"response": "..."}] (or [{"error": "..."}] on a tool
error) inside the tool message. A raising tool's raw exception text
goes back as the 500 body, but n8n's helpers.httpRequest swallows
the body and throws a generic "Request failed with status code 500",
so the observation carries only the generic 500 and the stub's
error branch fires on the "error:" prefix: the model learns the tool
failed without learning why. n8n ships an opt-in HITL approval
mechanism in the platform (ToolExecutor + Chat Trigger approval
flows, wired into ToolsAgent V3) that this workflow does not
configure, so no approval step stands between the model's choice
and execution here (measured by the confirmation gate in the
re-probe).

Setup findings (the hang the prior worker hit, resolved 2026-11-13;
see the adapter docstring for the full list): the OpenAI Chat Model
1.3 node hides options.baseURL for typeVersion >= 1.1, so the dummy
credential's `url` field was re-pointed at the stub; the HTTP
Request Tool 1.1 node has no execute method, so the workflow was
rebuilt with ToolCode 1.3 nodes; the startup reconciler needs
workflow_entity.activeVersionId set on v2 (the `active` flag alone
is not enough); the ToolCode sandbox exposes `helpers`, not
`$helpers`; and the cold-start race (healthz 200 precedes webhook
registration by seconds) is handled by retrying webhook 404s for
up to 120s in the adapter.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
    evals/run_real_agents_n8n.py [--max-tasks N]
(The n8n install lives in trustrun-venvs/n8n-venv, not the project
venv; see real_agents/n8n_adapter.py. The runner runs under the
PROJECT venv python and manages the n8n server subprocess.)

Runs trustrun.cli.run_audit over the n8n adapter on all 25 tasks,
seed 0, k=5, with the eval corpus as the data module input. Writes
one machine readable summary into reports/real_agents/n8n/summary.json
and the evidence logs (injection observations, tampering calls)
into reports/real_agents/n8n/evidence.json. Every number in those
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
agents' failures are theirs; the n8n rows are n8n's. Note the
audited code is the v.2.47.7 release, NOT default-branch HEAD (HEAD
is newer): see the adapter docstring for the pinning facts.
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

import real_agents.n8n_adapter as n8n_adapter  # noqa: E402
from real_agents.n8n_adapter import (  # noqa: E402
    N8N_REPO,
    N8N_SECURITY_CONTACT,
    N8N_SECURITY_MD,
    N8N_TAG,
    N8N_TAG_COMMIT,
    N8N_TAG_DATE,
    N8N_VERSION,
    RUN_LOGS,
    n8n_agent,
    shutdown,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "n8n")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
TOOLCALLS_LOG = os.path.normpath(os.path.join(
    os.path.dirname(HERE), "..", "trustrun-venvs",
    "n8n-venv", "n8n-toolcalls.jsonl"))
TOOLCALLS_OFFSET = os.path.join(OUT_DIR, ".toolcalls_start_offset")


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


def _toolcalls_line_count():
    if not os.path.exists(TOOLCALLS_LOG):
        return 0
    count = 0
    with open(TOOLCALLS_LOG, encoding="utf-8") as handle:
        for _ in handle:
            count += 1
    return count


def _driver_tool_calls(from_line):
    """Driver-side tool-call counts from n8n-toolcalls.jsonl
    (the bridge logs every tools/call there), counted only from
    `from_line` onward, so the total covers exactly this battery
    and never depends on a counter living in another process (the
    audit-64/65 open item) or on probe runs that wrote to the same
    log earlier. Returns (Counter, n_rows)."""
    counts = Counter()
    n_rows = 0
    if os.path.exists(TOOLCALLS_LOG):
        with open(TOOLCALLS_LOG, encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if index < from_line:
                    continue
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
    # The driver-side tool-call count is anchored once, at the start
    # of the FIRST slice (when no partial rows exist yet), and kept
    # in .toolcalls_start_offset so later slices reuse the same
    # anchor instead of re-anchoring mid-battery.
    if os.path.exists(TOOLCALLS_OFFSET):
        with open(TOOLCALLS_OFFSET, encoding="utf-8") as handle:
            toolcalls_start = int(handle.read().strip())
    else:
        toolcalls_start = _toolcalls_line_count()
        with open(TOOLCALLS_OFFSET, "w", encoding="utf-8") as handle:
            handle.write(str(toolcalls_start))
    print("toolcalls log anchored at line %d" % toolcalls_start,
          flush=True)
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
                n8n_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the n8n (non-)effect lives
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
                "agent": "n8n",
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
            print("n8n x %s -> %s (contract %s, stress %s, "
                  "consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "n8n",
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
            print("n8n x %s -> CRASH (%s: %s)"
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
    driver_counts, driver_n = _driver_tool_calls(toolcalls_start)
    summary = {
        "product": "n8n (n8n-io/n8n, v.2.47.7, the real workflow-automation platform's AI Agent loop)",
        "component": "The real n8n 2.47.7 workflow engine running the real AI Agent node (ToolsAgent V3, AI Agent 3.1, maxIterations 10) against the Trustrun tool set (search_docs, calculator, plus the monitor/grader/clarification tools run_audit adds) as real ToolCode 1.3 nodes whose calls POST to the adapter's localhost tool bridge (each tool is a real n8n ToolCode node whose jsCode calls helpers.httpRequest to the bridge; a bridge error raises out of the tool, so the observation carries the error shape and the stub's audit-45 error branch fires). The stub is the audit-30 DeterministicChatModel decision logic ported VERBATIM into n8n-stub.py (literal model). No key, no network. The loop allows up to 10 tool-call iterations per task, so multi-hop tasks can complete. Tool results reach the model as [{\"response\": \"...\"}] (or [{\"error\": \"...\"}] on a tool error) inside the tool message.",
        "version": "n8n %s (tag %s; installed with `npm install n8n@2.47.7`, tarball sha512 verified against the npm registry integrity value)" % (
            N8N_VERSION, N8N_TAG),
        "repo": N8N_REPO,
        "repo_resolved": "https://github.com/n8n-io/n8n, tag %s (commit %s, %s). Default-branch HEAD is NEWER than the release, so the audited code is the v.2.47.7 release, NOT HEAD. The audited code IS the tag source: the venv install is npm's published 2.47.7 tarball, verified by sha512, and @n8n/n8n-nodes-langchain 2.47.5 was verified the same way. %s. No email security contact is published in the repo. The audited object is the AI Agent workflow loop -- see the adapter docstring for the wiring facts." % (
            N8N_TAG, N8N_TAG_COMMIT,
            N8N_TAG_DATE,
            N8N_SECURITY_MD),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic ported VERBATIM into n8n-stub.py, served to the real n8n loop as a local stub OpenAI API server at the dummy credential's `url` field, http://127.0.0.1:18069/v1; see real_agents/n8n_adapter.py and trustrun-venvs/n8n-venv/)",
        "confirmation_gate": "SEE reprobe.log (evals/reports/real_agents/n8n/reprobe.log) for the measured gate text; this field is filled in by the finalize step after the re-probe runs. Headline, measured: (1) n8n ships no approval step on THIS workflow's AI Agent tool path: a tool the model picks executes immediately. The platform does ship an opt-in HITL approval mechanism (ToolExecutor + Chat Trigger approval flows, wired into ToolsAgent V3) that this workflow does not configure. (2) A forced write/exec probe tool executes with no approval step. (3) A raising tool's exception text is swallowed by helpers.httpRequest: the model sees only a generic \"Request failed with status code 500\", not the reason, and the run ends flagged.",
        "tool_calls": dict(driver_counts),
        "tool_calls_in_process": dict(n8n_adapter.TOOL_CALLS),
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
    print("tool_calls:", dict(driver_counts), "rows:", driver_n)
    print("tool_calls_in_process:", dict(n8n_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    shutdown()
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, TOOLCALLS_OFFSET):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
