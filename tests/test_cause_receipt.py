"""Tests for TRUSTRUN-CauseReceipt: failure-cause attribution
and the closed-loop retry/switch/escalate router."""

from trustrun.cause_receipt import (
    ABILITY_GAP_BAR,
    CAUSE_BAD_RUN,
    CAUSE_ISSUE_DIFFICULTY,
    CAUSE_MODEL_ABILITY,
    CAUSE_NOT_A_FAILURE,
    CAUSE_UNKNOWN,
    DECISION_ESCALATE,
    DECISION_NONE,
    DECISION_RETRY,
    DECISION_SWITCH,
    DIFFICULTY_BAR,
    attribute_failure,
    format_summary,
    score_campaign,
)


def _run(**overrides):
    run = {
        "id": "t",
        "issue_id": "i1",
        "model_id": "m1",
        "outcome": "failed",
    }
    run.update(overrides)
    return run


def test_bad_run_mixed_repeats():
    result = attribute_failure(_run(
        repeat_outcomes=[False, True], issue_difficulty=0.5))
    assert result["cause"] == CAUSE_BAD_RUN
    assert result["decision"] == DECISION_RETRY


def test_bad_run_single_true_repeat():
    result = attribute_failure(_run(repeat_outcomes=[True]))
    assert result["cause"] == CAUSE_BAD_RUN
    assert result["decision"] == DECISION_RETRY


def test_bad_run_beats_difficulty():
    # Direct observation (a repeat solved it) beats the
    # population statistic, even at difficulty 0.95.
    result = attribute_failure(_run(
        repeat_outcomes=[False, True], issue_difficulty=0.95))
    assert result["cause"] == CAUSE_BAD_RUN
    assert result["decision"] == DECISION_RETRY


def test_issue_difficulty_full():
    result = attribute_failure(_run(
        issue_difficulty=1.0, repeat_outcomes=[False, False],
        model_pass_rate=0.4, best_other_pass_rate=0.5))
    assert result["cause"] == CAUSE_ISSUE_DIFFICULTY
    assert result["decision"] == DECISION_ESCALATE


def test_issue_difficulty_boundary():
    assert attribute_failure(
        _run(issue_difficulty=DIFFICULTY_BAR))["cause"] \
        == CAUSE_ISSUE_DIFFICULTY
    assert attribute_failure(
        _run(issue_difficulty=DIFFICULTY_BAR - 0.01))["cause"] \
        == CAUSE_UNKNOWN


def test_issue_difficulty_beats_ability():
    result = attribute_failure(_run(
        issue_difficulty=0.95, model_pass_rate=0.3,
        best_other_pass_rate=0.8))
    assert result["cause"] == CAUSE_ISSUE_DIFFICULTY
    assert result["decision"] == DECISION_ESCALATE


def test_model_ability_gap():
    result = attribute_failure(_run(
        issue_difficulty=0.4, repeat_outcomes=[False],
        model_pass_rate=0.3, best_other_pass_rate=0.65))
    assert result["cause"] == CAUSE_MODEL_ABILITY
    assert result["decision"] == DECISION_SWITCH


def test_model_ability_boundary():
    assert attribute_failure(_run(
        model_pass_rate=0.5,
        best_other_pass_rate=0.5 + ABILITY_GAP_BAR))["cause"] \
        == CAUSE_MODEL_ABILITY
    assert attribute_failure(_run(
        model_pass_rate=0.5,
        best_other_pass_rate=0.5 + ABILITY_GAP_BAR - 0.01))["cause"] \
        == CAUSE_UNKNOWN


def test_ability_not_difficulty_below_bar():
    result = attribute_failure(_run(
        issue_difficulty=0.89, model_pass_rate=0.4,
        best_other_pass_rate=0.7))
    assert result["cause"] == CAUSE_MODEL_ABILITY
    assert result["decision"] == DECISION_SWITCH


def test_unknown_no_signals():
    result = attribute_failure(_run())
    assert result["cause"] == CAUSE_UNKNOWN
    assert result["decision"] == DECISION_ESCALATE


def test_unknown_small_gap():
    result = attribute_failure(_run(
        issue_difficulty=0.3, repeat_outcomes=[False, False],
        model_pass_rate=0.6, best_other_pass_rate=0.7))
    assert result["cause"] == CAUSE_UNKNOWN


def test_unknown_missing_ability_fields():
    result = attribute_failure(_run(
        issue_difficulty=0.5, repeat_outcomes=[False],
        model_pass_rate=None, best_other_pass_rate=0.9))
    assert result["cause"] == CAUSE_UNKNOWN


def test_unknown_empty_repeats():
    result = attribute_failure(_run(
        issue_difficulty=0.5, repeat_outcomes=[]))
    assert result["cause"] == CAUSE_UNKNOWN


def test_unknown_all_false_repeats_low_difficulty():
    result = attribute_failure(_run(
        issue_difficulty=0.2, repeat_outcomes=[False, False, False]))
    assert result["cause"] == CAUSE_UNKNOWN


def test_passed_run_not_a_failure():
    result = attribute_failure(_run(outcome="passed"))
    assert result["cause"] == CAUSE_NOT_A_FAILURE
    assert result["decision"] == DECISION_NONE


def test_missing_outcome_is_unknown_not_pass():
    result = attribute_failure({"id": "t"})
    assert result["cause"] == CAUSE_UNKNOWN
    assert result["decision"] == DECISION_ESCALATE


def test_non_dict_run_is_unknown():
    result = attribute_failure(None)
    assert result["cause"] == CAUSE_UNKNOWN
    assert result["decision"] == DECISION_ESCALATE


def test_bool_difficulty_is_not_a_number():
    # True is not 1.0 here: booleans are excluded from the
    # numeric checks, so a bool difficulty cannot attribute.
    result = attribute_failure(_run(issue_difficulty=True))
    assert result["cause"] == CAUSE_UNKNOWN


def test_campaign_empty_is_review():
    campaign = score_campaign([])
    assert campaign["failed"] == 0
    assert campaign["verdict"] == "REVIEW"
    assert "no failed runs" in campaign["verdict_evidence"]


def test_campaign_passed_runs_excluded():
    campaign = score_campaign([
        _run(outcome="passed"),
        _run(repeat_outcomes=[True], tokens=100),
    ])
    assert campaign["runs"] == 2
    assert campaign["failed"] == 1
    assert campaign["router"]["recovered"] == 1


def test_campaign_ready_when_all_known_and_router_wins():
    campaign = score_campaign([
        _run(repeat_outcomes=[True], tokens=100),
        _run(issue_difficulty=1.0, repeat_outcomes=[False],
             trajectory_flag=True, tokens=200),
    ])
    assert campaign["attributions"] == {
        CAUSE_BAD_RUN: 1, CAUSE_ISSUE_DIFFICULTY: 1}
    assert campaign["router"]["recovered"] == 1
    assert campaign["router"]["tokens_wasted"] == 0
    # always_retry wastes the 200 on the unsolvable issue;
    # trajectory_flag does the same. The router wastes nothing.
    assert campaign["always_retry"]["tokens_wasted"] == 200
    assert campaign["trajectory_flag"]["tokens_wasted"] == 200
    assert campaign["verdict"] == "READY"


def test_campaign_review_when_unknown_present():
    campaign = score_campaign([
        _run(repeat_outcomes=[True], tokens=100),
        _run(),
    ])
    assert campaign["unknown"] == 1
    assert campaign["verdict"] == "REVIEW"
    assert "unattributed" in campaign["verdict_evidence"]


def test_campaign_review_when_router_wastes_more():
    # A switch that does not recover wastes tokens; with no
    # flags anywhere the trajectory-flag baseline wastes zero,
    # so the router loses on waste.
    campaign = score_campaign([
        _run(model_pass_rate=0.3, best_other_pass_rate=0.7,
             other_model_outcome=False, tokens=500),
    ])
    assert campaign["attributions"] == {CAUSE_MODEL_ABILITY: 1}
    assert campaign["router"]["recovered"] == 0
    assert campaign["router"]["tokens_wasted"] == 500
    assert campaign["trajectory_flag"]["tokens_wasted"] == 0
    assert campaign["verdict"] == "REVIEW"


def test_campaign_switch_recovers_when_other_solves():
    campaign = score_campaign([
        _run(model_pass_rate=0.2, best_other_pass_rate=0.8,
             other_model_outcome=True, tokens=500),
    ])
    assert campaign["router"]["recovered"] == 1
    assert campaign["always_switch"]["recovered"] == 1
    assert campaign["always_retry"]["recovered"] == 0
    assert campaign["verdict"] == "READY"


def test_campaign_flag_baseline_retries_flagged_only():
    campaign = score_campaign([
        _run(issue_difficulty=1.0, trajectory_flag=True, tokens=300),
        _run(issue_difficulty=1.0, trajectory_flag=False, tokens=400),
        _run(issue_difficulty=1.0, tokens=500),
    ])
    assert campaign["trajectory_flag"]["attempts"] == 1
    assert campaign["trajectory_flag"]["tokens_spent"] == 300
    assert campaign["trajectory_flag"]["recovered"] == 0
    assert campaign["always_retry"]["attempts"] == 3


def test_campaign_missing_tokens_cost_zero():
    campaign = score_campaign([
        _run(repeat_outcomes=[True]),
    ])
    assert campaign["router"]["recovered"] == 1
    assert campaign["router"]["tokens_spent"] == 0


def test_campaign_attribution_accuracy_all_labeled():
    campaign = score_campaign([
        _run(repeat_outcomes=[True], expected_cause=CAUSE_BAD_RUN),
        _run(issue_difficulty=1.0, expected_cause=CAUSE_ISSUE_DIFFICULTY),
    ])
    assert campaign["attribution_accuracy"] == 1.0


def test_campaign_attribution_accuracy_partial_is_none():
    campaign = score_campaign([
        _run(repeat_outcomes=[True], expected_cause=CAUSE_BAD_RUN),
        _run(issue_difficulty=1.0),
    ])
    assert campaign["attribution_accuracy"] is None


def test_campaign_attribution_accuracy_counts_misses():
    campaign = score_campaign([
        _run(repeat_outcomes=[True], expected_cause=CAUSE_UNKNOWN),
        _run(issue_difficulty=1.0, expected_cause=CAUSE_ISSUE_DIFFICULTY),
    ])
    assert campaign["attribution_accuracy"] == 0.5


def test_format_summary_names_verdict_and_numbers():
    campaign = score_campaign([
        _run(repeat_outcomes=[True], tokens=100,
             expected_cause=CAUSE_BAD_RUN),
    ])
    summary = format_summary(campaign)
    assert "READY" in summary
    assert "1/1" in summary
    assert "1.00" in summary
