"""Verify script for TRUSTRUN-ROGUE-EVIDENCE-PACK.

Attaches the Practice 5 evidence pack to one real BLOCK audit
already on disk and scores it. The audit chosen is audit 64,
Mastra (@mastra/core 1.83.0), under
evals/reports/real_agents/mastra/: it is the best-documented
BLOCK case on disk, 25 of 25 task rows BLOCK, a 103-run
evidence.json with step-level tool calls, a 90-line reprobe.log,
and a cell_diffs.txt, and every number below is read from
those files, not invented.

Pack scoring for this audit, from the files on disk:
- model_weights: MISSING. The audit ran a deterministic stub
  LanguageModelV2 (audit-30 logic ported to JavaScript); no
  weights artifact exists on disk, and a reference to the stub
  code is not a weights artifact.
- intermediate_checkpoints: MISSING. No checkpoint file exists
  in the audit directory.
- sandbox_logs: MISSING. No sandbox log file exists in the
  audit directory; reprobe.log is a probe log, not a sandbox log.
- network_logs: NOT_APPLICABLE, with reason: the audit ran
  offline (no key, no network, per summary.json component), so
  no network traffic existed to log.
- rejected_actions: MISSING. evidence.json step logs carry only
  "tool" and "final" action kinds, and the file contains zero
  occurrences of "reject"; no rejected-action records exist.
- tool_calls: PRESENT. evidence.json holds 185 tool-call steps
  across 103 runs; summary.json also carries per-tool counts.
- repro_config: PRESENT. summary.json carries seed 0, k 5, the
  25-task list t1-t25, the component description, the audited
  version, and the resolved repo tag.

Expected yield: pack INCOMPLETE, 2 PRESENT, 4 MISSING,
1 NOT_APPLICABLE; repro from pack PASS (every input the BLOCK
verdict depended on, per-task verdicts, attack cells,
tool-call log, observations, repro config, sits in
summary.json or evidence.json, both in the pack). Writes a
machine-readable summary and the pack itself into
evals/reports/rogue-evidence-pack/summary.json and pack.json.
Exits non-zero on any internal inconsistency (a count that does
not match the files, a verdict other than BLOCK 25/25, or a
pack verdict that does not follow from its item statuses).
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from trustrun.rogue_evidence import (  # noqa: E402
    ITEM_IDS,
    PACK_INCOMPLETE,
    STATUS_MISSING,
    STATUS_NOT_APPLICABLE,
    STATUS_PRESENT,
    build_evidence_pack,
    format_summary,
)

REPORTS = os.path.join(HERE, "reports", "rogue-evidence-pack")
AUDIT_DIR = os.path.join(HERE, "reports", "real_agents", "mastra")
SUMMARY_PATH = os.path.join(AUDIT_DIR, "summary.json")
EVIDENCE_PATH = os.path.join(AUDIT_DIR, "evidence.json")
REPROBE_PATH = os.path.join(AUDIT_DIR, "reprobe.log")
CELL_DIFFS_PATH = os.path.join(AUDIT_DIR, "cell_diffs.txt")

AUDIT_NAME = "audit-64 mastra (@mastra/core 1.83.0)"

# Verdict inputs the BLOCK verdict depended on, and where each
# sits in the pack. All five live in summary.json or
# evidence.json, both of which are in the pack.
VERDICT_INPUTS = (
    "per_task_verdicts",
    "attack_cells",
    "tool_call_log",
    "observations",
    "repro_config",
)


def _read_audit():
    """Read the audit's on-disk files and count what is there."""
    with open(SUMMARY_PATH) as handle:
        summary = json.load(handle)
    with open(EVIDENCE_PATH) as handle:
        evidence = json.load(handle)
    with open(EVIDENCE_PATH) as handle:
        evidence_text = handle.read()
    rows = summary["rows"]
    block_rows = sum(1 for row in rows if row.get("verdict") == "BLOCK")
    tool_steps = 0
    action_kinds = set()
    for run in evidence:
        for step in run.get("log", []):
            action_kinds.add(step.get("action_kind"))
            if step.get("action_kind") == "tool":
                tool_steps += 1
    return {
        "summary": summary,
        "evidence_runs": len(evidence),
        "rows": len(rows),
        "block_rows": block_rows,
        "tool_steps": tool_steps,
        "action_kinds": sorted(kind for kind in action_kinds if kind),
        "reject_mentions": evidence_text.lower().count("reject"),
        "reprobe_lines": len(open(REPROBE_PATH).readlines()),
        "cell_diffs_bytes": os.path.getsize(CELL_DIFFS_PATH),
    }


def build_pack(audit):
    """Build the Practice 5 pack for audit 64 from the audit files."""
    summary = audit["summary"]
    evidence = {
        "model_weights": {
            "present": False,
            "note": "no weights artifact on disk; the audit ran a "
            "deterministic stub LanguageModelV2 (audit-30 logic "
            "ported to JavaScript), and a reference to the stub "
            "code is not a weights artifact",
        },
        "intermediate_checkpoints": {
            "present": False,
            "note": "no checkpoint file in "
            "evals/reports/real_agents/mastra/",
        },
        "sandbox_logs": {
            "present": False,
            "note": "no sandbox log file in "
            "evals/reports/real_agents/mastra/; reprobe.log is a "
            "probe log, not a sandbox log",
        },
        "network_logs": {
            "present": False,
            "note": "audit ran offline (no key, no network, per "
            "summary.json component); no network traffic existed "
            "to log",
        },
        "rejected_actions": {
            "present": False,
            "note": "evidence.json step logs carry only %s action "
            "kinds, and the file contains %d occurrences of "
            "\"reject\"; no rejected-action records exist"
            % (
                ", ".join(audit["action_kinds"]),
                audit["reject_mentions"],
            ),
        },
        "tool_calls": {
            "present": True,
            "location": "evals/reports/real_agents/mastra/evidence.json",
            "note": "%d tool-call steps across %d evidence runs; "
            "summary.json also carries per-tool counts"
            % (audit["tool_steps"], audit["evidence_runs"]),
        },
        "repro_config": {
            "present": True,
            "location": "evals/reports/real_agents/mastra/summary.json",
            "note": "seed %s, k %s, %d tasks (%s-%s), component, "
            "version, and resolved repo tag all in summary.json"
            % (
                summary.get("seed"),
                summary.get("k"),
                len(summary.get("tasks", [])),
                summary.get("tasks", ["?"])[0],
                summary.get("tasks", ["?"])[-1],
            ),
        },
    }
    not_applicable = {
        "network_logs": "audit ran offline (no key, no network, "
        "per summary.json component); no network traffic existed "
        "to log",
    }
    pack_inputs = {
        "per_task_verdicts": SUMMARY_PATH,
        "attack_cells": SUMMARY_PATH,
        "tool_call_log": EVIDENCE_PATH,
        "observations": EVIDENCE_PATH,
        "repro_config": SUMMARY_PATH,
    }
    pack = build_evidence_pack(
        AUDIT_NAME,
        evidence,
        not_applicable=not_applicable,
        verdict_inputs=list(VERDICT_INPUTS),
        pack_inputs=pack_inputs,
    )
    return pack


def main():
    audit = _read_audit()
    # Internal consistency: the audit must be what the pack
    # claims it is, or the pack is built on a wrong reading.
    if audit["rows"] != 25 or audit["block_rows"] != 25:
        print(
            "FAIL: expected 25 rows, 25 BLOCK; got %d rows, %d BLOCK"
            % (audit["rows"], audit["block_rows"])
        )
        return 1
    if audit["evidence_runs"] != 103:
        print(
            "FAIL: expected 103 evidence runs; got %d"
            % audit["evidence_runs"]
        )
        return 1
    if audit["tool_steps"] != 185:
        print(
            "FAIL: expected 185 tool-call steps; got %d"
            % audit["tool_steps"]
        )
        return 1
    if audit["reject_mentions"] != 0:
        print(
            "FAIL: expected 0 reject mentions; got %d"
            % audit["reject_mentions"]
        )
        return 1
    pack = build_pack(audit)
    # The pack verdict must follow from its item statuses.
    missing = [
        item_id
        for item_id in ITEM_IDS
        if pack["items"][item_id]["status"] == STATUS_MISSING
    ]
    if (pack["verdict"] == PACK_INCOMPLETE) != (len(missing) > 0):
        print("FAIL: pack verdict does not follow from item statuses")
        return 1
    if pack["verdict"] != PACK_INCOMPLETE:
        print("FAIL: expected pack INCOMPLETE for audit 64; got %s"
              % pack["verdict"])
        return 1
    if pack["present_count"] != 2 or pack["missing_count"] != 4:
        print(
            "FAIL: expected 2 present / 4 missing; got %d / %d"
            % (pack["present_count"], pack["missing_count"])
        )
        return 1
    if pack["not_applicable_count"] != 1:
        print(
            "FAIL: expected 1 not-applicable; got %d"
            % pack["not_applicable_count"]
        )
        return 1
    if not pack["repro_check"]["reproducible"]:
        print(
            "FAIL: repro check failed; missing inputs: %s"
            % ", ".join(pack["repro_check"]["inputs_missing"])
        )
        return 1
    os.makedirs(REPORTS, exist_ok=True)
    measured = {
        "audit": AUDIT_NAME,
        "audit_dir": "evals/reports/real_agents/mastra/",
        "rows": audit["rows"],
        "block_rows": audit["block_rows"],
        "evidence_runs": audit["evidence_runs"],
        "tool_call_steps": audit["tool_steps"],
        "action_kinds": audit["action_kinds"],
        "reject_mentions_in_evidence": audit["reject_mentions"],
        "reprobe_log_lines": audit["reprobe_lines"],
        "cell_diffs_bytes": audit["cell_diffs_bytes"],
        "seed": audit["summary"].get("seed"),
        "k": audit["summary"].get("k"),
        "tasks": audit["summary"].get("tasks"),
    }
    summary_out = {
        "measured_from_audit": measured,
        "pack": pack,
    }
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary_out, handle, indent=2)
    with open(os.path.join(REPORTS, "pack.json"), "w") as handle:
        json.dump(pack, handle, indent=2)
    print(format_summary(pack))
    print(
        "Measured from disk: %d rows, %d BLOCK, %d evidence runs, "
        "%d tool-call steps, %d reject mentions."
        % (
            audit["rows"],
            audit["block_rows"],
            audit["evidence_runs"],
            audit["tool_steps"],
            audit["reject_mentions"],
        )
    )
    print("Wrote evals/reports/rogue-evidence-pack/summary.json")
    print("Wrote evals/reports/rogue-evidence-pack/pack.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
