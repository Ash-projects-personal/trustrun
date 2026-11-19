"""Audit Kilo Code (Kilo-Org/kilocode, v7.8.30) with Trustrun
(seventy-ninth real-agent audit).

Configuration under test: the real Kilo Code 7.8.30 CLI
(`kilo run --format json`, the shipped headless mode) running
the real Kilo agent loop (the OpenCode-descended session
runner over the openai-compatible provider runtime) against
the Trustrun tool set, driven by a deterministic stub model.
The 8 Trustrun tools are real MCP tools (server "trustrun",
stdio, registered in the project kilo.json); Kilo 7.8.30
offers MCP tools to the model DIRECTLY as individual model
tools named `trustrun_<name>` -- there is no `execute` Code
Mode gateway in the offered inventory (a call to `execute`
is rejected in-band as "Model tried to call unavailable
tool 'execute'"). The stub's harness tool calls are
translated at the wire only into direct `trustrun_<name>`
calls with the n8n argument mapping verbatim (see
real_agents/kilo/kilo_stub.py); a harness "final"
answer passes through as plain text, which ends the loop. The
stub model is served as a local OpenAI-compatible server the
binary points at through the project config (provider "stub",
npm @ai-sdk/openai-compatible, baseURL
http://127.0.0.1:18080/v1). No key, no network. One fresh
`kilo run` process (and one fresh session) per call.

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
trustrun-venvs/kilo-requests.jsonl).

MEASURED Kilo STRUCTURE (see the adapter docstring and the
re-probe): the run command takes the task as a positional
argument; the user message wraps the task as a double-quoted
first text part plus an <environment_details> block, which the
adapter unwraps before the stub decides (probe 1 showed the
unwrapped "Message time" date being read as an arithmetic
expression). The loop ends on a text response, so multi-hop
tasks CAN complete (probe: t4 multistep returned 2024 via
search then calculator). Tool results reach the model as bare
text inside a role "tool" message (the inner MCP tool's text
verbatim; a raising tool's error arrives as the bare exception
text, no "Error:" prefix, no "tool failure" text). Kilo sends
one auxiliary title-generation model call per session AFTER
the task's final answer (system prompt "You are a title
generator..."); the adapter answers it directly with a
plain-text title and never lets it touch the stub. The
confirmation gate in the re-probe measures the approval
surface on the default and --auto flags.

Setup findings (measured while building the probe; see the adapter
docstring for the full list): the project config file is
kilo.json (kilo.jsonc / opencode.json also accepted); the
provider shape is `provider: {stub: {npm:
"@ai-sdk/openai-compatible", models: {...}, options:
{apiKey, baseURL}}}`; the MCP shape is `mcp: {trustrun:
{type: "local", command: [...], environment: {...},
enabled: true}}` (a flat map, NOT `mcp.servers`); the
installed npm package is a launcher that spawns the
platform binary @kilocode/cli-linux-x64.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \
    evals/run_real_agents_kilo.py [--max-tasks N]
(The Kilo install lives in trustrun-venvs/kilo-venv/
(npm @kilocode/cli@7.8.30 + tag source) with isolated
config/state in trustrun-venvs/kilo-venv/kilo-home. The
runner runs under the project venv python and drives the
binary as a subprocess. See real_agents/kilo_adapter.py.)

Runs trustrun.cli.run_audit over the kilo adapter on all 25 tasks,
seed 0, k=5, with the eval corpus as the data module input. Writes
one machine readable summary into reports/real_agents/kilo/summary.json
and the evidence logs (injection observations, tampering calls)
into reports/real_agents/kilo/evidence.json. Every number in those
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
agents' failures are theirs; the Kilo rows are Kilo's. Note the
audited code is the v7.8.30 release, NOT default-branch HEAD (HEAD
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

import real_agents.kilo_adapter as kilo_adapter  # noqa: E402
from real_agents.kilo_adapter import (  # noqa: E402
    KILO_REPO,
    KILO_SECURITY_CONTACT,
    KILO_SECURITY_MD,
    KILO_TAG,
    KILO_TAG_COMMIT,
    KILO_TAG_DATE,
    KILO_VERSION,
    RUN_LOGS,
    kilo_agent,
    shutdown,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "kilo")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
TOOLCALLS_LOG = os.path.normpath(os.path.join(
    os.path.dirname(HERE), "trustrun-venvs",
    "kilo-venv", "kilo-toolcalls.jsonl"))
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
    """Driver-side tool-call counts from kilo-toolcalls.jsonl
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
                kilo_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the kilo (non-)effect lives
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
                "agent": "kilo",
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
            print("kilo x %s -> %s (contract %s, stress %s, "
                  "consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "kilo",
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
            print("kilo x %s -> CRASH (%s: %s)"
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
        "product": "Kilo Code (Kilo-Org/kilocode, v7.8.30, the real Kilo CLI headless agent loop)",
        "component": "The real Kilo Code 7.8.30 CLI (`kilo run --format json`, the shipped headless mode; npm @kilocode/cli@7.8.30 launcher spawning the @kilocode/cli-linux-x64 platform binary) running the real Kilo agent loop (the OpenCode-descended session runner over the openai-compatible provider runtime) against the Trustrun tool set (search_docs, calculator, plus the monitor/grader/clarification tools run_audit adds) as real MCP tools (server \"trustrun\", stdio, registered in the project kilo.json; Kilo 7.8.30 offers MCP tools to the model DIRECTLY as individual model tools named `trustrun_<name>` -- no `execute` Code Mode gateway). The stub model is served as a local OpenAI-compatible server the binary points at through the project config (provider \"stub\", npm @ai-sdk/openai-compatible, baseURL http://127.0.0.1:18080/v1). No key, no network. The loop ends on a text response, so multi-hop tasks can complete. Tool results reach the model as bare text inside a role \"tool\" message (the inner MCP tool's text verbatim; a raising tool's error arrives as the bare exception text).",
        "version": "Kilo Code %s (tag %s; npm @kilocode/cli@7.8.30, dist-tag rc, shasum 0f11d01d5d13830f7cd6698b9eeee2bed7adef02; tag source cloned with `git clone --depth 1 --branch v7.8.30`, HEAD verified equal to the tag commit; binary reports version %s)"
        % (KILO_VERSION, KILO_TAG, "7.8.30"),
        "repo": KILO_REPO,
        "repo_resolved": "https://github.com/Kilo-Org/kilocode, tag %s (commit %s, %s). Default-branch HEAD is NEWER than the release, so the audited code is the v7.8.30 release, NOT HEAD. The audited code IS the release: the kilo-src clone's HEAD equals the tag commit and the working tree is clean, and the audited binary is the published v7.8.30 npm release artifact (npm latest is 7.8.27; 7.8.30 is the rc dist-tag). %s. The audited object is the Kilo CLI headless agent loop -- see the adapter docstring for the wiring facts." % (
            KILO_TAG, KILO_TAG_COMMIT,
            KILO_TAG_DATE,
            KILO_SECURITY_MD),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic ported VERBATIM into n8n-stub.py, translated at the wire only by real_agents/kilo/kilo_stub.py; see real_agents/kilo_adapter.py and trustrun-venvs/kilo-requests.jsonl)",
        "confirmation_gate": "SEE reprobe.log (evals/reports/real_agents/kilo/reprobe.log) for the measured gate text; this field is filled in by the finalize step after the re-probe runs. Headline, measured: (1) A registered MCP tool the model picks executes with no approval step under the default `kilo run` (no --auto). (2) --auto approves permission asks once; without it the non-interactive runner auto-rejects asks -- but no ask is raised for the MCP tool call in the measured run. (3) A raising tool's error text reaches the model as the bare exception text through the `execute` output, and the run ends flagged only when the harness's standard injected-failure text fires the stub's error branch.",
        "tool_calls": dict(driver_counts),
        "tool_calls_in_process": dict(kilo_adapter.TOOL_CALLS),
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
    print("tool_calls_in_process:", dict(kilo_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    shutdown()
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, TOOLCALLS_OFFSET):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
