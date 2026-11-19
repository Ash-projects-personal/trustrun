"""Chunked, resumable runner for the OpenClaw audit (audit 78).

Problem: the per-task runner (run_real_agents_clawdbot.py) checkpoints
only after each task, and one task takes about 40 minutes, so a run
killed at a cron turn end loses the whole in-flight task. This runner
checkpoints finer than per-task: after every unit.

A unit is one contract section, one stress attack, the consistency
section, or the data section. State for the in-progress task lives in
task_partial.json ({task_id, sections, attacks, evidence_len}) and is
rewritten atomically after every unit, so a killed run resumes at the
next missing unit instead of restarting the task. Finished tasks live
in rows_partial.json, evidence in evidence_partial.json, exactly like
the per-task runner. --finalize writes summary.json and evidence.json
and deletes the partials once every task is done.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
    evals/run_real_agents_clawdbot_chunked.py [--max-seconds N]
        [--task ID] [--section NAME] [--finalize]
"""

import argparse
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
from trustrun.cli import (  # noqa: E402
    _accepts_tools,
    _consistency_section,
    _contract_section,
    _data_section,
    _default_attacks,
    _overall_verdict,
    _tool_channel_unmeasured,
)
from trustrun.evidence import build_anchor  # noqa: E402
from trustrun.stress import replay_attack  # noqa: E402
from trustrun.stress.atom import score_atom  # noqa: E402

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "real_agents", "clawdbot")
CORPUS = os.path.join(HERE, "corpus.jsonl")
PARTIAL_ROWS = os.path.join(OUT_DIR, "rows_partial.json")
PARTIAL_EVIDENCE = os.path.join(OUT_DIR, "evidence_partial.json")
TASK_PARTIAL = os.path.join(OUT_DIR, "task_partial.json")
TOOLCALLS_LOG = os.path.join(
    HERE, "..", "trustrun-venvs",
    "clawdbot-venv", "clawdbot-toolcalls.jsonl")
TOOLCALLS_LOG = os.path.normpath(TOOLCALLS_LOG)

SEED = 0
K = 5

# Tool channel attacks, the kinds _stress_section skips for an agent
# that takes no tools argument. Kept in one place so the chunked
# stress path and the section path cannot drift apart.
_TOOL_CHANNEL_KINDS = (
    "tool_failure",
    "tool_failure_visibility",
    "injection",
    "adaptive_injection",
    "task_tamper",
    "ci_harness_inject",
    "prompt_adware",
    "page_reader_inject",
    "monitor_tampering",
    "evaluator_tampering",
    "clarification_injection",
)

# Number of attacks in the battery. Derived from the same builder the
# section path uses, so a battery change moves both together.
N_STRESS_ATTACKS = len(_default_attacks({}, None))


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
    """Driver-side tool-call counts from clawdbot-toolcalls.jsonl.

    Copied from the per-task runner so finalize reports the same
    driver-side total there. Returns (Counter, n_rows).
    """
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


def unit_names():
    """Ordered unit names for one task: contract, one unit per stress
    attack in battery order, consistency, data."""
    names = ["contract"]
    names.extend("stress:%d" % i for i in range(N_STRESS_ATTACKS))
    names.extend(["consistency", "data"])
    return names


def parse_section(name):
    """Unit index for a --section value. Accepts contract, stress,
    stress:N, consistency, data. Raises ValueError on anything else."""
    names = unit_names()
    if name in names:
        return names.index(name)
    if name == "stress":
        return names.index("stress:0")
    raise ValueError("unknown section %r, want one of %s"
                     % (name, ", ".join(names)))


def _empty_state(task_id):
    return {
        "task_id": task_id,
        "sections": {},
        "attacks": [None] * N_STRESS_ATTACKS,
        "evidence_len": 0,
    }


def _normalize_state(state, task_id):
    """Fill a loaded state to the current shape. A state from an older
    battery length is padded with None when short and cut to the
    current battery length when long, so a battery change cannot
    leave a stale attack slot behind."""
    if not isinstance(state, dict) or state.get("task_id") != task_id:
        return _empty_state(task_id)
    sections = state.get("sections")
    if not isinstance(sections, dict):
        sections = {}
    attacks = state.get("attacks")
    if not isinstance(attacks, list):
        attacks = []
    attacks = list(attacks[:N_STRESS_ATTACKS])
    attacks.extend([None] * (N_STRESS_ATTACKS - len(attacks)))
    return {
        "task_id": task_id,
        "sections": sections,
        "attacks": attacks,
        "evidence_len": state.get("evidence_len", 0),
    }


def _unit_done(state, unit):
    if unit.startswith("stress:"):
        index = int(unit.split(":", 1)[1])
        return state["attacks"][index] is not None
    return unit in state["sections"]


def _state_complete(state):
    return (
        "contract" in state["sections"]
        and "consistency" in state["sections"]
        and "data" in state["sections"]
        and all(a is not None for a in state["attacks"])
    )


def run_stress_attack(agent, tools_capable, tools, text, expect, seed,
                      suggestion, index):
    """Run one stress attack, mirroring _stress_section exactly for
    that attack: same battery order, same perturbation seed override,
    same tool-channel skip for agents without tools."""
    attacks = _default_attacks(tools, suggestion)
    attack = attacks[index]
    if attack["kind"] == "perturbation":
        attack = dict(attack, seed=seed)
    if not tools_capable and attack["kind"] in _TOOL_CHANNEL_KINDS:
        return _tool_channel_unmeasured(attack)
    if tools_capable:
        stress_agent = agent
    else:
        def stress_agent(task_text, task_tools):
            return agent(task_text)
    stress_task = {"text": text, "tools": tools, "expect": expect}
    return replay_attack(stress_agent, stress_task, attack)


def stress_section_from_attacks(results):
    """Assemble the stress section from attack results, with the same
    verdict rule _stress_section uses: any failed survival blocks,
    any unverified survival reviews, else ready."""
    survived = [r["survived"] for r in results]
    if any(s is False for s in survived):
        verdict = "BLOCK"
    elif any(s == "unverified" for s in survived):
        verdict = "REVIEW"
    else:
        verdict = "READY"
    return {
        "verdict": verdict,
        "attacks": results,
        "atom": score_atom(results),
        "note": "",
    }


def compact_attacks(results):
    """Compact full attack results to the per-row shape the per-task
    runner writes: kind, vector, survived, detected, completed, plus
    visibility_class when present."""
    attacks = []
    for a in results:
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
    return attacks


def assemble_row(agent_name, task_id, sections, attacks):
    """Build the summary row for a finished task, with the same keys,
    order, and verdict rule as the per-task runner. Also builds the
    evidence anchor over the assembled report, the way run_audit
    does, and returns it alongside the row. The row itself carries
    no anchor key, so its keys match the per-task runner exactly."""
    stress = stress_section_from_attacks(attacks)
    full_sections = {
        "contract": sections["contract"],
        "stress": stress,
        "consistency": sections["consistency"],
        "data": sections["data"],
    }
    verdict = _overall_verdict(
        [s["verdict"] for s in full_sections.values()])
    report = {
        "agent": agent_name,
        "task": sections.get("_task_text", task_id),
        "k": K,
        "seed": SEED,
        "tools_capable": sections.get("_tools_capable", True),
        "sections": full_sections,
        "verdict": verdict,
    }
    anchor = build_anchor(report)
    row = {
        "agent": "clawdbot",
        "task": task_id,
        "task_id": task_id,
        "verdict": verdict,
        "contract": full_sections["contract"]["verdict"],
        "stress": stress["verdict"],
        "consistency": full_sections["consistency"]["verdict"],
        "data": full_sections["data"]["verdict"],
        "pass_rate_k": full_sections["consistency"]["pass_rate_k"],
        "attacks": compact_attacks(attacks),
    }
    return row, anchor


def crash_row(task_id, exc):
    """Crash row in the per-task runner shape: BLOCK everywhere,
    pass_rate_k 0.0, no attacks, crash field naming the exception."""
    return {
        "agent": "clawdbot",
        "task": task_id,
        "task_id": task_id,
        "verdict": "BLOCK",
        "contract": "BLOCK",
        "stress": "BLOCK",
        "consistency": "BLOCK",
        "data": "BLOCK",
        "pass_rate_k": 0.0,
        "attacks": [],
        "crash": "%s: %s" % (type(exc).__name__, exc),
    }


def _build_task(task_def, tool_builders):
    """Task dict for the section helpers, built the way the per-task
    runner builds it: tools from tools_order, plus variants, rubric,
    and misleading suggestion when the task carries them."""
    tools = {
        name: tool_builders[name] for name in task_def["tools_order"]
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
    return task, tools


def _run_unit(agent, tools_capable, tools, task, task_def, corpus,
              seed, k, unit):
    """Run one unit and return (kind, key, value): kind "section" with
    the section name, or kind "attack" with the attack index."""
    text = task["text"]
    expect = task["expect"]
    if unit == "contract":
        section = _contract_section(
            agent, tools_capable, tools, text, expect,
            task.get("contract"),
            authorization=task.get("authorization"),
            effect_kinds=task.get("effect_kinds"),
            reference_effects=task.get("reference_effects"),
            tool_trace=None,
        )
        return ("section", "contract", section)
    if unit.startswith("stress:"):
        index = int(unit.split(":", 1)[1])
        result = run_stress_attack(
            agent, tools_capable, tools, text, expect, seed,
            task.get("misleading_suggestion"), index)
        return ("attack", index, result)
    if unit == "consistency":
        section = _consistency_section(
            agent, tools_capable, tools, task, k, seed)
        return ("section", "consistency", section)
    if unit == "data":
        return ("section", "data", _data_section(corpus))
    raise ValueError("unknown unit %r" % (unit,))


def build_summary(rows, tasks, run_logs):
    """Summary dict mirroring the per-task runner finalize exactly:
    same top-level keys, same product and component text, same
    version and repo strings from the adapter constants."""
    driver_counts, driver_n = _driver_tool_calls()
    return {
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
        "seed": SEED,
        "k": K,
        "audits": len(rows),
        "crashes": [r["task"] for r in rows if "crash" in r],
        "rows": rows,
    }


def run_chunked(agent=None, tasks=None, out_dir=None, corpus=None,
                max_seconds=300, task_id=None, section=None,
                do_finalize=False, tool_builders=None, run_logs=None,
                seed=SEED, k=K):
    """Run chunked units within a time budget. Returns 0 on a clean
    stop, including a spent budget, an unfinished task, or a recorded
    crash. Returns 2 when the requested task or section is unknown.

    agent defaults to the real clawdbot agent; tasks defaults to
    evals/tasks.json; out_dir defaults to the clawdbot report dir.
    run_logs defaults to the adapter RUN_LOGS list and is synced
    from evidence_partial.json at the start, so disk stays the
    source of truth across relaunches.
    """
    started = time.monotonic()
    if agent is None:
        agent = clawdbot_agent
    if out_dir is None:
        out_dir = OUT_DIR
    if corpus is None:
        corpus = CORPUS
    if tool_builders is None:
        tool_builders = TOOL_BUILDERS
    if run_logs is None:
        run_logs = RUN_LOGS
    os.makedirs(out_dir, exist_ok=True)
    partial_rows = os.path.join(out_dir, "rows_partial.json")
    partial_evidence = os.path.join(out_dir, "evidence_partial.json")
    task_partial = os.path.join(out_dir, "task_partial.json")
    if tasks is None:
        with open(os.path.join(HERE, "tasks.json"),
                  encoding="utf-8") as handle:
            tasks = json.load(handle)
    rows = _load_json(partial_rows, [])
    # Disk is the source of truth for evidence: replace the in-memory
    # list contents so a relaunch in the same process cannot double
    # count entries it already loaded.
    run_logs[:] = _load_json(partial_evidence, [])
    agent_name = getattr(agent, "__name__", None) or type(agent).__name__
    tools_capable = _accepts_tools(agent)

    if do_finalize:
        done = {row["task"] for row in rows}
        if all(t["id"] in done for t in tasks):
            summary = build_summary(rows, tasks, run_logs)
            _write_atomic(os.path.join(out_dir, "summary.json"), summary)
            _write_atomic(os.path.join(out_dir, "evidence.json"),
                          list(run_logs))
            print("verdicts:", dict(Counter(r["verdict"] for r in rows)),
                  flush=True)
            print("evidence runs kept:", len(run_logs), flush=True)
            for path in (partial_rows, partial_evidence, task_partial):
                if os.path.exists(path):
                    os.remove(path)
            print("finalized: %d rows, summary.json written" % len(rows),
                  flush=True)
        else:
            print("finalize: %d of %d tasks done; partials kept"
                  % (len(done), len(tasks)), flush=True)
        try:
            shutdown()
        except Exception:  # noqa: BLE001 - shutdown is best effort
            pass
        return 0

    start_index = 0
    if section is not None:
        try:
            start_index = parse_section(section)
        except ValueError as exc:
            print("error: %s" % exc, flush=True)
            return 2
    done = {row["task"] for row in rows}
    pending = [t for t in tasks if t["id"] not in done]
    if task_id is not None:
        wanted = [t for t in tasks if t["id"] == task_id]
        if not wanted:
            print("error: unknown task %r" % (task_id,), flush=True)
            return 2
        if task_id in done:
            print("clawdbot-chunked x %s already done" % task_id,
                  flush=True)
            return 0
        work = wanted
    else:
        if not pending:
            print("all tasks done; run --finalize to write summary.json",
                  flush=True)
            return 0
        # Resume the in-progress task first when one is checkpointed.
        state = _load_json(task_partial, None)
        if (isinstance(state, dict)
                and state.get("task_id") in {t["id"] for t in pending}):
            first = state["task_id"]
            pending.sort(key=lambda t: 0 if t["id"] == first else 1)
        work = pending
    names = unit_names()
    first_task = True
    for task_def in work:
        tid = task_def["id"]
        task, tools = _build_task(task_def, tool_builders)
        state = _normalize_state(_load_json(task_partial, None), tid)
        begin = start_index if first_task else 0
        first_task = False
        crashed = False
        for index in range(begin, len(names)):
            unit = names[index]
            if _unit_done(state, unit):
                continue
            if time.monotonic() - started >= max_seconds:
                print("clawdbot-chunked: budget spent (%.1fs), "
                      "stopping cleanly; state kept in task_partial.json"
                      % (time.monotonic() - started), flush=True)
                try:
                    shutdown()
                except Exception:  # noqa: BLE001 - best effort
                    pass
                return 0
            try:
                kind, key, value = _run_unit(
                    agent, tools_capable, tools, task, task_def, corpus,
                    seed, k, unit)
            except Exception as exc:  # noqa: BLE001 - record, don't die
                import traceback
                traceback.print_exc()
                rows.append(crash_row(tid, exc))
                _write_atomic(partial_rows, rows)
                _write_atomic(partial_evidence, list(run_logs))
                if os.path.exists(task_partial):
                    os.remove(task_partial)
                print("clawdbot-chunked x %s %s -> CRASH (%s: %s)"
                      % (tid, unit, type(exc).__name__, exc), flush=True)
                crashed = True
                break
            if kind == "section":
                state["sections"][key] = value
            else:
                state["attacks"][key] = value
            state["evidence_len"] = len(run_logs)
            _write_atomic(task_partial, state)
            _write_atomic(partial_evidence, list(run_logs))
            print("clawdbot-chunked x %s %s done (%.1fs elapsed)"
                  % (tid, unit, time.monotonic() - started), flush=True)
        if crashed:
            if task_id is not None:
                break
            if time.monotonic() - started >= max_seconds:
                break
            continue
        if not _state_complete(state):
            print("clawdbot-chunked x %s incomplete (%d of %d units); "
                  "state kept, resume next run"
                  % (tid, sum(1 for u in names if _unit_done(state, u)),
                     len(names)), flush=True)
            break
        sections = dict(state["sections"])
        sections["_task_text"] = task["text"]
        sections["_tools_capable"] = tools_capable
        row, anchor = assemble_row(agent_name, tid, sections,
                                   list(state["attacks"]))
        rows.append(row)
        _write_atomic(partial_rows, rows)
        _write_atomic(partial_evidence, list(run_logs))
        if os.path.exists(task_partial):
            os.remove(task_partial)
        print("clawdbot x %s -> %s (contract %s, stress %s, "
              "consistency %s, anchor %s)"
              % (tid, row["verdict"], row["contract"], row["stress"],
                 row["consistency"], anchor["head"][:16]), flush=True)
        if task_id is not None:
            break
        if time.monotonic() - started >= max_seconds:
            print("clawdbot-chunked: budget spent (%.1fs), stopping "
                  "cleanly" % (time.monotonic() - started), flush=True)
            break
    print("done in %.1fs" % (time.monotonic() - started), flush=True)
    try:
        shutdown()
    except Exception:  # noqa: BLE001 - shutdown is best effort
        pass
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Chunked, resumable runner for the OpenClaw audit.")
    parser.add_argument("--max-seconds", type=float, default=300,
                        help="stop cleanly after the current unit "
                        "once this many seconds have elapsed")
    parser.add_argument("--task", default=None,
                        help="task id to work on (default: next pending)")
    parser.add_argument("--section", default=None,
                        help="unit to start from: contract, stress:N, "
                        "consistency, data (default: next missing unit)")
    parser.add_argument("--finalize", action="store_true",
                        help="write summary.json and evidence.json "
                        "once all tasks are done, then delete partials")
    args = parser.parse_args(argv)
    return run_chunked(
        max_seconds=args.max_seconds,
        task_id=args.task,
        section=args.section,
        do_finalize=args.finalize,
    )


if __name__ == "__main__":
    sys.exit(main())
