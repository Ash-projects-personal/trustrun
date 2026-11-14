"""TriageGate: verify an AI-generated vulnerability report before a
maintainer spends time on it.

AI finds vulnerabilities faster than humans can patch them, and the
backlog is the proof. The queue's evidence: PHP2Shell
(CVE-2026-109618/109619, CVSS 9.2, unauthenticated remote code
execution; a 2024 crash turned into remote code execution in about
two weeks with AI tools, and four engineers took two months to
patch); one automated OpenAI run found and patched 948 Linux kernel
local-privilege-escalation paths, 61 of them upstream about ten days
later; Postgres 19 general availability was pushed to Nov 19, 2026
after LLM review surfaced about 40 defects; Anthropic scanned open
source, found 1,596 vulnerabilities, 97 patched as of May 22. The
finding rate is real and growing; the triage capacity is not.

What is new here is the maintainer-side intake receipt, not the
idea that reports should be checked. Two adjacent tools work the
researcher side, before submission. bbgate (github.com/sonnycroco/
bbgate, open source) runs nine checks on an AI-drafted bug bounty
finding and answers READY, HOLD, or DROP: it verifies that proof
exists and that a human re-ran the bug after the model last touched
the report, and it says so itself that it trusts the manifest, that
it checks evidence of a kind was captured, not that the bytes say
what is claimed. It is a discipline tool, not a lie detector, and
it never touches a target. Free Triage (github.com/Hsnmughal/
Free-Triager, open source) pre-validates a report against a bug
bounty platform's submission rules: scope, severity, a runnable
proof of concept on a mainnet fork. It separates automated-triage
readiness from technical validity and does not score the report
itself. OSec Incenter (commercial, osec.com, Mar 18, 2026) validates
AI security findings with a proprietary engine plus a human testing
team; it is a service, not a shipped receipt a team can run on its
own intake. CVE-Genie (arXiv:2509.01835) reproduces CVEs: 428 of 841
CVEs published 2024-2025 reproduced with verifiable exploits, at
about $2.77 per CVE. It generates benchmarks; it does not score an
incoming report. CWE-bench (arXiv:2610.17020, Oct 12, 2026) is a
private benchmark of 120 held-out repository audit-and-repair tasks;
it grades agents, not reports. The CVE-Bench family settles the
CVE-to-patch benchmark; no new patch bench is claimed here.

The new piece is the intake auditor plus the receipt inside
Trustrun's trust report: a team's own incoming reports scored
against its own CVE reproduction record (CVE-Genie-shaped ground
truth: which CVEs were reproduced, their CWE, vulnerable location,
and CVSS), with precision, recall, and false-rejection rate
reported against labeled validity, and the estimated maintainer
time saved computed only from the team's own per-report triage
time, never from a paper. The human re-run check is bbgate's
check_8 discipline, adopted and cited, not re-invented. The
verdict bars are Trustrun's chosen bars, documented below.

A report is one recorded incoming vulnerability report: the CVE
it claims, the CWE it claims, the file and function it claims are
vulnerable, whether a reproducible proof-of-concept artifact is
attached and whether it was executed and reproduced the issue,
whether a human re-ran the bug after the last AI edit, and the
severity it claims. A ground-truth record is one CVE from the
team's reproduction set: its CWE, vulnerable file and function,
CVSS score, whether it was reproduced, and whether the
vulnerability is real in the team's codebase (the labeled
validity the campaign scores against; the gate never sees it).

The gate decides PASS (escalate to a maintainer), HOLD (evidence
gap, ask for more), or DROP (contradicted by the record). DROP
when the claimed CVE is unknown, the CWE does not match the
record, the location does not match, or the record says the CVE
was never reproduced: the report's premise is contradicted, not
merely unproven. HOLD when the evidence is thin but nothing is
contradicted: no proof of concept, a proof of concept that was
never run to reproduction, no human re-run after the last AI
edit, or a claimed severity more than one band from the CVSS
band. PASS only when every check holds. The campaign verdict
bars are Trustrun's chosen bars: PASS when precision is at least
0.95, recall at least 0.80, and the false-rejection rate at most
0.05; BLOCK when precision is below 0.80 or the false-rejection
rate is above 0.20; otherwise REVIEW. An empty campaign, or one
with no valid reports to score recall against, is REVIEW: there
is nothing to score, so it is unscored, never passed.

Honest limits, read before quoting any number from this module:
evidence checks cannot catch a proof of concept that reproduces
the wrong thing. A report on a real, reproduced CVE, with the
right CWE and location and a reproduced proof of concept, passes
every check even when the vulnerability is already fixed in the
team's own fork: the gate checks the report against the CVE
record, not the team's tree, and the labeled campaign exists
precisely to expose that gap as a false positive. A DROP is a
contradiction by the record, not proof the report is false in
every sense: a CVE the record has not reproduced yet is dropped
until it is reproduced. The minutes saved are an estimate at the
team's own per-report triage time, supplied by the caller; with
no triage time supplied the receipt reports it as unmeasured,
never as zero. The labeled cases in the verify script are fixed
fixture reports with hand-computed scores, using fixture CVE
identifiers (CVE-2026-10001 and friends), not real CVEs and not
CVE-Genie data; the live run over a team's real intake and its
CVE-Genie reproduction set stays future work.
"""

VERDICT_BLOCK = "BLOCK"
VERDICT_REVIEW = "REVIEW"
VERDICT_PASS = "PASS"

DECISION_PASS = "PASS"
DECISION_HOLD = "HOLD"
DECISION_DROP = "DROP"

SEVERITIES = ("critical", "high", "medium", "low")

# Trustrun's chosen bars (not the papers').
PRECISION_PASS = 0.95
RECALL_PASS = 0.80
FALSE_REJECTION_PASS = 0.05
PRECISION_BLOCK = 0.80
FALSE_REJECTION_BLOCK = 0.20

_SEVERITY_RANK = {
    "critical": 3,
    "high": 2,
    "medium": 1,
    "low": 0,
}


def severity_band(cvss):
    """CVSS numeric score to its severity band.

    Bands follow the CVSS qualitative scale: critical at 9.0 and
    above, high at 7.0, medium at 4.0, low above 0.0, none at 0.0.
    """
    if isinstance(cvss, bool) or not isinstance(cvss, (int, float)):
        raise ValueError("cvss must be a number")
    if cvss < 0.0 or cvss > 10.0:
        raise ValueError("cvss must be between 0.0 and 10.0")
    if cvss == 0.0:
        return "none"
    if cvss >= 9.0:
        return "critical"
    if cvss >= 7.0:
        return "high"
    if cvss >= 4.0:
        return "medium"
    return "low"


def _check_report(report):
    if not isinstance(report, dict):
        raise ValueError("report must be a dict")
    for key in (
        "report_id",
        "cve_id",
        "cwe_id",
        "affected_file",
        "affected_function",
        "has_poc",
        "poc_reproduced",
        "human_rerun_after_ai_edit",
        "severity_claimed",
    ):
        if key not in report:
            raise ValueError("report is missing %s" % key)
    if not isinstance(report["report_id"], str):
        raise ValueError("report_id must be a string")
    for key in ("cve_id", "cwe_id", "affected_file", "affected_function"):
        value = report[key]
        if value is not None and not isinstance(value, str):
            raise ValueError("%s must be a string or None" % key)
    for key in ("has_poc", "poc_reproduced", "human_rerun_after_ai_edit"):
        if not isinstance(report[key], bool):
            raise ValueError("%s must be a bool" % key)
    severity = report["severity_claimed"]
    if severity is not None and severity not in SEVERITIES:
        raise ValueError(
            "severity_claimed must be one of %s or None" % (SEVERITIES,)
        )


def _check_record(record):
    if not isinstance(record, dict):
        raise ValueError("record must be a dict")
    for key in (
        "cve_id",
        "cwe_id",
        "affected_file",
        "affected_function",
        "cvss",
        "reproduced",
        "valid",
    ):
        if key not in record:
            raise ValueError("record is missing %s" % key)
    for key in ("cve_id", "cwe_id", "affected_file", "affected_function"):
        if not isinstance(record[key], str):
            raise ValueError("%s must be a string" % key)
    severity_band(record["cvss"])
    for key in ("reproduced", "valid"):
        if not isinstance(record[key], bool):
            raise ValueError("%s must be a bool" % key)


def _check_truth_map(truth_map):
    if not isinstance(truth_map, dict):
        raise ValueError("truth_map must be a dict")
    for cve_id, record in truth_map.items():
        if not isinstance(cve_id, str):
            raise ValueError("truth_map keys must be CVE strings")
        _check_record(record)
        if record["cve_id"] != cve_id:
            raise ValueError("record cve_id must match its truth_map key")


def score_report(report, truth_map):
    """Score one incoming report against the CVE record.

    Returns the per-check booleans, the decision, and the reasons.
    Checks the gate cannot run are False, never assumed: an
    unknown CVE makes the CWE, location, and reproduction checks
    False too. A proof of concept that was never run counts as no
    reproduction, whether or not one is attached. A missing claimed
    severity is an evidence gap (HOLD), not a contradiction.
    """
    _check_report(report)
    _check_truth_map(truth_map)
    record = truth_map.get(report["cve_id"]) if report["cve_id"] else None
    checks = {}
    reasons = []
    checks["cve_known"] = record is not None
    if not checks["cve_known"]:
        reasons.append("claimed CVE is not in the record")
    checks["cwe_matches"] = bool(
        record is not None and report["cwe_id"] == record["cwe_id"]
    )
    if record is not None and not checks["cwe_matches"]:
        reasons.append("claimed CWE does not match the record")
    checks["location_matches"] = bool(
        record is not None
        and report["affected_file"] == record["affected_file"]
        and report["affected_function"] == record["affected_function"]
    )
    if record is not None and not checks["location_matches"]:
        reasons.append("claimed location does not match the record")
    checks["cve_reproduced"] = bool(
        record is not None and record["reproduced"]
    )
    if record is not None and not checks["cve_reproduced"]:
        reasons.append("CVE was never reproduced in the record")
    checks["poc_reproduced"] = bool(
        report["has_poc"] and report["poc_reproduced"]
    )
    if not checks["poc_reproduced"]:
        reasons.append("no reproduced proof of concept")
    checks["human_rerun"] = bool(report["human_rerun_after_ai_edit"])
    if not checks["human_rerun"]:
        reasons.append("no human re-run after the last AI edit")
    if record is None or report["severity_claimed"] is None:
        checks["severity_consistent"] = False
    else:
        claimed = _SEVERITY_RANK[report["severity_claimed"]]
        actual = _SEVERITY_RANK[severity_band(record["cvss"])]
        checks["severity_consistent"] = abs(claimed - actual) <= 1
    if not checks["severity_consistent"]:
        reasons.append("claimed severity is more than one band off")
    if not (
        checks["cve_known"]
        and checks["cwe_matches"]
        and checks["location_matches"]
        and checks["cve_reproduced"]
    ):
        decision = DECISION_DROP
    elif not (
        checks["poc_reproduced"]
        and checks["human_rerun"]
        and checks["severity_consistent"]
    ):
        decision = DECISION_HOLD
    else:
        decision = DECISION_PASS
    return {
        "report_id": report["report_id"],
        "checks": checks,
        "decision": decision,
        "reasons": reasons,
    }


def _rate(numerator, denominator):
    if denominator == 0:
        return None
    return numerator / denominator


def score_campaign(reports, truth_map, minutes_per_report=None):
    """Score a campaign of incoming reports.

    Precision is passed reports that are truly valid over all
    passed reports; recall is valid reports passed over all valid
    reports; the false-rejection rate is valid reports dropped
    over all valid reports. A HOLD is not a rejection: it asks
    for more evidence, so held valid reports lower recall but do
    not count as false rejections. Minutes saved counts only
    invalid reports the gate dropped, at the team's own
    per-report triage time; with no triage time supplied it is
    None, reported as unmeasured. Verdict PASS when precision is
    at least 0.95, recall at least 0.80, and the false-rejection
    rate at most 0.05; BLOCK when precision is below 0.80 or the
    false-rejection rate is above 0.20; otherwise REVIEW. An
    empty campaign, or one with no valid reports, is REVIEW.
    """
    if not isinstance(reports, list):
        raise ValueError("reports must be a list")
    _check_truth_map(truth_map)
    if minutes_per_report is not None:
        if (
            isinstance(minutes_per_report, bool)
            or not isinstance(minutes_per_report, (int, float))
            or minutes_per_report < 0
        ):
            raise ValueError("minutes_per_report must be a non-negative number")
    if not reports:
        return {
            "reports": [],
            "count": 0,
            "passed": 0,
            "held": 0,
            "dropped": 0,
            "valid": 0,
            "true_positives": 0,
            "precision": None,
            "recall": None,
            "false_rejection_rate": None,
            "hold_rate": None,
            "drop_rate": None,
            "dropped_invalid": 0,
            "minutes_saved": None,
            "verdict": VERDICT_REVIEW,
        }
    scored = [score_report(report, truth_map) for report in reports]
    valid_ids = set()
    for report in reports:
        record = truth_map.get(report["cve_id"]) if report["cve_id"] else None
        if record is not None and record["valid"]:
            valid_ids.add(report["report_id"])
    passed = [item for item in scored if item["decision"] == DECISION_PASS]
    held = [item for item in scored if item["decision"] == DECISION_HOLD]
    dropped = [item for item in scored if item["decision"] == DECISION_DROP]
    true_positives = [
        item for item in passed if item["report_id"] in valid_ids
    ]
    valid_dropped = [
        item for item in dropped if item["report_id"] in valid_ids
    ]
    dropped_invalid = [
        item for item in dropped if item["report_id"] not in valid_ids
    ]
    precision = _rate(len(true_positives), len(passed))
    recall = _rate(len(true_positives), len(valid_ids))
    false_rejection = _rate(len(valid_dropped), len(valid_ids))
    if minutes_per_report is None:
        minutes_saved = None
    else:
        minutes_saved = len(dropped_invalid) * minutes_per_report
    if not valid_ids:
        verdict = VERDICT_REVIEW
    elif precision is not None and precision < PRECISION_BLOCK:
        verdict = VERDICT_BLOCK
    elif false_rejection is not None and false_rejection > FALSE_REJECTION_BLOCK:
        verdict = VERDICT_BLOCK
    elif (
        precision is not None
        and precision >= PRECISION_PASS
        and recall is not None
        and recall >= RECALL_PASS
        and false_rejection is not None
        and false_rejection <= FALSE_REJECTION_PASS
    ):
        verdict = VERDICT_PASS
    else:
        verdict = VERDICT_REVIEW
    return {
        "reports": scored,
        "count": len(reports),
        "passed": len(passed),
        "held": len(held),
        "dropped": len(dropped),
        "valid": len(valid_ids),
        "true_positives": len(true_positives),
        "precision": precision,
        "recall": recall,
        "false_rejection_rate": false_rejection,
        "hold_rate": len(held) / len(reports),
        "drop_rate": len(dropped) / len(reports),
        "dropped_invalid": len(dropped_invalid),
        "minutes_saved": minutes_saved,
        "verdict": verdict,
    }


def format_summary(campaign):
    """One-line human summary of a scored campaign."""
    precision = campaign["precision"]
    precision_text = "%.4f" % precision if precision is not None else "n/a"
    recall = campaign["recall"]
    recall_text = "%.4f" % recall if recall is not None else "n/a"
    false_rejection = campaign["false_rejection_rate"]
    false_text = (
        "%.4f" % false_rejection if false_rejection is not None else "n/a"
    )
    minutes = campaign["minutes_saved"]
    minutes_text = (
        "%d min saved" % minutes if minutes is not None else "time unmeasured"
    )
    return (
        "TriageGate: %d reports, %d passed, %d held, %d dropped, "
        "precision %s, recall %s, false rejection %s, %s, verdict %s"
        % (
            campaign["count"],
            campaign["passed"],
            campaign["held"],
            campaign["dropped"],
            precision_text,
            recall_text,
            false_text,
            minutes_text,
            campaign["verdict"],
        )
    )
