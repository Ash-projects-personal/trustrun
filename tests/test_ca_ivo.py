"""Tests for the CAIVO module: SB 813 IVO methodology proposal,
AB 1405 registry readiness, and SB 1119 child-safety audit timing
and scoring."""

import pytest

from trustrun.ca_ivo import (
    CHILD_SAFETY_AUDIT_AREAS,
    DISCLAIMER,
    IVO_APPLICATION,
    MODULE_MAP,
    REGISTRY_REQUIREMENTS,
    STATUTE,
    build_methodology_proposal,
    child_safety_audit_due,
    format_summary,
    score_child_safety_report,
    score_methodology_proposal,
    score_registry_readiness,
)
from trustrun.cli import run_audit


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


def _complete_registration():
    return {
        "business_name": "Trustrun Audits LLC",
        "contact": "audits@example.org",
        "laws": ["SB 813", "AB 1405"],
        "certifications": ["ISO/IEC 42001 lead auditor"],
        "services_description": "Covered AI audits of agent systems.",
        "sop": "Four-module Trustrun audit methodology.",
        "independence_bars_met": True,
        "retention_years": 10,
        "report_template": {
            "scope": True,
            "objectives": True,
            "results": True,
            "documentation": True,
            "deficiencies": True,
            "remedies": True,
            "signed": True,
            "dated": True,
        },
    }


def test_statute_constants():
    assert STATUTE["sb_813"] == "SB 813"
    assert STATUTE["sb_813_chapter"] == 179
    assert STATUTE["ab_1405"] == "AB 1405"
    assert STATUTE["ab_1405_chapter"] == 178
    assert STATUTE["signed"] == "2026-09-09"
    assert STATUTE["ivo_criteria_due"] == "2028-01-01"
    assert STATUTE["registry_due"] == "2029-01-01"
    assert STATUTE["registry_accelerated_due"] == "2027-05-01"
    assert STATUTE["record_retention_years"] == 10
    assert STATUTE["sb_1119"] == "SB 1119"
    assert STATUTE["sb_1119_signed"] == "2026-09-10"
    assert STATUTE["sb_1119_first_audit_due"] == "2029-01-01"
    assert STATUTE["sb_1119_audit_interval_years"] == 2
    assert STATUTE["sb_1119_small_operator_revenue_usd"] == 500_000_000
    assert STATUTE["sb_1119_small_operator_exempt_until"] == "2032-01-01"
    assert STATUTE["sb_1119_penalty_per_child_negligent_usd"] == 5000
    assert STATUTE["sb_1119_penalty_per_child_intentional_usd"] == 15000


def test_eight_ivo_application_elements():
    assert [e["id"] for e in IVO_APPLICATION] == list("ABCDEFGH")
    for element in IVO_APPLICATION:
        assert element["statute"] == "SB 813"
        assert element["title"]
        assert element["description"]
    titles = [e["title"] for e in IVO_APPLICATION]
    assert "Benchmarks proposed" in titles
    assert "Methodologies proposed" in titles
    assert "Independence from the assessed party" in titles


def test_four_registry_requirements():
    assert [r["id"] for r in REGISTRY_REQUIREMENTS] == list("ABCD")
    titles = [r["title"] for r in REGISTRY_REQUIREMENTS]
    assert "Ten-year record retention" in titles
    assert "Signed report contents" in titles


def test_six_child_safety_audit_areas():
    assert [a["id"] for a in CHILD_SAFETY_AUDIT_AREAS] == list("ABCDEF")
    titles = [a["title"] for a in CHILD_SAFETY_AUDIT_AREAS]
    assert "Risk-assessment accuracy" in titles
    assert "Child-safe defaults" in titles
    assert "Parent notification" in titles
    assert "Crisis protocol under adversarial input" in titles


def test_module_map_covers_all_four_modules():
    assert set(MODULE_MAP) == {"contract", "stress", "consistency", "data"}
    for module, entry in MODULE_MAP.items():
        assert entry["role"]
        assert entry["description"]
        assert entry["ivo_elements"]
        assert entry["registry"]
        assert entry["child_safety"]
        for element in entry["ivo_elements"]:
            assert element in "ABCDEFGH", (module, element)
        for requirement in entry["registry"]:
            assert requirement in "ABCD", (module, requirement)
        for area in entry["child_safety"]:
            assert area in "ABCDEF", (module, area)


def test_methodology_proposal_names_benchmarks_metrics_methods():
    proposal = build_methodology_proposal()
    assert proposal["statute"] == "SB 813"
    assert any("contract" in b.lower() for b in proposal["benchmarks"])
    assert any("battery" in b.lower() for b in proposal["benchmarks"])
    assert any("pass" in m.lower() for m in proposal["metrics"])
    assert len(proposal["methodologies"]) == 4
    assert proposal["expertise"] is None
    assert proposal["conflicts_procedure"] is None
    assert proposal["independence_evidence"] is None
    assert "2028-01-01" in proposal["note"]


def test_methodology_proposal_carries_corpus_counts():
    proposal = build_methodology_proposal({
        "audit_rows": 2975,
        "check_judgments": 53943,
        "tasks": 25,
        "agents": 12,
        "battery": 13,
    })
    assert "2975" in proposal["corpus_note"]
    assert "53943" in proposal["corpus_note"]
    assert "13-attack" in proposal["benchmarks"][1]


def test_methodology_proposal_rejects_bad_corpus():
    with pytest.raises(TypeError):
        build_methodology_proposal("not a dict")


def test_trustrun_only_proposal_is_block_with_four_gaps():
    scored = score_methodology_proposal(build_methodology_proposal())
    assert scored["verdict"] == "BLOCK"
    assert scored["gaps"] == ["E", "G", "H"]
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["A"]["status"] == "covered"
    assert by_id["B"]["status"] == "covered"
    assert by_id["C"]["status"] == "covered"
    assert by_id["D"]["status"] == "covered"
    assert by_id["F"]["status"] == "partial"
    assert scored["covered"] == 4
    assert scored["partial"] == 1
    assert scored["coverage"] == pytest.approx((4 + 0.5) / 8)
    assert scored["note"] == DISCLAIMER
    assert "not legal advice" in scored["note"]
    assert scored["label"] == "CAIVO methodology"


def test_auditor_record_fills_methodology_gaps():
    proposal = build_methodology_proposal()
    proposal["expertise"] = "Ten years of AI risk assessment."
    proposal["risk_assessment_capability"] = "Published risk method."
    proposal["conflicts_procedure"] = "No financial interest; logged."
    proposal["independence_evidence"] = "No control by any auditee."
    scored = score_methodology_proposal(proposal)
    assert scored["gaps"] == []
    assert scored["verdict"] == "READY"
    assert scored["covered"] == 8
    assert scored["coverage"] == pytest.approx(1.0)


def test_methodology_proposal_missing_benchmarks_is_gap():
    proposal = build_methodology_proposal()
    proposal["benchmarks"] = []
    scored = score_methodology_proposal(proposal)
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["A"]["status"] == "gap"
    assert "A" in scored["gaps"]


def test_methodology_proposal_rejects_bad_input():
    with pytest.raises(TypeError):
        score_methodology_proposal("not a dict")


def test_complete_registration_is_ready():
    scored = score_registry_readiness(_complete_registration())
    assert scored["verdict"] == "READY"
    assert scored["gaps"] == []
    assert scored["covered"] == 4
    assert scored["coverage"] == pytest.approx(1.0)
    assert scored["label"] == "CAIVO registry"


def test_registration_without_independence_is_block():
    registration = _complete_registration()
    registration["independence_bars_met"] = False
    scored = score_registry_readiness(registration)
    assert scored["verdict"] == "BLOCK"
    assert scored["gaps"] == ["B"]


def test_short_retention_is_partial_not_covered():
    registration = _complete_registration()
    registration["retention_years"] = 7
    scored = score_registry_readiness(registration)
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["C"]["status"] == "partial"
    assert scored["verdict"] == "REVIEW"


def test_missing_registration_fields_are_gap():
    scored = score_registry_readiness({})
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["A"]["status"] == "gap"
    assert "business name" in by_id["A"]["evidence"]
    assert by_id["B"]["status"] == "gap"
    assert by_id["C"]["status"] == "gap"
    assert by_id["D"]["status"] == "gap"
    assert scored["verdict"] == "BLOCK"


def test_unsigned_report_template_is_partial():
    registration = _complete_registration()
    registration["report_template"]["signed"] = False
    scored = score_registry_readiness(registration)
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["D"]["status"] == "partial"
    assert scored["verdict"] == "REVIEW"


def test_registry_readiness_rejects_bad_input():
    with pytest.raises(TypeError):
        score_registry_readiness("not a dict")


def test_large_operator_first_audit_due_2029():
    result = child_safety_audit_due({
        "revenue_usd": 800_000_000,
        "first_available": "2027-03-01",
    })
    assert result["audit_required"] is True
    assert result["first_audit_due"] == "2029-01-01"
    assert result["next_audit_due"] == "2029-01-01"
    assert result["exempt_until"] is None


def test_operator_launching_after_2029_due_before_launch():
    result = child_safety_audit_due({
        "revenue_usd": 800_000_000,
        "first_available": "2030-06-15",
    })
    assert result["audit_required"] is True
    assert result["first_audit_due"] == "2030-06-15"
    assert result["next_audit_due"] == "2030-06-15"


def test_biennial_cadence_after_last_audit():
    result = child_safety_audit_due({
        "revenue_usd": 800_000_000,
        "first_available": "2027-03-01",
        "last_audit": "2029-01-01",
    })
    assert result["next_audit_due"] == "2031-01-01"


def test_small_operator_exempt_until_2032():
    result = child_safety_audit_due({
        "revenue_usd": 120_000_000,
        "first_available": "2027-03-01",
    })
    assert result["audit_required"] is False
    assert result["exempt_until"] == "2032-01-01"
    assert result["first_audit_due"] == "2032-01-01"
    assert "July 1, 2027" in result["reason"]


def test_substantial_modification_needs_audit_before_release():
    result = child_safety_audit_due({
        "revenue_usd": 800_000_000,
        "first_available": "2027-03-01",
        "last_audit": "2029-01-01",
        "substantial_modification": True,
        "modification_date": "2030-04-01",
    })
    assert result["audit_required"] is True
    assert result["next_audit_due"] == "2030-04-01"


def test_small_operator_modification_flagged_unsettled():
    result = child_safety_audit_due({
        "revenue_usd": 120_000_000,
        "first_available": "2027-03-01",
        "substantial_modification": True,
        "modification_date": "2030-04-01",
    })
    assert result["audit_required"] is False
    assert "do not settle" in result["reason"]
    assert "counsel" in result["reason"]


def test_child_safety_audit_due_rejects_bad_input():
    with pytest.raises(TypeError):
        child_safety_audit_due("not a dict")
    with pytest.raises(ValueError):
        child_safety_audit_due({
            "revenue_usd": 800_000_000,
            "substantial_modification": True,
        })
    with pytest.raises(ValueError):
        child_safety_audit_due({
            "revenue_usd": 800_000_000,
            "first_available": "not-a-date",
        })


def test_ready_report_alone_is_block_with_two_gaps():
    scored = score_child_safety_report(_ready_report())
    assert scored["verdict"] == "BLOCK"
    assert scored["gaps"] == ["A", "F"]
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["B"]["status"] == "covered"
    assert by_id["C"]["status"] == "covered"
    assert by_id["D"]["status"] == "covered"
    assert by_id["E"]["status"] == "partial"
    assert scored["covered"] == 3
    assert scored["partial"] == 1
    assert scored["coverage"] == pytest.approx((3 + 0.5) / 6)
    assert scored["note"] == DISCLAIMER


def test_blocked_report_areas_follow_module_verdicts():
    scored = score_child_safety_report(_blocked_report())
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["B"]["status"] == "covered"  # contract READY
    assert by_id["C"]["status"] == "partial"  # consistency REVIEW
    assert by_id["D"]["status"] == "gap"  # stress BLOCK
    assert scored["verdict"] == "BLOCK"


def test_auditor_record_fills_child_safety_gaps():
    auditor = {
        "risk_assessment_reviewed": True,
        "lead_auditor": "Lead Auditor",
        "signed": True,
    }
    scored = score_child_safety_report(_ready_report(), auditor=auditor)
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["A"]["status"] == "covered"
    assert by_id["F"]["status"] == "covered"
    assert scored["gaps"] == []
    # Area (E) stays partial by design, so the verdict is REVIEW.
    assert scored["verdict"] == "REVIEW"
    assert scored["coverage"] == pytest.approx((5 + 0.5) / 6)


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
    scored = score_child_safety_report(row)
    assert scored["verdict"] == "BLOCK"
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["D"]["status"] == "partial"


def test_score_child_safety_report_rejects_bad_input():
    with pytest.raises(TypeError):
        score_child_safety_report("not a dict")
    with pytest.raises(ValueError):
        score_child_safety_report(
            {"sections": {"contract": {"verdict": "READY"}}}
        )
    bad = _ready_report()
    bad["sections"]["data"] = {"verdict": "MAYBE"}
    with pytest.raises(ValueError):
        score_child_safety_report(bad)
    with pytest.raises(TypeError):
        score_child_safety_report(_ready_report(), auditor="not a dict")


def test_format_summary_names_verdict_gaps_and_disclaimer():
    text = format_summary(
        score_methodology_proposal(build_methodology_proposal())
    )
    assert "CAIVO methodology readiness: BLOCK" in text
    assert "Gaps: E, G, H" in text
    assert "not legal advice" in text
    for element_id in "ABCDEFGH":
        assert "(%s)" % element_id in text
    child_text = format_summary(score_child_safety_report(_ready_report()))
    assert "CAIVO child safety readiness: BLOCK" in child_text
    assert "Gaps: A, F" in child_text
    registry_text = format_summary(
        score_registry_readiness(_complete_registration())
    )
    assert "CAIVO registry readiness: READY" in registry_text


def test_real_run_audit_report_scores():
    def stub_agent(task_text):
        return {"result": "42"}

    report = run_audit(
        stub_agent,
        {"text": "What is 6 times 7?", "expect": "42"},
        seed=0,
        k=2,
    )
    scored = score_child_safety_report(report)
    assert scored["verdict"] == "BLOCK"
    assert scored["gaps"] == ["A", "F"]
    by_id = {c["id"]: c for c in scored["contents"]}
    assert by_id["B"]["status"] in ("covered", "partial", "gap")
    proposal = score_methodology_proposal(build_methodology_proposal())
    assert proposal["verdict"] == "BLOCK"
    assert proposal["gaps"] == ["E", "G", "H"]
