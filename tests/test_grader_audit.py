"""Tests for TRUSTRUN-GraderAudit: the verdict-extraction audit."""

import pytest

from trustrun.grader_audit import (
    RULES,
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_REVIEW,
    audit_extraction,
    extract,
    format_summary,
    score_campaign,
    score_card,
)

MIXED = (
    "PASS at first glance, but on reflection the claim "
    "does not hold. FAIL"
)


def _record(output, truth):
    return {"output": output, "truth": truth}


MAIN = [
    _record("PASS", "pass"),
    _record("FAIL", "fail"),
    _record("UNVERIFIED", "unverified"),
    _record('{"verdict": "PASS"}', "pass"),
    _record("The claim holds. PASS", "pass"),
    _record("I think this fails. The answer is FAIL", "fail"),
    _record(MIXED, "fail"),
    _record("The object is a nail.", "unverified"),
    _record("The answer is no, the claim fails.", "fail"),
    _record("", "unverified"),
]

CLEAN = [
    _record("PASS", "pass"),
    _record("FAIL", "fail"),
    _record("UNVERIFIED", "unverified"),
    _record('{"verdict": "PASS"}', "pass"),
    _record("pass", "pass"),
    _record("FAIL", "fail"),
    _record("UNVERIFIED", "unverified"),
    _record('{"verdict": "PASS"}', "pass"),
]

REVIEW_RECORDS = (
    [_record("PASS", "pass")] * 5
    + [_record("FAIL", "fail")] * 5
    + [_record("UNVERIFIED", "unverified")] * 5
    + [_record('{"verdict": "PASS"}', "pass")] * 4
    + [_record("Not sure.", "unverified")]
)

RAMBLES = [
    _record("The object is a nail.", "unverified"),
    _record("The answer is no, the claim fails.", "fail"),
    _record("The claim holds, mostly.", "pass"),
    _record("Not sure.", "unverified"),
    _record("It works.", "pass"),
]


# --- strict extraction ---

def test_strict_clean_tokens():
    assert extract("PASS", "strict") == "pass"
    assert extract("FAIL", "strict") == "fail"
    assert extract("UNVERIFIED", "strict") == "unverified"


def test_strict_lowercase_and_whitespace():
    assert extract("pass", "strict") == "pass"
    assert extract("  FAIL\n", "strict") == "fail"


def test_strict_json_verdict():
    assert extract('{"verdict": "PASS"}', "strict") == "pass"
    assert extract('{"verdict": "fail", "note": "x"}', "strict") == "fail"


def test_strict_ramble_is_non_compliant():
    assert extract("The claim holds. PASS", "strict") is None
    assert extract("The object is a nail.", "strict") is None


def test_strict_words_answer_is_non_compliant():
    assert extract("The answer is no, the claim fails.", "strict") is None


def test_strict_empty_and_bad_json():
    assert extract("", "strict") is None
    assert extract('{"verdict": "maybe"}', "strict") is None
    assert extract("not json", "strict") is None


# --- first / last match ---

def test_first_match_takes_earliest_token():
    assert extract(MIXED, "first_match") == "pass"
    assert extract("The claim holds. PASS", "first_match") == "pass"


def test_last_match_takes_latest_token():
    assert extract(MIXED, "last_match") == "fail"
    assert extract(
        "I think this fails. The answer is FAIL", "last_match"
    ) == "fail"


def test_first_last_single_token():
    assert extract("FAIL", "first_match") == "fail"
    assert extract("FAIL", "last_match") == "fail"


def test_first_last_no_token_is_non_compliant():
    assert extract("The object is a nail.", "first_match") is None
    assert extract("The object is a nail.", "last_match") is None
    assert extract("", "first_match") is None


def test_first_last_word_boundary():
    # "bypass" contains "pass" but no word-boundary token.
    assert extract("bypass the check", "first_match") is None
    assert extract("bypass the check", "last_match") is None
    # "fails" is not the FAIL token either.
    assert extract("the claim fails", "first_match") is None


def test_first_last_case_insensitive():
    assert extract("pass", "first_match") == "pass"
    assert extract("Fail", "last_match") == "fail"


# --- snap ---

def test_snap_always_manufactures_a_verdict():
    assert extract("The object is a nail.", "snap") == "fail"
    assert extract("", "snap") == "unverified"
    assert extract('{"verdict": "maybe"}', "snap") == "unverified"


def test_snap_is_case_normalized_but_breaks_on_json():
    # Lowercase "pass" reads as PASS: the rule differs from
    # first/last match only in its fallback, not in case handling.
    assert extract("pass", "snap") == "pass"
    # But the whole-string comparison breaks on a lowercase JSON
    # verdict: the wrapper text dominates and the manufactured
    # verdict is UNVERIFIED for a FAIL answer. That is the
    # paper's snap artifact, not a parsing success.
    assert extract('{"verdict": "fail"}', "snap") == "unverified"


def test_snap_clean_tokens():
    assert extract("PASS", "snap") == "pass"
    assert extract("FAIL", "snap") == "fail"


def test_snap_mixed_trace_keeps_first_token_side():
    # difflib picks PASS for the mixed trace: the manufactured
    # verdict follows lexical closeness, not the considered answer.
    assert extract(MIXED, "snap") == "pass"


# --- extract validation ---

def test_extract_bad_rule():
    with pytest.raises(ValueError):
        extract("PASS", "random")


def test_extract_non_string():
    with pytest.raises(ValueError):
        extract(None, "strict")


# --- audit ---

def test_audit_main_fixture_numbers():
    audit = audit_extraction(MAIN)
    assert audit["n"] == 10
    strict = audit["rules"]["strict"]
    assert strict["accuracy"] == pytest.approx(0.4)
    assert strict["non_compliance_rate"] == pytest.approx(0.6)
    assert strict["compliant_accuracy"] == pytest.approx(1.0)
    first = audit["rules"]["first_match"]
    assert first["accuracy"] == pytest.approx(0.6)
    assert first["non_compliance_rate"] == pytest.approx(0.3)
    assert first["compliant_accuracy"] == pytest.approx(6 / 7)
    last = audit["rules"]["last_match"]
    assert last["accuracy"] == pytest.approx(0.7)
    assert last["non_compliance_rate"] == pytest.approx(0.3)
    assert last["compliant_accuracy"] == pytest.approx(1.0)
    snap = audit["rules"]["snap"]
    assert snap["accuracy"] == pytest.approx(0.6)
    assert snap["non_compliance_rate"] == pytest.approx(0.0)
    assert audit["swing_pp"] == pytest.approx(30.0)
    assert audit["max_non_compliance_rate"] == pytest.approx(0.6)
    assert audit["min_accuracy"] == pytest.approx(0.4)


def test_audit_two_rules_reports_the_paper_recommendation():
    audit = audit_extraction(MAIN, rules=("strict", "first_match"))
    assert set(audit["rules"]) == {"strict", "first_match"}
    assert audit["swing_pp"] == pytest.approx(20.0)


def test_audit_empty_records():
    audit = audit_extraction([])
    assert audit["n"] == 0
    assert audit["swing_pp"] is None
    assert audit["max_non_compliance_rate"] is None
    assert audit["min_accuracy"] is None
    for row in audit["rules"].values():
        assert row["accuracy"] is None
        assert row["non_compliance_rate"] is None


def test_audit_single_rule_swing_zero():
    audit = audit_extraction(MAIN, rules=("strict",))
    assert audit["swing_pp"] == pytest.approx(0.0)


def test_audit_bad_record():
    with pytest.raises(ValueError):
        audit_extraction([{"output": "PASS"}])
    with pytest.raises(ValueError):
        audit_extraction([{"output": "PASS", "truth": "maybe"}])
    with pytest.raises(ValueError):
        audit_extraction([{"output": 1, "truth": "pass"}])


def test_audit_bad_rule():
    with pytest.raises(ValueError):
        audit_extraction(MAIN, rules=("strict", "random"))


# --- campaign verdicts ---

def test_campaign_main_blocks_on_swing():
    campaign = score_campaign(MAIN)
    assert campaign["verdict"] == VERDICT_BLOCK
    assert campaign["swing_pp"] == pytest.approx(30.0)


def test_campaign_clean_passes():
    campaign = score_campaign(CLEAN)
    assert campaign["verdict"] == VERDICT_PASS
    assert campaign["swing_pp"] == pytest.approx(0.0)
    assert campaign["max_non_compliance_rate"] == pytest.approx(0.0)
    assert campaign["min_accuracy"] == pytest.approx(1.0)


def test_campaign_review_on_small_swing():
    campaign = score_campaign(REVIEW_RECORDS)
    assert campaign["n"] == 20
    assert campaign["verdict"] == VERDICT_REVIEW
    assert campaign["swing_pp"] == pytest.approx(5.0)
    assert campaign["max_non_compliance_rate"] == pytest.approx(0.05)
    assert campaign["min_accuracy"] == pytest.approx(0.95)


def test_campaign_rambles_block_on_non_compliance():
    campaign = score_campaign(RAMBLES)
    assert campaign["verdict"] == VERDICT_BLOCK
    assert campaign["max_non_compliance_rate"] == pytest.approx(1.0)


def test_campaign_empty_is_review():
    campaign = score_campaign([])
    assert campaign["verdict"] == VERDICT_REVIEW
    assert campaign["n"] == 0


# --- score card ---

def test_score_card_carries_non_compliance_alongside_score():
    campaign = score_campaign(MAIN)
    card = score_card(0.85, campaign, rule="strict")
    assert card["judge_score"] == 0.85
    assert card["extraction_rule"] == "strict"
    assert card["non_compliance_rate"] == pytest.approx(0.6)
    assert card["extraction_accuracy"] == pytest.approx(0.4)
    assert card["swing_pp"] == pytest.approx(30.0)
    assert card["verdict"] == VERDICT_BLOCK


def test_score_card_defaults_to_strict():
    campaign = score_campaign(CLEAN)
    card = score_card(1.0, campaign)
    assert card["extraction_rule"] == "strict"
    assert card["non_compliance_rate"] == pytest.approx(0.0)


def test_score_card_bad_inputs():
    campaign = score_campaign(CLEAN)
    strict_only = score_campaign(CLEAN, rules=("strict",))
    with pytest.raises(ValueError):
        score_card(1.5, campaign)
    with pytest.raises(ValueError):
        score_card(0.5, campaign, rule="random")
    with pytest.raises(ValueError):
        # first_match was not audited under a strict-only campaign
        score_card(0.5, strict_only, rule="first_match")
    with pytest.raises(ValueError):
        score_card(0.5, {"n": 0})


# --- summary ---

def test_format_summary_main():
    campaign = score_campaign(MAIN)
    assert format_summary(campaign) == (
        "GraderAudit: 10 outputs, strict 0.4000 (non-compliance 0.6000), "
        "first_match 0.6000 (non-compliance 0.3000), "
        "last_match 0.7000 (non-compliance 0.3000), "
        "snap 0.6000 (non-compliance 0.0000), "
        "swing 30.00pp, verdict BLOCK"
    )


def test_format_summary_empty():
    campaign = score_campaign([])
    assert format_summary(campaign) == (
        "GraderAudit: 0 outputs, strict n/a (non-compliance n/a), "
        "first_match n/a (non-compliance n/a), "
        "last_match n/a (non-compliance n/a), "
        "snap n/a (non-compliance n/a), "
        "swing n/a, verdict REVIEW"
    )


def test_rules_cover_all_four():
    assert RULES == ("strict", "first_match", "last_match", "snap")
