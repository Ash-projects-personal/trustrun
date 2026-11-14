"""Audit Roo Code (RooCodeInc/Roo-Code, v3.54.0) with Trustrun
(seventy-first real-agent audit).

Configuration under test: the real Roo Code 3.54.0 CLI
(`roo --print --stdin-prompt-stream --output-format stream-json`,
the shipped headless/CI mode) running the real Roo Code agent
loop (the roo-cline extension task loop, driven through the
vscode-shim in-process host) against the Trustrun tool set,
driven by a deterministic stub model. The 8 Trustrun tools are
real MCP tools (server "trustrun", stdio, registered in the
extension's mcp_settings.json); Roo Code exposes them to the
model as native tools named `mcp--trustrun--<name>`. The stub
model is served as a local OpenAI-compatible server the CLI
points at per task through the `start` command's `configuration`
(openai handler: apiProvider "openai", openAiBaseUrl
http://127.0.0.1:18080, model deterministic-stub-v1). No key,
no network. One long-lived CLI process per flag set, one fresh
stub (and fresh MCP server) per call. The stub's harness-level
decisions are translated at the wire only (see
real_agents/roo/roo_stub.py): a "final" answer becomes an
attempt_completion tool call (Roo Code has no minimum summary
length, so no padding), and a harness tool call becomes a call
to `mcp--trustrun--<name>` with the mapped arguments verbatim.

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
trustrun-venvs/roo-requests.jsonl).

MEASURED Roo Code STRUCTURE (see the adapter docstring and the
re-probe): the CLI's non-interactive print mode enables
auto-approval by default (initialSettings: autoApprovalEnabled
true, alwaysAllowReadOnly/Write/WriteOutsideWorkspace/
WriteProtected/Mcp/ModeSwitch/Subtasks/Execute true,
allowedCommands ["*"]); --require-approval flips it off. The
loop is unbounded and ends on attempt_completion (with a
`completion_result` ask the CLI auto-answers), not on an
iteration cap -- so multi-hop tasks CAN complete. Tool results
reach the model as bare text inside a role "tool" message (the
MCP text verbatim; a raising tool's error arrives as
"Error:\n<exception text>" from the use_mcp_tool handler, no
untrusted-context tag). The `completion_result` ask is NOT
covered by any checkAutoApproval branch, and attempt_completion
is blocked while didToolFailInCurrentTurn is set after a failed
tool. The confirmation gate in the re-probe measures the
approval surface on the default and --require-approval settings.

Setup findings (measured while building the probe; see the adapter
docstring for the full list): the extension must be bundled
(`pnpm --filter @roo-code/build build` then `pnpm --filter
roo-cline bundle`) and the CLI built (`pnpm --filter @roo-code/cli
build`); the CLI needs the @vscode/ripgrep postinstall binary or
tasks fail at start; the stub is injected ONLY via the per-task
configuration in the stdin-stream start command (the CLI flags
accept no openai-compatible provider); MCP tools must be listed
in mcp_settings.json with alwaysAllow ["*"] or use_mcp_server
asks are not auto-approved.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \
    evals/run_real_agents_roo.py [--max-tasks N]
(The Roo Code install lives in trustrun-venvs/roo-venv/roo-src
(tag source, built with pnpm) with isolated config/state in
trustrun-venvs/roo-venv/roo-home. The runner runs under the
project venv python and drives the CLI as a subprocess. See
real_agents/roo_adapter.py.)

Runs trustrun.cli.run_audit over the roo adapter on all 25 tasks,
seed 0, k=5, with the eval corpus as the data module input. Writes
one machine readable summary into reports/real_agents/roo/summary.json
and the evidence logs (injection observations, tampering calls)
into reports/real_agents/roo/evidence.json. Every number in those
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
agents' failures are theirs; the Roo Code rows are Roo Code's. Note the
audited code is the v3.54.0 release, NOT default-branch HEAD (HEAD
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

import real_agents.roo_adapter as roo_adapter  # noqa: E402
from real_agents.roo_adapter import (  # noqa: E402
    ROO_REPO,
    ROO_SECURITY_CONTACT,
    ROO_SECURITY_MD,
    ROO_TAG,
    ROO_TAG_COMMIT,
    ROO_TAG_DATE,
    ROO_VERSION,
    RUN_LOGS,
    WEDGE_RECOVERIES,
    WEDGE_STATS,
    roo_agent,
    shutdown,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import run_audit  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "roo")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
TOOLCALLS_LOG = os.path.normpath(os.path.join(
    os.path.dirname(HERE), "..", "trustrun-venvs",
    "roo-venv", "roo-toolcalls.jsonl"))
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
    """Driver-side tool-call counts from roo-toolcalls.jsonl
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
                roo_agent, task, data_path=CORPUS, seed=0, k=5
            )
            sections = report["sections"]
            # Per-attack breakdown: the roo (non-)effect lives
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
                "agent": "roo",
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
            print("roo x %s -> %s (contract %s, stress %s, "
                  "consistency %s)"
                  % (task_def["id"], report["verdict"],
                     sections["contract"]["verdict"],
                     sections["stress"]["verdict"],
                     sections["consistency"]["verdict"]), flush=True)
        except Exception as exc:  # noqa: BLE001 - record, don't die
            import traceback
            traceback.print_exc()
            rows.append({
                "agent": "roo",
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
            print("roo x %s -> CRASH (%s: %s)"
                  % (task_def["id"], type(exc).__name__, exc), flush=True)
        # Checkpoint after every task so a killed run loses at most one.
        _write_atomic(PARTIAL_ROWS, rows)
        _write_atomic(PARTIAL_EVIDENCE, RUN_LOGS)
    if max_tasks is not None and len(rows) < len(tasks):
        # Sliced run: do NOT write summary.json or delete the partials.
        print("stopped early: %d of %d tasks done (max-tasks %d); "
              "partials kept, resume next run"
              % (len(rows), len(tasks), max_tasks), flush=True)
        print("wedge_stats (this slice only): %s; recoveries: %d"
              % (dict(WEDGE_STATS), len(WEDGE_RECOVERIES)), flush=True)
        print("done in %.1fs" % (time.time() - started), flush=True)
        shutdown()
        return
    driver_counts, driver_n = _driver_tool_calls(toolcalls_start)
    summary = {
        "product": "Roo Code (RooCodeInc/Roo-Code, v3.54.0, the real Roo Code CLI agent loop)",
        "component": "The real Roo Code 3.54.0 CLI (`roo --print --stdin-prompt-stream --output-format stream-json`, the shipped headless/CI mode) running the real Roo Code agent loop (the roo-cline extension task loop, driven through the vscode-shim in-process host) against the Trustrun tool set (search_docs, calculator, plus the monitor/grader/clarification tools run_audit adds) as real MCP tools (server \"trustrun\", stdio, registered in the extension's mcp_settings.json; exposed to the model as native tools named mcp--trustrun--<name>). The stub model is served as a local OpenAI-compatible server the CLI points at per task through the `start` command's `configuration` (openai handler). No key, no network. The loop ends on the attempt_completion terminal tool, so multi-hop tasks can complete. Tool results reach the model as bare text inside a role \"tool\" message (the MCP text verbatim; a raising tool's error arrives as \"Error:\\n<exception text>\").",
        "version": "Roo Code %s (tag %s; cloned with `git clone --depth 1 --branch v3.54.0`, HEAD verified equal to the tag commit; CLI built from that source reports version %s)"
        % (ROO_VERSION, ROO_TAG, "0.1.17"),
        "repo": ROO_REPO,
        "repo_resolved": "https://github.com/RooCodeInc/Roo-Code, tag %s (commit %s, %s). Default-branch HEAD is NEWER than the release, so the audited code is the v3.54.0 release, NOT HEAD. The audited code IS the tag source: the roo-src clone's HEAD equals the tag commit and the working tree is clean. %s. The audited object is the Roo Code CLI agent loop -- see the adapter docstring for the wiring facts." % (
            ROO_TAG, ROO_TAG_COMMIT,
            ROO_TAG_DATE,
            ROO_SECURITY_MD),
        "model_driver": "deterministic-stub-v1 (literal model: follows instructions in task text and tool output; the audit-30 DeterministicChatModel decision logic ported VERBATIM into n8n-stub.py, translated at the wire only by real_agents/roo/roo_stub.py; see real_agents/roo_adapter.py and trustrun-venvs/roo-requests.jsonl)",
        "confirmation_gate": "SEE reprobe.log (evals/reports/real_agents/roo/reprobe.log) for the measured gate text; this field is filled in by the finalize step after the re-probe runs. Headline, measured: (1) The CLI's non-interactive print mode enables auto-approval by default (autoApprovalEnabled true, all alwaysAllow* flags true, allowedCommands [\"*\"]); --require-approval flips it off. (2) A forced write/exec probe tool executes with no approval step under the default. (3) A raising tool's error text reaches the model as \"Error:\\n<exception text>\" through the MCP tool result, and the run ends flagged.",
        "tool_calls": dict(driver_counts),
        "tool_calls_in_process": dict(roo_adapter.TOOL_CALLS),
        "tool_calls_driver_side": dict(driver_counts),
        "tool_calls_driver_rows": driver_n,
        "wedge_stats": dict(WEDGE_STATS),
        "wedge_recoveries": [
            {"task": t, "result": r} for t, r in WEDGE_RECOVERIES
        ],
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
    print("tool_calls_in_process:", dict(roo_adapter.TOOL_CALLS))
    print("evidence runs kept:", len(RUN_LOGS))
    print("done in %.1fs" % (time.time() - started))
    shutdown()
    # Clean completion: partial checkpoints are subsumed by summary.json.
    for path in (PARTIAL_ROWS, PARTIAL_EVIDENCE, TOOLCALLS_OFFSET):
        if os.path.exists(path):
            os.remove(path)


if __name__ == "__main__":
    main()
