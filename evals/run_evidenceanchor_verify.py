"""Focused verification for TRUSTRUN-EvidenceAnchor.

Runs the three capital tasks (t1_factual, t8_imperative, t18_tokyo)
over all twelve clean-room agents, same protocol as round 19 and
the CheatCoverage verify battery (trustrun.cli.run_audit, k=5,
seed=17, data_path=corpus.jsonl), after the evidence anchor landed
in run_audit/format_report.

Writes one formatted report per agent x task pair into
reports/evidenceanchor-verify/<agent>__<task>.txt and a machine
readable summary into reports/evidenceanchor-verify/summary.json.
Expected yield: 36 audits, 756 check-level judgments (21 per audit
at the 13-attack battery).

Then, for every report re-read from disk, verifies the [evidence]
chain with trustrun.evidence.verify_report_text, and runs four
tamper checks on the first report (flip a contract claim verdict,
flip a stress survived value, delete one entry line, rewrite the
head line), recording the bad_index each one is caught at. All
four must be caught or the script exits non-zero.

This script was derived from run_cheatcoverage_verify.py. Its
REPORTS constant was verified to point at evidenceanchor-verify/
before the run, so it cannot overwrite any round directory.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from agents import plan_execute_agent, rag_agent, react_agent  # noqa: E402
from agents_round2 import (  # noqa: E402
    guardrail_rag_agent,
    hardened_agent,
    reflection_agent,
)
from agents_round3 import (  # noqa: E402
    abstaining_agent,
    cautious_agent,
    clarification_agent,
    literal_agent,
    retry_agent,
    verifying_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.cli import format_report, run_audit  # noqa: E402
from trustrun.evidence import verify_report_text  # noqa: E402

AGENTS = {
    "react": react_agent,
    "rag": rag_agent,
    "plan_execute": plan_execute_agent,
    "hardened": hardened_agent,
    "reflection": reflection_agent,
    "guardrail_rag": guardrail_rag_agent,
    "cautious": cautious_agent,
    "clarification": clarification_agent,
    "verifying": verifying_agent,
    "literal": literal_agent,
    "abstaining": abstaining_agent,
    "retry": retry_agent,
}

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

CORPUS = os.path.join(HERE, "corpus.jsonl")
REPORTS = os.path.join(HERE, "reports", "evidenceanchor-verify")

SEED = 17  # same seed as round 19, so the numbers are comparable
TASK_IDS = ("t1_factual", "t8_imperative", "t18_tokyo")


def _tamper_checks(text):
    """Four edits to one report; each must be caught with a named
    bad_index (or None for the head-line edit). Returns a list of
    {"tamper", "valid", "bad_index"} dicts."""
    lines = text.splitlines()
    checks = []

    # 1. Flip a contract claim verdict inside its chain entry.
    edited = []
    hit = None
    for line in lines:
        if hit is None and line.startswith("  #") \
                and '"section":"contract"' in line \
                and '"verdict":"pass"' in line:
            line = line.replace('"verdict":"pass"', '"verdict":"fail"')
            hit = int(line.split(" ")[2][1:])
        edited.append(line)
    result = verify_report_text("\n".join(edited))
    checks.append({"tamper": "flip_claim_verdict", "valid": result["valid"],
                   "bad_index": result["bad_index"],
                   "hit_index": hit})

    # 2. Flip a stress survived value inside its chain entry.
    edited = []
    hit = None
    for line in lines:
        if hit is None and line.startswith("  #") \
                and '"section":"stress"' in line \
                and '"attack"' in line \
                and '"survived":true' in line:
            line = line.replace('"survived":true', '"survived":false')
            hit = int(line.split(" ")[2][1:])
        edited.append(line)
    result = verify_report_text("\n".join(edited))
    checks.append({"tamper": "flip_stress_survived", "valid": result["valid"],
                   "bad_index": result["bad_index"],
                   "hit_index": hit})

    # 3. Delete one chain entry line.
    victim = next(i for i, line in enumerate(lines)
                  if line.startswith("  #5 "))
    edited = [line for i, line in enumerate(lines) if i != victim]
    result = verify_report_text("\n".join(edited))
    checks.append({"tamper": "delete_entry_5", "valid": result["valid"],
                   "bad_index": result["bad_index"],
                   "hit_index": 5})

    # 4. Rewrite the head line.
    edited = []
    for line in lines:
        if line.startswith("[evidence] sha256 head "):
            head = line.split(" ")[3]
            line = line.replace(head, "0" * 64)
        edited.append(line)
    result = verify_report_text("\n".join(edited))
    checks.append({"tamper": "rewrite_head_line", "valid": result["valid"],
                   "bad_index": result["bad_index"],
                   "hit_index": None})
    return checks


def main():
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as handle:
        tasks = [t for t in json.load(handle) if t["id"] in TASK_IDS]
    assert len(tasks) == 3, "expected 3 capital tasks, got %d" % len(tasks)
    assert len(AGENTS) == 12, "expected 12 agents, got %d" % len(AGENTS)
    assert REPORTS.endswith("evidenceanchor-verify"), REPORTS
    summary = []
    started = time.time()
    first_text = None
    for agent_name, agent in AGENTS.items():
        for task_def in tasks:
            task_id = task_def["id"]
            tools = {
                name: TOOL_BUILDERS[name]
                for name in task_def["tools_order"]
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
            report = run_audit(
                agent, task, data_path=CORPUS, seed=SEED, k=5
            )
            text = format_report(report)
            if first_text is None:
                first_text = text
            path = os.path.join(
                REPORTS, "%s__%s.txt" % (agent_name, task_id)
            )
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text + "\n")
            anchor = report["evidence"]
            sections = report["sections"]
            summary.append(
                {
                    "agent": agent_name,
                    "task": task_id,
                    "verdict": report["verdict"],
                    "contract": sections["contract"]["verdict"],
                    "stress": sections["stress"]["verdict"],
                    "consistency": sections["consistency"]["verdict"],
                    "data": sections["data"]["verdict"],
                    "anchor_entries": len(anchor["entries"]),
                    "anchor_head": anchor["head"],
                    "anchor_valid": verify_report_text(text)["valid"],
                }
            )
            print(
                "%s x %s -> %s (anchor %d entries, valid %s)"
                % (
                    agent_name,
                    task_id,
                    report["verdict"],
                    len(anchor["entries"]),
                    summary[-1]["anchor_valid"],
                )
            )
    # Re-read every report from disk and verify its chain.
    disk_valid = 0
    for row in summary:
        path = os.path.join(
            REPORTS, "%s__%s.txt" % (row["agent"], row["task"])
        )
        with open(path, encoding="utf-8") as handle:
            disk_valid += verify_report_text(handle.read())["valid"]
    tamper = _tamper_checks(first_text)
    for check in tamper:
        print(
            "tamper %-22s valid=%s bad_index=%s (hit %s)"
            % (check["tamper"], check["valid"], check["bad_index"],
               check["hit_index"])
        )
    payload = {
        "audits": len(summary),
        "checks_per_audit": 21,
        "check_level_judgments": len(summary) * 21,
        "seconds": round(time.time() - started, 1),
        "anchor_valid_in_memory": sum(
            row["anchor_valid"] for row in summary),
        "anchor_valid_from_disk": disk_valid,
        "tamper_checks": tamper,
        "rows": summary,
    }
    with open(os.path.join(REPORTS, "summary.json"), "w",
              encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1)
    print(
        "36 audits, anchor valid %d/36 in memory, %d/36 from disk, "
        "tamper caught %d/4 in %.1fs"
        % (payload["anchor_valid_in_memory"], disk_valid,
           sum(not c["valid"] for c in tamper), payload["seconds"])
    )
    if disk_valid != len(summary):
        raise SystemExit("anchor failed to verify from disk")
    if any(c["valid"] for c in tamper):
        raise SystemExit("a tamper check was not caught")
    for check in tamper:
        if check["hit_index"] is not None \
                and check["bad_index"] != check["hit_index"]:
            raise SystemExit(
                "tamper %s caught at %s, want %s"
                % (check["tamper"], check["bad_index"],
                   check["hit_index"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
