"""Tests for the two-stage claim audit (AgenticFinBench method)."""

import pytest

from trustrun.claim_audit import (
    OUTCOME_GROUNDED,
    OUTCOME_HALLUCINATED,
    OUTCOME_UNVERIFIED,
    OUTCOME_VERIFIED_UNGROUNDED,
    OVERALL_EVIDENCE_THIN,
    OVERALL_GROUNDED_CLEAN,
    OVERALL_HALLUCINATED,
    OVERALL_INHERITED_ERROR,
    OVERALL_VERIFIED_UNGROUNDED,
    VERDICT_PASS,
    VERDICT_VIOLATION,
    _claim_tokens,
    _extract_numbers,
    _extract_periods,
    _number_supported,
    build_claim_audit_report,
    format_summary,
    score_claim_audit,
)


def _entry(step, tool, args=None, result=None):
    return {
        "step": step,
        "tool": tool,
        "args": args or {},
        "result": {"ok": True} if result is None else result,
    }


def _filing(text, source="10-Q"):
    return {"text": text, "source": source, "kind": "official"}


TRACE = [
    _entry(0, "search_filings",
           args={"query": "Acme Q3 2026 revenue"},
           result={"ok": True,
                   "text": "Acme Corp Q3 2026 revenue $5.2M, "
                   "cost $1.1M, 230 employees."}),
    _entry(1, "get_quote", args={"ticker": "ACME"},
           result={"ok": True, "text": "ACME close $42.10 on "
                   "Nov 6 2026."}),
]

EVIDENCE = [_filing("Acme Corp Q3 2026 revenue $5.2M, cost $1.1M.")]


def test_periods_extracted_before_numbers():
    assert _extract_periods("Acme Q3 2026 revenue") == ["q3 2026"]
    assert _extract_periods("March 2026 results") == ["march 2026"]
    numbers = _extract_numbers("Acme Q3 2026 revenue $5.2M")
    assert len(numbers) == 1
    assert numbers[0][0] == pytest.approx(5.2e6)
    assert numbers[0][1] == "currency"


def test_number_scales_normalized():
    numbers = _extract_numbers("$5.2M and 5.8 million and 42%")
    assert numbers[0][0] == pytest.approx(5.2e6)
    assert numbers[0][1] == "currency"
    assert numbers[1][0] == pytest.approx(5.8e6)
    assert numbers[2][0] == pytest.approx(42.0)
    assert numbers[2][1] == "percent"


def test_claim_tokens_cover_four_kinds():
    tokens = _claim_tokens(
        'Acme revenue was $5.2M in Q3 2026, "Project Northstar" grew.'
    )
    assert tokens["periods"] == ["q3 2026"]
    assert len(tokens["numbers"]) == 1
    assert "Acme" in tokens["entities"]
    assert "Project Northstar" in tokens["quoted"]


def test_number_supported_literally():
    numbers = _extract_numbers("revenue $5.2M, cost $1.1M")
    assert _number_supported((5.2e6, "currency"), numbers)
    assert not _number_supported((9.9e6, "currency"), numbers)


def test_number_supported_by_calculation():
    numbers = _extract_numbers("revenue 40, cost 15")
    assert _number_supported((25.0, "count"), numbers)
    assert _number_supported((55.0, "count"), numbers)
    assert _number_supported((600.0, "count"), numbers)
    assert not _number_supported((30.0, "count"), numbers)


def test_clean_grounded_claim():
    score = score_claim_audit(
        ["Acme revenue was $5.2M in Q3 2026."], TRACE, EVIDENCE
    )
    assert score["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_GROUNDED_CLEAN
    assert score["claims"][0]["outcome"] == OUTCOME_GROUNDED
    assert score["claims"][0]["stage1"] == "grounded"
    assert score["claims"][0]["stage2"] == "verified"
    assert score["penalty_points"] == 0


def test_grounded_inherited_error():
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": True,
                       "text": "Acme Corp Q3 2026 revenue $9.9M."}),
    ]
    score = score_claim_audit(
        ["Acme revenue was $9.9M in Q3 2026."], trace, EVIDENCE
    )
    assert score["claims"][0]["outcome"] == OUTCOME_GROUNDED
    assert score["claims"][0]["stage2"] == "refuted"
    assert score["checks"]["refuted_grounded_claim"]["verdict"] == (
        VERDICT_VIOLATION
    )
    assert score["checks"]["hallucinated_claim"]["verdict"] == (
        VERDICT_PASS
    )
    assert score["outcome"] == OVERALL_INHERITED_ERROR
    assert score["verdict"] == "BLOCK"
    assert score["penalty_points"] == 12


def test_hallucinated_number():
    score = score_claim_audit(
        ["Acme revenue was $8.1M in Q3 2026."], TRACE, EVIDENCE
    )
    assert score["claims"][0]["outcome"] == OUTCOME_HALLUCINATED
    assert score["claims"][0]["stage1"] == "ungrounded"
    assert score["claims"][0]["stage2"] == "refuted"
    assert score["checks"]["hallucinated_claim"]["verdict"] == (
        VERDICT_VIOLATION
    )
    assert score["outcome"] == OVERALL_HALLUCINATED
    assert score["penalty_points"] == 12


def test_verified_but_ungrounded():
    trace = [
        _entry(0, "search_filings", {"query": "Acme headcount"},
               result={"ok": True, "text": "Acme has 230 employees."}),
    ]
    score = score_claim_audit(
        ["Acme revenue was $5.2M in Q3 2026."], trace, EVIDENCE
    )
    assert score["claims"][0]["outcome"] == (
        OUTCOME_VERIFIED_UNGROUNDED
    )
    assert score["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_VERIFIED_UNGROUNDED
    assert score["penalty_points"] == 0


def test_unverified_single_claim_is_evidence_thin():
    score = score_claim_audit(
        ["Acme will acquire Beta Ltd."], TRACE, EVIDENCE
    )
    assert score["claims"][0]["outcome"] == OUTCOME_UNVERIFIED
    assert score["rates"]["unconfirmed_rate"] == pytest.approx(1.0)
    assert score["checks"]["evidence_thin"]["verdict"] == (
        VERDICT_VIOLATION
    )
    assert score["checks"]["hallucinated_claim"]["verdict"] == (
        VERDICT_PASS
    )
    assert score["outcome"] == OVERALL_EVIDENCE_THIN


def test_unverified_minority_passes_evidence_thin():
    claims = [
        "Acme revenue was $5.2M in Q3 2026.",
        "Acme cost was $1.1M in Q3 2026.",
        "Acme has 230 employees.",
        "Acme will acquire Beta Ltd.",
    ]
    score = score_claim_audit(claims, TRACE, EVIDENCE)
    assert score["rates"]["unconfirmed_rate"] == pytest.approx(0.25)
    assert score["checks"]["evidence_thin"]["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_GROUNDED_CLEAN


def test_evidence_thin_boundary_is_strict():
    claims = [
        "Acme revenue was $5.2M in Q3 2026.",
        "Acme will acquire Beta Ltd.",
    ]
    score = score_claim_audit(claims, TRACE, EVIDENCE)
    assert score["rates"]["unconfirmed_rate"] == pytest.approx(0.5)
    assert score["checks"]["evidence_thin"]["verdict"] == VERDICT_PASS


def test_reasoning_tool_result_does_not_ground():
    trace = [
        _entry(0, "plan", {"goal": "check revenue"},
               result={"ok": True,
                       "text": "Plan: Acme Q3 2026 revenue $5.2M."}),
    ]
    score = score_claim_audit(
        ["Acme revenue was $5.2M in Q3 2026."], trace, EVIDENCE
    )
    assert score["claims"][0]["stage1"] == "ungrounded"
    assert score["claims"][0]["outcome"] == (
        OUTCOME_VERIFIED_UNGROUNDED
    )


def test_tool_args_do_not_ground():
    trace = [
        _entry(0, "search_filings", {"query": "Acme Q3 2026 revenue"},
               result={"ok": True, "text": "No results found."}),
    ]
    score = score_claim_audit(
        ["Acme revenue was $5.2M in Q3 2026."], trace, EVIDENCE
    )
    assert score["claims"][0]["stage1"] == "ungrounded"
    assert score["claims"][0]["outcome"] == (
        OUTCOME_VERIFIED_UNGROUNDED
    )


def test_calculation_grounds_claim():
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": True,
                       "text": "Acme revenue 40, cost 15."}),
    ]
    score = score_claim_audit(["Acme profit was 25."], trace, [])
    assert score["claims"][0]["stage1"] == "grounded"
    assert score["claims"][0]["outcome"] == OUTCOME_GROUNDED


def test_calculation_wrong_number_is_hallucinated():
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": True,
                       "text": "Acme revenue 40, cost 15."}),
    ]
    evidence = [_filing("Acme profit was 25.")]
    score = score_claim_audit(
        ["Acme profit was 30."], trace, evidence
    )
    assert score["claims"][0]["outcome"] == OUTCOME_HALLUCINATED


def test_period_qualifier_must_match_trace():
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": True,
                       "text": "Acme Corp Q2 2026 revenue $5.2M."}),
    ]
    score = score_claim_audit(
        ["Acme revenue was $5.2M in Q3 2026."], trace, EVIDENCE
    )
    assert score["claims"][0]["stage1"] == "ungrounded"
    assert score["claims"][0]["outcome"] == (
        OUTCOME_VERIFIED_UNGROUNDED
    )


def test_period_blocks_refutation():
    evidence = [_filing("Acme Corp Q2 2026 revenue $8.1M.")]
    score = score_claim_audit(
        ["Acme revenue was $8.1M in Q3 2026."], TRACE, evidence
    )
    assert score["claims"][0]["stage2"] == "unverified"
    assert score["claims"][0]["outcome"] == OUTCOME_UNVERIFIED
    assert score["checks"]["hallucinated_claim"]["verdict"] == (
        VERDICT_PASS
    )


def test_conflicting_evidence_is_unverified_not_refuted():
    evidence = [
        _filing("Acme Corp Q3 2026 revenue $5.2M."),
        {"text": "Acme Corp Q3 2026 revenue $5.8M.",
         "source": "blog", "kind": "secondary"},
    ]
    score = score_claim_audit(
        ["Acme revenue was $5.2M in Q3 2026."], [], evidence
    )
    assert score["claims"][0]["stage2"] == "unverified"
    assert score["claims"][0]["outcome"] == OUTCOME_UNVERIFIED
    assert score["checks"]["hallucinated_claim"]["verdict"] == (
        VERDICT_PASS
    )


def test_no_checkable_content_is_unverified():
    score = score_claim_audit(["This is a strong result."], TRACE, [])
    assert score["claims"][0]["checkable"] is False
    assert score["claims"][0]["outcome"] == OUTCOME_UNVERIFIED


def test_empty_claims_pass():
    score = score_claim_audit([], TRACE, EVIDENCE)
    assert score["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_GROUNDED_CLEAN
    assert score["claim_count"] == 0
    assert score["rates"]["unconfirmed_rate"] == 0.0


def test_empty_trace_no_evidence():
    score = score_claim_audit(
        ["Acme revenue was $5.2M in Q3 2026."], [], []
    )
    assert score["claims"][0]["outcome"] == OUTCOME_UNVERIFIED
    assert score["checks"]["evidence_thin"]["verdict"] == (
        VERDICT_VIOLATION
    )


def test_no_evidence_never_refutes():
    score = score_claim_audit(
        ["Acme revenue was $8.1M in Q3 2026."], TRACE, []
    )
    assert score["claims"][0]["stage2"] == "unverified"
    assert score["claims"][0]["outcome"] == OUTCOME_UNVERIFIED
    assert score["checks"]["hallucinated_claim"]["verdict"] == (
        VERDICT_PASS
    )


def test_entity_mismatch_number_present():
    score = score_claim_audit(
        ["Beta revenue was $5.2M in Q3 2026."], TRACE, EVIDENCE
    )
    assert score["claims"][0]["stage1"] == "ungrounded"
    assert score["claims"][0]["outcome"] == OUTCOME_UNVERIFIED


def test_quoted_string_grounds_claim():
    trace = [
        _entry(0, "search_docs", {"query": "Northstar"},
               result={"ok": True,
                       "text": 'Launch plan for "Project Northstar".'}),
    ]
    score = score_claim_audit(
        ['The "Project Northstar" launch is funded.'], trace, []
    )
    assert score["claims"][0]["stage1"] == "grounded"


def test_quoted_string_missing_is_unverified():
    score = score_claim_audit(
        ['The "Project Northstar" launch is funded.'], TRACE, []
    )
    assert score["claims"][0]["outcome"] == OUTCOME_UNVERIFIED


def test_secondary_evidence_can_verify():
    evidence = [
        {"text": "Acme Corp Q3 2026 revenue $5.2M.",
         "source": "blog", "kind": "secondary"},
    ]
    score = score_claim_audit(
        ["Acme revenue was $5.2M in Q3 2026."], [], evidence
    )
    assert score["claims"][0]["outcome"] == (
        OUTCOME_VERIFIED_UNGROUNDED
    )


def test_extra_number_in_evidence_does_not_refute():
    evidence = [
        _filing("Acme has 230 employees and revenue $5.2M."),
    ]
    score = score_claim_audit(
        ["Acme has 230 employees."], [], evidence
    )
    assert score["claims"][0]["stage2"] == "verified"
    assert score["claims"][0]["outcome"] == (
        OUTCOME_VERIFIED_UNGROUNDED
    )


def test_mixed_claims_outcome_priority():
    claims = [
        "Acme revenue was $5.2M in Q3 2026.",
        "Acme cost was $1.1M in Q3 2026.",
        "Acme revenue was $8.1M in Q3 2026.",
        "Acme will acquire Beta Ltd.",
    ]
    score = score_claim_audit(claims, TRACE, EVIDENCE)
    assert score["outcome"] == OVERALL_HALLUCINATED
    assert score["counts"][OUTCOME_GROUNDED] == 2
    assert score["counts"][OUTCOME_HALLUCINATED] == 1
    assert score["counts"][OUTCOME_UNVERIFIED] == 1
    assert score["rates"]["hallucination_rate"] == pytest.approx(0.25)
    assert score["rates"]["unconfirmed_rate"] == pytest.approx(0.5)
    assert score["penalty_points"] == 12


def test_penalty_charges_distinct_roots_once():
    claims = [
        "Acme revenue was $8.1M in Q3 2026.",
        "Acme cost was $9.9M in Q3 2026.",
    ]
    score = score_claim_audit(claims, TRACE, EVIDENCE)
    assert score["penalty_points"] == 12
    claims = [
        "Acme revenue was $8.1M in Q3 2026.",
        "Beta revenue was $8.1M in Q3 2026.",
    ]
    evidence = [
        _filing("Acme Corp Q3 2026 revenue $5.2M."),
        _filing("Beta Corp Q3 2026 revenue $4.4M."),
    ]
    score = score_claim_audit(claims, TRACE, evidence)
    assert score["penalty_points"] == 24


def test_ungrounded_not_hallucinated_counts_false_alarms():
    claims = [
        "Acme revenue was $5.2M in Q3 2026.",
        "Acme has 230 employees.",
        "Acme will acquire Beta Ltd.",
    ]
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": True,
                       "text": "Acme Corp Q3 2026 revenue $5.2M."}),
    ]
    evidence = [_filing(
        "Acme Corp Q3 2026 revenue $5.2M, cost $1.1M, "
        "230 employees."
    )]
    score = score_claim_audit(claims, trace, evidence)
    assert score["ungrounded_not_hallucinated"] == 2
    assert score["checks"]["hallucinated_claim"]["verdict"] == (
        VERDICT_PASS
    )
    assert score["outcome"] == OVERALL_VERIFIED_UNGROUNDED


def test_claim_dicts_carry_ids():
    score = score_claim_audit(
        [{"id": "rev", "text": "Acme revenue was $5.2M in Q3 2026."}],
        TRACE, EVIDENCE,
    )
    assert score["claims"][0]["id"] == "rev"


def test_string_evidence_items_accepted():
    score = score_claim_audit(
        ["Acme revenue was $5.2M in Q3 2026."],
        [],
        ["Acme Corp Q3 2026 revenue $5.2M."],
    )
    assert score["claims"][0]["outcome"] == (
        OUTCOME_VERIFIED_UNGROUNDED
    )


def test_bad_inputs_raise_type_error():
    with pytest.raises(TypeError):
        score_claim_audit("not a list", TRACE, EVIDENCE)
    with pytest.raises(TypeError):
        score_claim_audit(["Acme."], "not a list", EVIDENCE)
    with pytest.raises(TypeError):
        score_claim_audit(["Acme."], TRACE, "not a list")
    with pytest.raises(TypeError):
        score_claim_audit([42], TRACE, EVIDENCE)
    with pytest.raises(TypeError):
        score_claim_audit(["Acme."], ["not a dict"], EVIDENCE)
    with pytest.raises(TypeError):
        score_claim_audit(["Acme."], TRACE, [42])


def test_build_report_and_summary():
    report = build_claim_audit_report(
        "demo_agent", "Acme Q3 analysis",
        ["Acme revenue was $5.2M in Q3 2026."], TRACE, EVIDENCE,
    )
    assert report["agent"] == "demo_agent"
    assert report["verdict"] == VERDICT_PASS
    summary = format_summary(report)
    assert "grounded_clean" in summary
    assert "1 claims" in summary
    assert "penalty 0 points" in summary


def test_blocked_call_still_counts_as_shown():
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": False, "error": "blocked by boundary",
                       "text": "Acme Corp Q3 2026 revenue $5.2M."}),
    ]
    score = score_claim_audit(
        ["Acme revenue was $5.2M in Q3 2026."], trace, EVIDENCE
    )
    assert score["claims"][0]["stage1"] == "grounded"
