"""Focused verification for TRUSTRUN-TriageGate.

Scores the module's 25 labeled cases: severity bands (the CVSS
boundaries), single-report decisions (the full valid pass, the
three HOLD evidence gaps, the severity band rules, the DROP
contradictions, the false pass on a patched fork, a missing CVE,
and the validation rejections), and campaign verdicts (the 10
report BLOCK fixture, PASS with full precision and recall, REVIEW
on low recall, BLOCK on false rejection, empty campaign, no valid
reports, and the one-line summary). Every case is a fixed fixture
report with a hand-computed score, scored by
trustrun.triage_gate. The campaign block checks the aggregate
numbers by hand: 10 reports, 3 passed, 3 held, 4 dropped, 7
valid, 2 true positives, precision 0.6667, recall 0.2857, false
rejection 0.2857, 40 minutes saved at 20 minutes per report,
verdict BLOCK.

Writes a machine-readable summary into
reports/triage-gate-verify/summary.json. Expected yield: 25
labeled cases, 25/25 match, campaign block matches.
Exits non-zero on any mismatch.

The cases are fixed fixture reports with hand-computed scores,
using fixture CVE identifiers (CVE-2026-10001 and friends), not
real CVEs and not CVE-Genie data.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.triage_gate import (  # noqa: E402
    DECISION_DROP,
    DECISION_HOLD,
    DECISION_PASS,
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_REVIEW,
    format_summary,
    score_campaign,
    score_report,
    severity_band,
)

REPORTS = os.path.join(HERE, "reports", "triage-gate-verify")


def _record(cve="CVE-2026-10001", cwe="CWE-89", path="src/db.py",
            function="run_query", cvss=9.8, reproduced=True, valid=True):
    return {
        "cve_id": cve,
        "cwe_id": cwe,
        "affected_file": path,
        "affected_function": function,
        "cvss": cvss,
        "reproduced": reproduced,
        "valid": valid,
    }


TRUTH = {
    "CVE-2026-10001": _record(),
    "CVE-2026-10002": _record(
        cve="CVE-2026-10002", cwe="CWE-79", path="src/render.py",
        function="render_page", cvss=6.1,
    ),
    "CVE-2026-10003": _record(
        cve="CVE-2026-10003", cwe="CWE-22", path="src/files.py",
        function="serve_file", cvss=5.3, reproduced=False, valid=False,
    ),
    "CVE-2026-10004": _record(
        cve="CVE-2026-10004", path="src/db.py", function="run_query",
        cvss=7.5, valid=False,
    ),
}


def _report(report_id="r1", cve="CVE-2026-10001", cwe="CWE-89",
            path="src/db.py", function="run_query", has_poc=True,
            poc_reproduced=True, human_rerun=True, severity="critical"):
    return {
        "report_id": report_id,
        "cve_id": cve,
        "cwe_id": cwe,
        "affected_file": path,
        "affected_function": function,
        "has_poc": has_poc,
        "poc_reproduced": poc_reproduced,
        "human_rerun_after_ai_edit": human_rerun,
        "severity_claimed": severity,
    }


def _main_fixture():
    return [
        _report("r1"),
        _report(
            "r2", cve="CVE-2026-10002", cwe="CWE-79", path="src/render.py",
            function="render_page", severity="medium",
        ),
        _report("r3", has_poc=False, poc_reproduced=False),
        _report("r4", cve="CVE-2026-10002", cwe="CWE-79",
                path="src/render.py", function="render_page",
                severity="medium", poc_reproduced=False),
        _report("r5", human_rerun=False),
        _report("r6", cve="CVE-2026-99999"),
        _report("r7", cwe="CWE-79"),
        _report("r8", cve="CVE-2026-10002", cwe="CWE-79",
                path="src/wrong.py", function="render_page",
                severity="medium"),
        _report(
            "r9", cve="CVE-2026-10003", cwe="CWE-22", path="src/files.py",
            function="serve_file", severity="medium",
        ),
        _report(
            "r10", cve="CVE-2026-10004", path="src/db.py",
            function="run_query", severity="high",
        ),
    ]


MAIN = _main_fixture()

PASS_FIXTURE = [
    _report("p1"),
    _report(
        "p2", cve="CVE-2026-10002", cwe="CWE-79", path="src/render.py",
        function="render_page", severity="medium",
    ),
    _report("p3"),
    _report(
        "p4", cve="CVE-2026-10002", cwe="CWE-79", path="src/render.py",
        function="render_page", severity="medium",
    ),
    _report("p5", cve="CVE-2026-99999"),
]

REVIEW_FIXTURE = [
    _report("v1"),
    _report(
        "v2", cve="CVE-2026-10002", cwe="CWE-79", path="src/render.py",
        function="render_page", severity="medium",
    ),
    _report("v3", has_poc=False, poc_reproduced=False),
    _report("v4", human_rerun=False),
]

FALSE_REJECTION_FIXTURE = [
    _report("f1"),
    _report("f2", cwe="CWE-79"),
    _report("f3", cve="CVE-2026-99999"),
]

# (case_id, kind, payload, expected)
CASES = [
    ("bands", "bands", None,
     {"9.2": "critical", "6.1": "medium", "3.9": "low", "7.0": "high"}),
    ("report-pass", "report", _report(), DECISION_PASS),
    ("report-hold-no-poc", "report",
     _report(has_poc=False, poc_reproduced=False), DECISION_HOLD),
    ("report-hold-poc-not-reproduced", "report",
     _report(poc_reproduced=False), DECISION_HOLD),
    ("report-hold-no-human-rerun", "report",
     _report(human_rerun=False), DECISION_HOLD),
    ("report-hold-severity-two-bands", "report",
     _report(cve="CVE-2026-10002", cwe="CWE-79", path="src/render.py",
             function="render_page", severity="critical"),
     DECISION_HOLD),
    ("report-pass-severity-one-band", "report",
     _report(cve="CVE-2026-10002", cwe="CWE-79", path="src/render.py",
             function="render_page", severity="high"),
     DECISION_PASS),
    ("report-hold-severity-missing", "report",
     _report(severity=None), DECISION_HOLD),
    ("report-drop-unknown-cve", "report",
     _report(cve="CVE-2026-99999"), DECISION_DROP),
    ("report-drop-missing-cve", "report",
     _report(cve=None), DECISION_DROP),
    ("report-drop-wrong-cwe", "report",
     _report(cwe="CWE-79"), DECISION_DROP),
    ("report-drop-wrong-location", "report",
     _report(path="src/other.py"), DECISION_DROP),
    ("report-drop-not-reproduced", "report",
     _report(cve="CVE-2026-10003", cwe="CWE-22", path="src/files.py",
             function="serve_file", severity="medium"),
     DECISION_DROP),
    ("report-false-pass-patched-fork", "report",
     _report(cve="CVE-2026-10004", path="src/db.py",
             function="run_query", severity="high"),
     DECISION_PASS),
    ("report-error-missing-field", "report_error",
     "missing_has_poc", "ValueError"),
    ("report-error-bad-severity", "report_error",
     "bad_severity", "ValueError"),
    ("campaign-block", "campaign", MAIN,
     {"verdict": VERDICT_BLOCK, "count": 10, "passed": 3, "held": 3,
      "dropped": 4, "valid": 7, "true_positives": 2,
      "precision": 0.6667, "recall": 0.2857, "false_rejection_rate": 0.2857,
      "hold_rate": 0.3, "drop_rate": 0.4, "dropped_invalid": 2,
      "minutes_saved": 40}),
    ("campaign-pass", "campaign", PASS_FIXTURE,
     {"verdict": VERDICT_PASS, "count": 5, "passed": 4, "dropped": 1,
      "precision": 1.0, "recall": 1.0, "false_rejection_rate": 0.0,
      "minutes_saved": 20}),
    ("campaign-review", "campaign", REVIEW_FIXTURE,
     {"verdict": VERDICT_REVIEW, "count": 4, "passed": 2, "held": 2,
      "precision": 1.0, "recall": 0.5, "false_rejection_rate": 0.0,
      "minutes_saved": 0}),
    ("campaign-block-false-rejection", "campaign",
     FALSE_REJECTION_FIXTURE,
     {"verdict": VERDICT_BLOCK, "count": 3, "passed": 1, "dropped": 2,
      "precision": 1.0, "recall": 0.5, "false_rejection_rate": 0.5}),
    ("campaign-empty", "campaign", [],
     {"verdict": VERDICT_REVIEW, "count": 0, "precision": None,
      "recall": None, "false_rejection_rate": None,
      "minutes_saved": None}),
    ("campaign-no-valid", "campaign",
     [_report("n1", cve="CVE-2026-99999"),
      _report("n2", cve="CVE-2026-99998")],
     {"verdict": VERDICT_REVIEW, "count": 2, "dropped": 2, "valid": 0,
      "precision": None, "recall": None, "false_rejection_rate": None,
      "minutes_saved": 40}),
    ("campaign-error-bad-minutes", "campaign_error", MAIN, "ValueError"),
    ("format-summary", "summary", MAIN,
     "TriageGate: 10 reports, 3 passed, 3 held, 4 dropped, "
     "precision 0.6667, recall 0.2857, false rejection 0.2857, "
     "40 min saved, verdict BLOCK"),
    ("format-summary-empty", "summary", [],
     "TriageGate: 0 reports, 0 passed, 0 held, 0 dropped, "
     "precision n/a, recall n/a, false rejection n/a, "
     "time unmeasured, verdict REVIEW"),
]

EXPECTED_CAMPAIGN = {
    "count": 10,
    "passed": 3,
    "held": 3,
    "dropped": 4,
    "valid": 7,
    "true_positives": 2,
    "precision": 0.6667,
    "recall": 0.2857,
    "false_rejection_rate": 0.2857,
    "hold_rate": 0.3,
    "drop_rate": 0.4,
    "dropped_invalid": 2,
    "minutes_saved": 40,
    "verdict": VERDICT_BLOCK,
}


def _round(value):
    return None if value is None else round(value, 4)


def _check(kind, payload, expected):
    if kind == "bands":
        got = {
            "9.2": severity_band(9.2),
            "6.1": severity_band(6.1),
            "3.9": severity_band(3.9),
            "7.0": severity_band(7.0),
        }
        return got == expected, got
    if kind == "report":
        got = score_report(payload, TRUTH)["decision"]
        return got == expected, got
    if kind == "report_error":
        try:
            if payload == "missing_has_poc":
                report = _report()
                del report["has_poc"]
                score_report(report, TRUTH)
            else:
                score_report(_report(severity="urgent"), TRUTH)
        except ValueError:
            return expected == "ValueError", "ValueError"
        return False, "no error"
    if kind == "campaign":
        campaign = score_campaign(payload, TRUTH, minutes_per_report=20)
        got = {"verdict": campaign["verdict"]}
        for key in (
            "count", "passed", "held", "dropped", "valid",
            "true_positives", "dropped_invalid",
        ):
            if key in expected:
                got[key] = campaign[key]
        for key in (
            "precision", "recall", "false_rejection_rate",
            "hold_rate", "drop_rate",
        ):
            if key in expected:
                got[key] = _round(campaign[key])
        if "minutes_saved" in expected:
            got["minutes_saved"] = campaign["minutes_saved"]
        return got == expected, got
    if kind == "campaign_error":
        try:
            score_campaign(payload, TRUTH, minutes_per_report=-1)
        except ValueError:
            return expected == "ValueError", "ValueError"
        return False, "no error"
    if kind == "summary":
        campaign = score_campaign(payload, TRUTH, minutes_per_report=20)
        got = format_summary(campaign)
        return got == expected, got
    raise ValueError("unknown case kind %s" % kind)


def main():
    rows = []
    matched = 0
    for case_id, kind, payload, expected in CASES:
        match, got = _check(kind, payload, expected)
        matched += 1 if match else 0
        rows.append({
            "case_id": case_id,
            "kind": kind,
            "expected": expected,
            "actual": got,
            "match": match,
        })

    campaign = score_campaign(MAIN, TRUTH, minutes_per_report=20)
    campaign_block = {
        "count": campaign["count"],
        "passed": campaign["passed"],
        "held": campaign["held"],
        "dropped": campaign["dropped"],
        "valid": campaign["valid"],
        "true_positives": campaign["true_positives"],
        "precision": _round(campaign["precision"]),
        "recall": _round(campaign["recall"]),
        "false_rejection_rate": _round(campaign["false_rejection_rate"]),
        "hold_rate": _round(campaign["hold_rate"]),
        "drop_rate": _round(campaign["drop_rate"]),
        "dropped_invalid": campaign["dropped_invalid"],
        "minutes_saved": campaign["minutes_saved"],
        "verdict": campaign["verdict"],
    }
    campaign_ok = campaign_block == EXPECTED_CAMPAIGN

    summary = {
        "cases": rows,
        "matched": matched,
        "total": len(CASES),
        "campaign": campaign_block,
        "campaign_match": campaign_ok,
    }
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2)

    print("TriageGate verify: %d/%d cases matched"
          % (matched, len(CASES)))
    print("campaign:", json.dumps(campaign_block, sort_keys=True))
    ok = matched == len(CASES) and campaign_ok
    if not ok:
        print("MISMATCH: see summary.json")
        return 1
    print("25/25 match, campaign block matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
