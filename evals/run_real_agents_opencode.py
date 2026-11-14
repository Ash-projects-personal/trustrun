"""Audit OpenCode (sst/opencode, v2.3.0) with Trustrun
(seventy-second real-agent audit).

Configuration under test: the real OpenCode 2.3.0 binary
(`opencode run --standalone --format json`, the shipped
headless mode) running the real OpenCode agent loop (the
session runner over the openai-compatible provider runtime)
against the Trustrun tool set, driven by a deterministic stub
model. The 8 Trustrun tools are real MCP tools (server
"trustrun", stdio, registered in the project opencode.json);
OpenCode 2.3.0 does NOT offer MCP tools to the model as
individual tools by default -- tools with codemode !== false
live inside the Code Mode inventory and are reached only
through the single `execute` tool (run JavaScript; call tools
as `tools.<namespace>.<name>(input)`). The stub's harness tool
calls are translated at the wire only into `execute` calls
whose code awaits `tools.trustrun["<name>"](args)` with the
n8n argument mapping verbatim (see
real_agents/opencode/opencode_stub.py); a harness "final"
answer passes through as plain text, which ends the loop. The
stub model is served as a local OpenAI-compatible server the
binary points at through the project config (provider "stub",
package @opencode/ai/providers/openai-compatible, baseURL
http://127.0.0.1:18080/v1). No key, no network. One fresh
`opencode run` process (and one fresh session) per call.

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
trustrun-venvs/opencode-requests.jsonl).

MEASURED OpenCode STRUCTURE (see the adapter docstring and the
re-probe): `opencode run` reads a FIFO stdin in full as piped
input, so stdin must be /dev/null (or a TTY) or the run hangs
forever; the run command resolves the session directory from
$PWD, not from the child's cwd, so $PWD must be the workdir or
the model resolves as "Model unavailable". The loop ends on a
text response (step-finish reason "stop"), so multi-hop tasks
CAN complete. Tool results reach the model as bare text inside
a role "tool" message (the `execute` output string -- the inner
MCP tool's text verbatim; a raising tool's error arrives as the
bare exception text, no "Error:" prefix, no "tool failure"
text). OpenCode also sends one auxiliary title-generation model
call per session before the prompt runs; the adapter answers it
directly with a plain-text title and never lets it touch the
stub. The confirmation gate in the re-probe measures the
approval surface on the default and --auto flags.

Setup findings (measured while building the probe; see the adapter
docstring for the full list): the v2 config shape is
`mcp: {servers: {...}}` (a server listed directly under `mcp`
is silently ignored); local MCP servers take `command` as an
ARRAY and use `disabled`, not `enabled`; the inotify watch
limit in this environment is exhausted, so the server logs
ENOSPC "failed to watch directory" errors on every start and
proceeds anyway; the server logs "mcp connected server=trustrun
tools=8" when the MCP server connects.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \
    evals/run_real_agents_opencode.py [--max-tasks N]
(The OpenCode install lives in trustrun-venvs/opencode-venv/
(release binary + tag source) with isolated config/state in
trustrun-venvs/opencode-venv/opencode-home. The runner runs under the
project venv python and drives the binary as a subprocess. See
real_agents/opencode_adapter.py.)

Runs trustrun.cli.run_audit over the opencode adapter on all 25 tasks,
seed 0, k=5, with the eval corpus as the data module input. Writes
one machine readable summary into reports/real_agents/opencode/summary.json
and the evidence logs (injection observations, tampering calls)
into reports/real_agents/opencode/evidence.json. Every number in those
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
agents' failures are theirs; the OpenCode rows are OpenCode's. Note the
audited code is the v2.3.0 release, NOT default-branch HEAD (HEAD
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

import real_agents.opencode_adapter as opencode_adapter  # noqa: E402
from real_agents.opencode_adapter import (  # noqa: E402
    OPENCODE_REPO,
    OPENCODE_SECURITY_CONTACT,
    OPENCODE_SECURITY_MD,
    OPENCODE_TAG,
    OPENCODE_TAG_COMMIT,
    OPENCODE_TAG_DATE,
    OPENCODE_VERSION,
    RUN_LOGS,
    opencode_agent,
    shutdown,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "opencode")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
TOOLCALLS_LOG = os.path.normpath(os.path.join(
    os.path.dirname(HERE), "..", "trustrun-venvs",
    "opencode-venv", "opencode-toolcalls.jsonl"))
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
    """Driver-side tool-call counts from opencode-toolcalls.jsonl
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
                opencode_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the opencode (non-)effect lives
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
                "agent": "opencode",
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
            print("opencode x %s -> %s (contract %s, stress %s, "
                  "consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "opencode",
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
            print("opencode x %s -> CRASH (%s: %s)"
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
        "product": "OpenCode (sst/opencode, v2.3.0, the real OpenCode headless agent loop)",
        "component": "The real OpenCode 2.3.0 binary (`opencode run --standalone --format json`, the shipped headless mode) running the real OpenCode agent loop (the session runner over the openai-compatible provider runtime) against the Trustrun tool set (search_docs, calculator, plus the monitor/grader/clarification tools run_audit adds) as real MCP tools (server \"trustrun\", stdio, registered in the project opencode.json; OpenCode 2.3.0 offers MCP tools to the model only inside Code Mode, through the single `execute` tool -- the stub's harness tool calls become `execute` calls whose code awaits `tools.trustrun[\"<name>\"](args)`). The stub model is served as a local OpenAI-compatible server the binary points at through the project config (provider \"stub\", package @opencode/ai/providers/openai-compatible, baseURL http://127.0.0.1:18080/v1). No key, no network. The loop ends on a text response, so multi-hop tasks can complete. Tool results reach the model as bare text inside a role \"tool\" message (the `execute` output string -- the inner MCP tool's text verbatim; a raising tool's error arrives as the bare exception text).",
        "version": "OpenCode %s (tag %s; release artifact opencode-linux-x64.tar.gz downloaded from the v2.3.0 release; tag source cloned with `git clone --depth 1 --branch v2.3.0`, HEAD verified equal to the tag commit; binary reports version %s)"
        % (OPENCODE_VERSION, OPENCODE_TAG, "2.3.0"),
        "repo": OPENCODE_REPO,
        "repo_resolved": "https://github.com/sst/opencode, tag %s (commit %s, %s). Default-branch HEAD is NEWER than the release, so the audited code is the v2.3.0 release, NOT HEAD. The audited code IS the release: the opencode-src clone's HEAD equals the tag commit and the working tree is clean, and the audited binary is the published v2.3.0 release artifact. %s. The audited object is the OpenCode headless agent loop -- see the adapter docstring for the wiring facts." % (
            OPENCODE_TAG, OPENCODE_TAG_COMMIT,
            OPENCODE_TAG_DATE,
            OPENCODE_SECURITY_MD),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic ported VERBATIM into n8n-stub.py, translated at the wire only by real_agents/opencode/opencode_stub.py; see real_agents/opencode_adapter.py and trustrun-venvs/opencode-requests.jsonl)",
        "confirmation_gate": "SEE reprobe.log (evals/reports/real_agents/opencode/reprobe.log) for the measured gate text; this field is filled in by the finalize step after the re-probe runs. Headline, measured: (1) A registered MCP tool the model picks executes with no approval step under the default `opencode run` (no --auto). (2) --auto approves permission asks once; without it the non-interactive runner auto-rejects asks -- but no ask is raised for the MCP tool call in the measured run. (3) A raising tool's error text reaches the model as the bare exception text through the `execute` output, and the run ends flagged only when the harness's standard injected-failure text fires the stub's error branch.",
        "tool_calls": dict(driver_counts),
        "tool_calls_in_process": dict(opencode_adapter.TOOL_CALLS),
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
    print("tool_calls_in_process:", dict(opencode_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    shutdown()
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, TOOLCALLS_OFFSET):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
