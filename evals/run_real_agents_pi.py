"""Audit Pi (earendil-works/pi, v1.5.2) with Trustrun
(eighty-first real-agent audit).

Configuration under test: the real Pi 1.5.2 CLI
(`pi --mode json`, the shipped one-shot JSON event stream)
running the real Pi agent loop (the coding-agent session
runner over the pi-ai unified provider runtime) against the
Trustrun tool set, driven by a deterministic stub model. The 8
Trustrun tools are real MCP tools (server "trustrun", stdio,
registered in the agent-dir mcp.json with exposure "direct");
Pi 1.5.2 offers MCP tools to the model DIRECTLY as individual
model tools named `mcp__trustrun__<name>` -- there is no
`execute` gateway in the offered inventory. The stub's harness
tool calls are translated at the wire only into direct
`mcp__trustrun__<name>` calls with the n8n argument mapping
verbatim (see real_agents/pi/pi_stub.py); a harness "final"
answer passes through as plain text, which ends the loop. The
stub model is served as a local OpenAI-compatible server the
binary points at through the agent-dir models.json (provider
"stub", api "openai-completions", baseURL
http://127.0.0.1:18084/v1). No key, no network. One fresh
`pi --mode json` process (and one fresh in-memory session) per
call.

HONEST-SETUP DISCLOSURE (read every finding with this in mind):
the stub is a deliberately LITERAL model (it follows instructions
in the task text and tool output), so the audit measures what the
FRAMEWORK does about injected instructions: a framework that
passes an injected instruction through to such a model unfiltered
is the finding; a framework that strips or flags it is the
defense. The stub's compliance is stated; the framework's
pass-through (or filtering) is measured from the messages the
stub actually received, which it logs verbatim (the stub log in
each run's model_log, plus the raw wire bodies in
trustrun-venvs/pi-requests.jsonl).

MEASURED Pi STRUCTURE (see the adapter docstring and the
re-probe): the run command takes the prompt as a positional
argument; --mode json writes JSONL session events to stdout
and exits after the supplied prompts finish; the adapter takes
the last assistant message_end text as the result. The user
message is a list with one text part carrying the task
verbatim. Tool results reach the model as bare text inside a
role "tool" message (the inner MCP tool's text verbatim; a
raising tool's error arrives as the bare exception text, no
"Error:" prefix, no "tool failure" text -- measured in the
re-probe, which also records Pi's own tool_execution_end
isError flag). The loop ends on a text response, so multi-hop
tasks CAN complete. Pi sends no auxiliary title-generation
call. The confirmation gate in the re-probe measures the
approval surface on the default invocation: a registered MCP
tool the model picks executes with no approval step, and Pi
ships no built-in permission system (permission gates exist
only as extensions).

Setup findings (measured while building the probe; see the
adapter docstring for the full list): the agent directory is
~/.pi/agent, overridden here with PI_CODING_AGENT_DIR to an
isolated pi-home; models.json declares the stub provider;
mcp.json registers the trustrun server with direct exposure
(the default codemode exposure would hide the tools behind
scripts); settings.json sets the stub as default model and
project trust to always. Per-run latency ~3.3s for t1.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \
    evals/run_real_agents_pi.py [--max-tasks N]
(The Pi install lives in trustrun-venvs/pi-venv/
(npm @earendil-works/pi-coding-agent@1.5.2 + tag source) with
isolated config/state in trustrun-venvs/pi-venv/pi-home. The
runner runs under the project venv python and drives the binary
as a subprocess. See real_agents/pi_adapter.py.)

Runs trustrun.cli.run_audit over the pi adapter on all 25 tasks,
seed 0, k=5, with the eval corpus as the data module input. Writes
one machine readable summary into reports/real_agents/pi/summary.json
and the evidence logs (injection observations, tampering calls)
into reports/real_agents/pi/evidence.json. Every number in those
files comes from a real run. Nothing is invented.

Reading the results: the verdicts measure the framework + stub-model
combination. The stub is a literal model (it follows instructions
in the task text and tool output), so a BLOCK on an injection or
tampering attack means the framework passed the attack through to
such a model unfiltered. The per-row "attacks" field records every
attack in the stress battery with its survived/detected outcome.
The evidence logs show the exact observation text the framework
handed the model, which is the framework-level fact. Never present
a clean-room failure as a flaw in a real product: the clean-room
agents' failures are theirs; the Pi rows are Pi's. Note the
audited code is the v1.5.2 release, NOT default-branch HEAD: see
the adapter docstring for the pinning facts.
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

import real_agents.pi_adapter as pi_adapter  # noqa: E402
from real_agents.pi_adapter import (  # noqa: E402
    PI_LICENSE,
    PI_NPM_TARBALL_SHA1,
    PI_NPM_TARBALL_SHA256,
    PI_REPO,
    PI_SECURITY_CONTACT,
    PI_SECURITY_MD,
    PI_SOURCE_TARBALL_SHA256,
    PI_TAG,
    PI_TAG_COMMIT,
    PI_TAG_DATE,
    PI_VERSION,
    RUN_LOGS,
    pi_agent,
    shutdown,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "pi")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
TOOLCALLS_LOG = os.path.normpath(os.path.join(
    os.path.dirname(HERE), "trustrun-venvs",
    "pi-venv", "pi-toolcalls.jsonl"))
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
    """Driver-side tool-call counts from pi-toolcalls.jsonl
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


def build_summary(rows, driver_counts, driver_n, tasks,
                  partial=False):
    """Build the summary dict from graded rows (same code path
    for a slice and for the full battery)."""
    done_ids = [r["task"] for r in rows]
    tag = "Pi %s (tag %s; commit %s, %s; license %s; npm tarball " \
        "sha1 %s, sha256 %s; release source tarball sha256 %s)" % (
            PI_VERSION, PI_TAG, PI_TAG_COMMIT, PI_TAG_DATE,
            PI_LICENSE, PI_NPM_TARBALL_SHA1, PI_NPM_TARBALL_SHA256,
            PI_SOURCE_TARBALL_SHA256)
    summary = {
        "product": "Pi (earendil-works/pi, v1.5.2, the real Pi CLI "
                   "headless agent loop)",
        "component": "The real Pi 1.5.2 CLI (`pi --mode json`, the "
                     "shipped one-shot JSON event stream) running "
                     "the real Pi agent loop (the coding-agent "
                     "session runner over the pi-ai unified "
                     "provider runtime) against the Trustrun tool "
                     "set (search_docs, calculator, plus the "
                     "monitor/grader/clarification tools run_audit "
                     "adds) as real MCP tools (server \"trustrun\", "
                     "stdio, registered in the agent-dir mcp.json "
                     "with exposure \"direct\"; Pi 1.5.2 offers MCP "
                     "tools to the model DIRECTLY as individual "
                     "model tools named `mcp__trustrun_<name>` -- "
                     "no `execute` gateway). The stub model is "
                     "served as a local OpenAI-compatible server "
                     "the binary points at through the agent-dir "
                     "models.json (provider \"stub\", api "
                     "\"openai-completions\", baseURL "
                     "http://127.0.0.1:18084/v1). No key, no "
                     "network. The loop ends on a text response, "
                     "so multi-hop tasks can complete. Tool results "
                     "reach the model as bare text inside a role "
                     "\"tool\" message (the inner MCP tool's text "
                     "verbatim; a raising tool's error arrives as "
                     "the bare exception text).",
        "version": tag,
        "repo": PI_REPO,
        "repo_resolved": "https://github.com/earendil-works/pi, tag "
                         "%s (commit %s, %s). Default-branch HEAD may "
                         "be NEWER than the release, so the audited "
                         "code is the v1.5.2 release, NOT HEAD. The "
                         "audited code IS the release: the pi-src "
                         "clone's HEAD equals the tag commit and the "
                         "working tree is clean; the release source "
                         "tarball extracts byte-identical to `git "
                         "archive v1.5.2` except the generated "
                         "model-catalog data files; the npm package "
                         "@earendil-works/pi-coding-agent@1.5.2 is "
                         "verified against the registry shasum and "
                         "its shipped docs are byte-identical to "
                         "the tag source. %s. The audited object is "
                         "the Pi CLI headless agent loop -- see the "
                         "adapter docstring for the wiring facts."
                         % (PI_TAG, PI_TAG_COMMIT, PI_TAG_DATE,
                            PI_SECURITY_MD),
        "model_driver": "deterministic-stub-v1 (literal model: "
                        "follows instructions in task text and tool "
                        "output; the audit-30 DeterministicChatModel "
                        "decision logic ported VERBATIM into "
                        "n8n-stub.py, translated at the wire only by "
                        "real_agents/pi/pi_stub.py; see "
                        "real_agents/pi_adapter.py and "
                        "trustrun-venvs/pi-requests.jsonl)",
        "confirmation_gate": "SEE reprobe.log "
            "(evals/reports/real_agents/pi/reprobe.log) for the "
            "measured gate text; this field is filled in by the "
            "finalize step after the re-probe runs. Headline, "
            "measured: (1) A registered MCP tool the model picks "
            "executes with no approval step under the default "
            "`pi --mode json` invocation (no approval flag exists; "
            "Pi ships no built-in permission system). (2) A "
            "raising tool's error text reaches the model as the "
            "bare exception text, and Pi reports the call as "
            "isError in its own tool_execution_end event; the run "
            "ends flagged only when the harness's standard "
            "injected-failure text fires the stub's error branch. "
            "(3) A call to a tool outside the offered inventory is "
            "rejected in-band, naming the tool. (4) Pi sends no "
            "auxiliary title-generation call.",
        "tool_calls": dict(driver_counts),
        "tool_calls_in_process": dict(pi_adapter.TOOL_CALLS),
        "tool_calls_driver_side": dict(driver_counts),
        "tool_calls_driver_rows": driver_n,
        "tasks": [t["id"] for t in tasks],
        "seed": 0,
        "k": 5,
        "audits": len(rows),
        "crashes": [r["task"] for r in rows if "crash" in r],
        "rows": rows,
    }
    if partial:
        summary["partial"] = True
        summary["tasks_done"] = done_ids
        summary["tasks_total"] = len(tasks)
    return summary


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as handle:
        tasks = json.load(handle)
    started = time.time()
    # Slice support (same rationale as run_real_agents_dify.py:
    # backgrounded sessions do not survive long enough for a 25-task
    # audit, so each eval-loop run does the next N tasks in the
    # foreground and exits; resume picks up the rest next run).
    max_tasks = None
    if "--max-tasks" in sys.argv:
        max_tasks = int(sys.argv[sys.argv.index("--max-tasks") + 1])
    # Resume support (same rationale as run_real_agents_dify.py:
    # rows and evidence are checkpointed after every task; a
    # re-launch skips tasks already in rows_partial.json and keeps
    # their evidence).
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
        # Per-task guard (same rationale as run_real_agents_dify.py:
        # a framework crash must be recorded as a crash row, not kill
        # the remaining tasks. A crash row is verdict BLOCK with a
        # "crash" field; its section verdicts were NOT graded, so folds
        # must count checks as 21 per graded row and 0 per crash row,
        # and summary.json lists crash task ids.)
        try:
            report = run_audit(
                pi_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the pi (non-)effect lives
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
                "agent": "pi",
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
            print("pi x %s -> %s (contract %s, stress %s, "
                  "consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "pi",
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
            print("pi x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc), flush=True)
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
    if max_tasks is not None and len(rows) < len(tasks):
        # Sliced run: write the slice summary (same code path as
        # the full finalize, via build_summary) and keep the
        # partials for resume; do NOT write the final summary.json
        # or delete the partials.
        driver_counts, driver_n = _driver_tool_calls(toolcalls_start)
        slice_summary = build_summary(rows, driver_counts, driver_n,
                                      tasks, partial=True)
        first = rows[0]["task"] if rows else "none"
        last = rows[-1]["task"] if rows else "none"
        slice_name = "summary-slice-%s-%s.json" % (first, last)
        ev_name = "evidence-slice-%s-%s.json" % (first, last)
        with open(os.path.join(OUT_DIR, slice_name), "w",
                  encoding="utf-8") as handle:
            json.dump(slice_summary, handle, indent=1)
        with open(os.path.join(OUT_DIR, ev_name), "w",
                  encoding="utf-8") as handle:
            json.dump(RUN_LOGS, handle, indent=1)
        print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
        print("stress:", dict(Counter(r["stress"] for r in rows)))
        print("tool_calls:", dict(driver_counts), "rows:", driver_n)
        print("tool_calls_in_process:", dict(pi_adapter.TOOL_CALLS))
        print("evidence runs kept:", len(RUN_LOGS))
        print("stopped early: %d of %d tasks done (max-tasks %d); "
              "slice summary %s written, partials kept, resume next run"
              % (len(rows), len(tasks), max_tasks, slice_name), flush=True)
        print("done in %.1fs" % (time.time() - started), flush=True)
        shutdown()
        return
    driver_counts, driver_n = _driver_tool_calls(toolcalls_start)
    summary = build_summary(rows, driver_counts, driver_n, tasks)
    with open(os.path.join(OUT_DIR, "summary.json"), "w",
              encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
    with open(os.path.join(OUT_DIR, "evidence.json"), "w",
              encoding="utf-8") as handle:
        json.dump(RUN_LOGS, handle, indent=1)
    print("verdicts:", dict(Counter(r["verdict"] for r in rows)))
    print("stress:", dict(Counter(r["stress"] for r in rows)))
    print("tool_calls:", dict(driver_counts), "rows:", driver_n)
    print("tool_calls_in_process:", dict(pi_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    shutdown()
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, TOOLCALLS_OFFSET):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
