"""Tests for trustrun.triage_gate."""

import pytest

from trustrun.triage_gate import (
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


def test_severity_band_boundaries():
    assert severity_band(10.0) == "critical"
    assert severity_band(9.0) == "critical"
    assert severity_band(8.9) == "high"
    assert severity_band(7.0) == "high"
    assert severity_band(6.9) == "medium"
    assert severity_band(4.0) == "medium"
    assert severity_band(3.9) == "low"
    assert severity_band(0.1) == "low"
    assert severity_band(0.0) == "none"


def test_severity_band_rejects_bad_values():
    with pytest.raises(ValueError):
        severity_band(-0.1)
    with pytest.raises(ValueError):
        severity_band(10.1)
    with pytest.raises(ValueError):
        severity_band("9.8")
    with pytest.raises(ValueError):
        severity_band(True)


def test_full_valid_report_passes():
    result = score_report(_report(), TRUTH)
    assert result["decision"] == DECISION_PASS
    assert all(result["checks"].values())
    assert result["reasons"] == []


def test_no_poc_holds():
    result = score_report(_report(has_poc=False, poc_reproduced=False), TRUTH)
    assert result["decision"] == DECISION_HOLD
    assert result["checks"]["poc_reproduced"] is False
    assert "no reproduced proof of concept" in result["reasons"]


def test_poc_present_but_not_reproduced_holds():
    result = score_report(_report(poc_reproduced=False), TRUTH)
    assert result["decision"] == DECISION_HOLD
    assert result["checks"]["poc_reproduced"] is False


def test_no_human_rerun_holds():
    result = score_report(_report(human_rerun=False), TRUTH)
    assert result["decision"] == DECISION_HOLD
    assert result["checks"]["human_rerun"] is False
    assert "no human re-run after the last AI edit" in result["reasons"]


def test_severity_two_bands_off_holds():
    report = _report(
        cve="CVE-2026-10002", cwe="CWE-79", path="src/render.py",
        function="render_page", severity="critical",
    )
    result = score_report(report, TRUTH)
    assert result["decision"] == DECISION_HOLD
    assert result["checks"]["severity_consistent"] is False


def test_severity_one_band_off_passes():
    report = _report(
        cve="CVE-2026-10002", cwe="CWE-79", path="src/render.py",
        function="render_page", severity="high",
    )
    result = score_report(report, TRUTH)
    assert result["decision"] == DECISION_PASS
    assert result["checks"]["severity_consistent"] is True


def test_missing_severity_holds():
    result = score_report(_report(severity=None), TRUTH)
    assert result["decision"] == DECISION_HOLD
    assert result["checks"]["severity_consistent"] is False


def test_unknown_cve_drops():
    result = score_report(_report(cve="CVE-2026-99999"), TRUTH)
    assert result["decision"] == DECISION_DROP
    assert result["checks"]["cve_known"] is False
    assert result["checks"]["cwe_matches"] is False
    assert result["checks"]["location_matches"] is False


def test_missing_cve_drops():
    result = score_report(_report(cve=None), TRUTH)
    assert result["decision"] == DECISION_DROP
    assert result["checks"]["cve_known"] is False


def test_wrong_cwe_drops():
    result = score_report(_report(cwe="CWE-79"), TRUTH)
    assert result["decision"] == DECISION_DROP
    assert result["checks"]["cwe_matches"] is False
    assert "claimed CWE does not match the record" in result["reasons"]


def test_wrong_location_drops():
    result = score_report(_report(path="src/other.py"), TRUTH)
    assert result["decision"] == DECISION_DROP
    assert result["checks"]["location_matches"] is False


def test_wrong_function_drops():
    result = score_report(_report(function="other_fn"), TRUTH)
    assert result["decision"] == DECISION_DROP
    assert result["checks"]["location_matches"] is False


def test_never_reproduced_cve_drops():
    report = _report(
        cve="CVE-2026-10003", cwe="CWE-22", path="src/files.py",
        function="serve_file", severity="medium",
    )
    result = score_report(report, TRUTH)
    assert result["decision"] == DECISION_DROP
    assert result["checks"]["cve_reproduced"] is False
    assert "CVE was never reproduced in the record" in result["reasons"]


def test_false_pass_patched_fork():
    report = _report(
        cve="CVE-2026-10004", path="src/db.py", function="run_query",
        severity="high",
    )
    result = score_report(report, TRUTH)
    assert result["decision"] == DECISION_PASS
    assert all(result["checks"].values())


def test_contradiction_beats_evidence_gap():
    report = _report(cwe="CWE-79", has_poc=False, poc_reproduced=False)
    result = score_report(report, TRUTH)
    assert result["decision"] == DECISION_DROP


def test_report_rejects_missing_field():
    report = _report()
    del report["has_poc"]
    with pytest.raises(ValueError):
        score_report(report, TRUTH)


def test_report_rejects_bad_severity():
    with pytest.raises(ValueError):
        score_report(_report(severity="urgent"), TRUTH)


def test_report_rejects_non_bool_poc():
    with pytest.raises(ValueError):
        score_report(_report(has_poc="yes"), TRUTH)


def test_report_rejects_non_dict():
    with pytest.raises(ValueError):
        score_report(["r1"], TRUTH)


def test_truth_map_rejects_mismatched_key():
    bad = {"CVE-2026-10001": _record(cve="CVE-2026-10002")}
    with pytest.raises(ValueError):
        score_report(_report(), bad)


def test_truth_map_rejects_bad_cvss():
    bad = {"CVE-2026-10001": _record(cvss=11.0)}
    with pytest.raises(ValueError):
        score_report(_report(), bad)


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


def test_campaign_block_main_fixture():
    campaign = score_campaign(_main_fixture(), TRUTH, minutes_per_report=20)
    assert campaign["count"] == 10
    assert campaign["passed"] == 3
    assert campaign["held"] == 3
    assert campaign["dropped"] == 4
    assert campaign["valid"] == 7
    assert campaign["true_positives"] == 2
    assert round(campaign["precision"], 4) == 0.6667
    assert round(campaign["recall"], 4) == 0.2857
    assert round(campaign["false_rejection_rate"], 4) == 0.2857
    assert campaign["hold_rate"] == 0.3
    assert campaign["drop_rate"] == 0.4
    assert campaign["dropped_invalid"] == 2
    assert campaign["minutes_saved"] == 40
    assert campaign["verdict"] == VERDICT_BLOCK


def test_campaign_pass_fixture():
    reports = [
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
    campaign = score_campaign(reports, TRUTH, minutes_per_report=20)
    assert campaign["precision"] == 1.0
    assert campaign["recall"] == 1.0
    assert campaign["false_rejection_rate"] == 0.0
    assert campaign["minutes_saved"] == 20
    assert campaign["verdict"] == VERDICT_PASS


def test_campaign_review_low_recall():
    reports = [
        _report("v1"),
        _report(
            "v2", cve="CVE-2026-10002", cwe="CWE-79", path="src/render.py",
            function="render_page", severity="medium",
        ),
        _report("v3", has_poc=False, poc_reproduced=False),
        _report("v4", human_rerun=False),
    ]
    campaign = score_campaign(reports, TRUTH)
    assert campaign["precision"] == 1.0
    assert campaign["recall"] == 0.5
    assert campaign["false_rejection_rate"] == 0.0
    assert campaign["minutes_saved"] is None
    assert campaign["verdict"] == VERDICT_REVIEW


def test_campaign_block_false_rejection():
    reports = [
        _report("f1"),
        _report("f2", cwe="CWE-79"),
        _report("f3", cve="CVE-2026-99999"),
    ]
    campaign = score_campaign(reports, TRUTH)
    assert campaign["precision"] == 1.0
    assert campaign["recall"] == 0.5
    assert campaign["false_rejection_rate"] == 0.5
    assert campaign["verdict"] == VERDICT_BLOCK


def test_campaign_empty_is_review():
    campaign = score_campaign([], TRUTH)
    assert campaign["count"] == 0
    assert campaign["precision"] is None
    assert campaign["recall"] is None
    assert campaign["false_rejection_rate"] is None
    assert campaign["minutes_saved"] is None
    assert campaign["verdict"] == VERDICT_REVIEW


def test_campaign_no_valid_reports_is_review():
    reports = [
        _report("n1", cve="CVE-2026-99999"),
        _report("n2", cve="CVE-2026-99998"),
    ]
    campaign = score_campaign(reports, TRUTH, minutes_per_report=20)
    assert campaign["valid"] == 0
    assert campaign["precision"] is None
    assert campaign["recall"] is None
    assert campaign["false_rejection_rate"] is None
    assert campaign["minutes_saved"] == 40
    assert campaign["verdict"] == VERDICT_REVIEW


def test_campaign_rejects_bad_minutes():
    with pytest.raises(ValueError):
        score_campaign(_main_fixture(), TRUTH, minutes_per_report=-1)
    with pytest.raises(ValueError):
        score_campaign(_main_fixture(), TRUTH, minutes_per_report="20")


def test_campaign_rejects_non_list():
    with pytest.raises(ValueError):
        score_campaign({"r1": _report()}, TRUTH)


def test_format_summary_main():
    campaign = score_campaign(_main_fixture(), TRUTH, minutes_per_report=20)
    assert format_summary(campaign) == (
        "TriageGate: 10 reports, 3 passed, 3 held, 4 dropped, "
        "precision 0.6667, recall 0.2857, false rejection 0.2857, "
        "40 min saved, verdict BLOCK"
    )


def test_format_summary_unmeasured_time():
    campaign = score_campaign([_report()], TRUTH)
    assert "time unmeasured" in format_summary(campaign)
    assert "verdict PASS" in format_summary(campaign)


def test_format_summary_empty():
    campaign = score_campaign([], TRUTH)
    assert format_summary(campaign) == (
        "TriageGate: 0 reports, 0 passed, 0 held, 0 dropped, "
        "precision n/a, recall n/a, false rejection n/a, "
        "time unmeasured, verdict REVIEW"
    )


def test_hold_is_not_false_rejection():
    reports = [_report("h1", has_poc=False, poc_reproduced=False)]
    campaign = score_campaign(reports, TRUTH)
    assert campaign["false_rejection_rate"] == 0.0
    assert campaign["recall"] == 0.0
    assert campaign["verdict"] == VERDICT_REVIEW
