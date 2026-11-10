"""Tests for the ILAudit module: SB 315 audit-report mapping and
incident-threshold classification."""

import pytest

from trustrun.cli import run_audit
from trustrun.il_audit import (
    DISCLAIMER,
    FRAMEWORK_TOPICS,
    MODULE_MAP,
    REPORT_CONTENTS,
    STATUTE,
    format_summary,
    incident_triggers_reporting,
    score_report,
)


def _ready_report():
    return {
        "agent": "stub",
        "task": "stub task",
        "k": 5,
        "seed": 0,
        "tools_capable": False,
        "sections": {
            "contract": {"verdict": "READY"},
            "stress": {"verdict": "READY"},
            "consistency": {"verdict": "READY"},
            "data": {"verdict": "READY"},
        },
        "verdict": "READY",
    }


def _blocked_report():
    report = _ready_report()
    report["sections"]["stress"]["verdict"] = "BLOCK"
    report["sections"]["consistency"]["verdict"] = "REVIEW"
    report["verdict"] = "BLOCK"
    return report


def test_statute_constants():
    assert STATUTE["public_act"] == "104-0538"
    assert STATUTE["bill"] == "SB 315"
    assert STATUTE["signed"] == "2026-07-06"
    assert STATUTE["revenue_threshold_usd"] == 500_000_000
    assert STATUTE["compute_threshold_flops"] == 10 ** 26


def test_seven_report_contents_a_to_g():
    assert [c["id"] for c in REPORT_CONTENTS] == list("ABCDEFG")
    for content in REPORT_CONTENTS:
        assert content["statute"].startswith("Section 10(d)(2)(")
        assert content["title"]
        assert content["description"]


def test_ten_framework_topics():
    assert len(FRAMEWORK_TOPICS) == 10
    assert [t["id"] for t in FRAMEWORK_TOPICS] == list(range(1, 11))
    titles = [t["title"] for t in FRAMEWORK_TOPICS]
    assert "Weight cybersecurity" in titles
    assert "Internal-use catastrophic risk" in titles
    assert "Incident response" in titles


def test_module_map_covers_all_four_modules():
    assert set(MODULE_MAP) == {"contract", "stress", "consistency", "data"}
    for module, entry in MODULE_MAP.items():
        assert entry["role"]
        assert entry["description"]
        assert entry["framework_topics"]
        assert entry["report_contents"]
        for topic in entry["framework_topics"]:
            assert 1 <= topic <= 10, (module, topic)
        for content in entry["report_contents"]:
            assert content in "ABCDEFG", (module, content)


def test_ready_report_alone_is_block_with_three_gaps():
    scored = score_report(_ready_report())
    assert scored["verdict"] == "BLOCK"
    assert scored["gaps"] == ["D", "E", "G"]
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["A"]["status"] == "covered"
    assert by_id["B"]["status"] == "covered"
    assert "No material deviations" in by_id["B"]["evidence"]
    assert by_id["C"]["status"] == "partial"
    assert by_id["F"]["status"] == "covered"
    assert "seed=0" in by_id["F"]["evidence"]
    assert "k=5" in by_id["F"]["evidence"]
    assert scored["covered"] == 3
    assert scored["partial"] == 1
    assert scored["coverage"] == pytest.approx((3 + 0.5) / 7)
    assert scored["note"] == DISCLAIMER
    assert "not legal advice" in scored["note"]


def test_blocked_report_deviations_are_partial_not_covered():
    scored = score_report(_blocked_report())
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["B"]["status"] == "partial"
    assert "stress" in by_id["B"]["evidence"]
    assert "consistency" in by_id["B"]["evidence"]
    assert by_id["C"]["status"] == "partial"
    assert scored["verdict"] == "BLOCK"


def test_auditor_record_fills_the_human_contents():
    auditor = {
        "personnel": ["Lead Auditor", "Technical Reviewer"],
        "conflicts_procedure": "No financial interest; conflicts logged.",
        "lead_auditor": "Lead Auditor",
        "signed": True,
    }
    scored = score_report(_ready_report(), auditor=auditor)
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["D"]["status"] == "covered"
    assert by_id["E"]["status"] == "covered"
    assert by_id["G"]["status"] == "covered"
    assert scored["gaps"] == []
    assert scored["verdict"] == "REVIEW"  # only (C) stays partial
    assert scored["coverage"] == pytest.approx((6 + 0.5) / 7)


def test_auditor_record_must_be_complete_to_count():
    auditor = {"personnel": ["Lead Auditor"], "lead_auditor": "Lead Auditor"}
    scored = score_report(_ready_report(), auditor=auditor)
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["D"]["status"] == "covered"
    assert by_id["E"]["status"] == "gap"
    assert by_id["G"]["status"] == "gap"  # named but not signed
    assert scored["gaps"] == ["E", "G"]


def test_flat_summary_row_shape_accepted():
    row = {
        "agent": "react",
        "task": "t1_factual",
        "verdict": "REVIEW",
        "contract": "READY",
        "stress": "REVIEW",
        "consistency": "READY",
        "data": "READY",
    }
    scored = score_report(row)
    assert scored["verdict"] == "BLOCK"
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["B"]["status"] == "partial"
    assert "stress" in by_id["B"]["evidence"]


def test_score_report_rejects_bad_input():
    with pytest.raises(TypeError):
        score_report("not a dict")
    with pytest.raises(ValueError):
        score_report({"sections": {"contract": {"verdict": "READY"}}})
    bad = _ready_report()
    bad["sections"]["data"] = {"verdict": "MAYBE"}
    with pytest.raises(ValueError):
        score_report(bad)
    with pytest.raises(TypeError):
        score_report(_ready_report(), auditor="not a dict")


def test_hf_escape_does_not_trigger_reporting():
    # AEI comparative report (Oct 2026): the July 2026 OpenAI-Hugging
    # Face escape was a loss of control with no death, bodily injury,
    # or materialized catastrophic risk, so it meets no Section 5 prong.
    result = incident_triggers_reporting({"loss_of_control": True})
    assert result["triggers"] is False
    assert result["deadline_hours"] is None
    assert result["prongs"] == []


def test_weight_exfiltration_with_injury_triggers_72_hours():
    result = incident_triggers_reporting({
        "weights_exfiltrated": True,
        "death_or_bodily_injury": True,
    })
    assert result["triggers"] is True
    assert result["prongs"] == [1]
    assert result["deadline_hours"] == 72


def test_weight_leak_without_injury_does_not_trigger():
    result = incident_triggers_reporting({"weights_exfiltrated": True})
    assert result["triggers"] is False
    assert result["prongs"] == []


def test_catastrophic_risk_materialized_triggers():
    result = incident_triggers_reporting({
        "catastrophic_risk_materialized": True,
    })
    assert result["triggers"] is True
    assert result["prongs"] == [2]
    assert result["deadline_hours"] == 72


def test_imminent_risk_shortens_deadline_to_24_hours():
    result = incident_triggers_reporting({
        "loss_of_control": True,
        "death_or_bodily_injury": True,
        "imminent_risk": True,
    })
    assert result["triggers"] is True
    assert result["prongs"] == [3]
    assert result["deadline_hours"] == 24


def test_deceptive_subversion_outside_eval_triggers_prong_4():
    result = incident_triggers_reporting({
        "deceptive_subversion": True,
        "materially_increased_catastrophic_risk": True,
    })
    assert result["triggers"] is True
    assert result["prongs"] == [4]
    assert result["deadline_hours"] == 72


def test_deceptive_subversion_inside_eval_does_not_trigger():
    result = incident_triggers_reporting({
        "deceptive_subversion": True,
        "materially_increased_catastrophic_risk": True,
        "in_evaluation": True,
    })
    assert result["triggers"] is False
    assert result["prongs"] == []


def test_incident_requires_dict():
    with pytest.raises(TypeError):
        incident_triggers_reporting("not a dict")


def test_format_summary_names_verdict_gaps_and_disclaimer():
    text = format_summary(score_report(_ready_report()))
    assert "ILAudit readiness: BLOCK" in text
    assert "Gaps: D, E, G" in text
    assert "not legal advice" in text
    for content_id in "ABCDEFG":
        assert "(%s)" % content_id in text


def test_real_run_audit_report_scores():
    def stub_agent(task_text):
        return {"result": "42"}

    report = run_audit(
        stub_agent,
        {"text": "What is 6 times 7?", "expect": "42"},
        seed=0,
        k=2,
    )
    scored = score_report(report)
    assert scored["verdict"] == "BLOCK"
    assert scored["gaps"] == ["D", "E", "G"]
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["F"]["status"] == "covered"
    assert "seed=0" in by_id["F"]["evidence"]
    assert "k=2" in by_id["F"]["evidence"]
