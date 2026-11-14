"""Tests for TRUSTRUN-SilentDrop: SPRT silent-regression detection."""

import math

import pytest

from trustrun.silent_drop import (
    DECISION_INCONCLUSIVE,
    DECISION_NO_REGRESSION,
    DECISION_REGRESSION,
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_REVIEW,
    apm_would_alert,
    detection_delay,
    expected_runs_to_clear,
    expected_runs_to_detect,
    fixed_sample_size,
    format_summary,
    run_sprt,
    score_campaign,
    score_stream,
    sprt_thresholds,
)

P0 = 0.9
P1 = 0.7
B0 = 0.91
B1 = 0.76


def test_thresholds_match_wald_boundaries():
    upper, lower = sprt_thresholds(0.05, 0.10)
    assert upper == pytest.approx(math.log(18), abs=1e-9)
    assert lower == pytest.approx(math.log(0.1 / 0.95), abs=1e-9)


def test_thresholds_tighten_with_smaller_alpha():
    upper_strict, lower_strict = sprt_thresholds(0.01, 0.10)
    upper_loose, lower_loose = sprt_thresholds(0.05, 0.10)
    assert upper_strict > upper_loose
    assert lower_strict < lower_loose


def test_thresholds_reject_bad_error_rates():
    with pytest.raises(ValueError):
        sprt_thresholds(0.0, 0.10)
    with pytest.raises(ValueError):
        sprt_thresholds(0.05, 1.0)


def test_three_failures_cross_upper_boundary():
    result = run_sprt([0, 0, 0], P0, P1)
    assert result["decision"] == DECISION_REGRESSION
    assert result["runs_used"] == 3
    assert result["boundary"] == "upper"
    assert result["final_llr"] == pytest.approx(3 * math.log(3), abs=1e-9)


def test_nine_successes_cross_lower_boundary():
    result = run_sprt([1] * 9, P0, P1)
    assert result["decision"] == DECISION_NO_REGRESSION
    assert result["runs_used"] == 9
    assert result["boundary"] == "lower"


def test_eight_successes_stay_inconclusive():
    result = run_sprt([1] * 8, P0, P1)
    assert result["decision"] == DECISION_INCONCLUSIVE
    assert result["runs_used"] == 8
    assert result["boundary"] is None


def test_test_stops_at_first_crossing_and_ignores_rest():
    result = run_sprt([0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1], P0, P1)
    assert result["decision"] == DECISION_REGRESSION
    assert result["runs_used"] == 3
    assert len(result["trace"]) == 3


def test_mixed_stream_crosses_upper_on_eighth_run():
    result = run_sprt([1, 0, 1, 0, 1, 0, 1, 0], P0, P1)
    assert result["decision"] == DECISION_REGRESSION
    assert result["runs_used"] == 8


def test_aiobs_rates_three_failures_detect():
    result = run_sprt([0, 0, 0], B0, B1)
    assert result["decision"] == DECISION_REGRESSION
    assert result["runs_used"] == 3


def test_aiobs_rates_thirteen_successes_clear():
    result = run_sprt([1] * 13, B0, B1)
    assert result["decision"] == DECISION_NO_REGRESSION
    assert result["runs_used"] == 13


def test_aiobs_rates_twelve_successes_inconclusive():
    result = run_sprt([1] * 12, B0, B1)
    assert result["decision"] == DECISION_INCONCLUSIVE
    assert result["runs_used"] == 12


def test_empty_stream_is_inconclusive():
    result = run_sprt([], P0, P1)
    assert result["decision"] == DECISION_INCONCLUSIVE
    assert result["runs_used"] == 0
    assert result["final_llr"] == 0.0


def test_rejects_degraded_rate_at_or_above_baseline():
    with pytest.raises(ValueError):
        run_sprt([1, 0], 0.9, 0.9)
    with pytest.raises(ValueError):
        run_sprt([1, 0], 0.9, 0.95)


def test_rejects_rates_outside_unit_interval():
    with pytest.raises(ValueError):
        run_sprt([1], 1.0, 0.7)
    with pytest.raises(ValueError):
        run_sprt([1], 0.9, 0.0)


def test_rejects_non_binary_outcomes():
    with pytest.raises(ValueError):
        run_sprt([1, 2, 0], P0, P1)
    with pytest.raises(ValueError):
        run_sprt([1, 0.5], P0, P1)


def test_rejects_non_list_outcomes():
    with pytest.raises(ValueError):
        run_sprt("010", P0, P1)


def test_trace_records_every_step():
    result = run_sprt([1, 0, 1], P0, P1)
    assert len(result["trace"]) == 3
    assert result["trace"][0] == pytest.approx(math.log(P1 / P0), abs=1e-9)
    assert result["trace"][1] == pytest.approx(
        math.log(P1 / P0) + math.log((1 - P1) / (1 - P0)), abs=1e-9
    )


def test_expected_runs_to_detect_090_to_070():
    assert expected_runs_to_detect(P0, P1) == pytest.approx(15.46, abs=0.01)


def test_expected_runs_to_detect_aiobs_rates():
    assert expected_runs_to_detect(B0, B1) == pytest.approx(24.12, abs=0.01)


def test_expected_runs_to_clear_090_to_070():
    assert expected_runs_to_clear(P0, P1) == pytest.approx(14.93, abs=0.01)


def test_expected_runs_fall_as_the_drop_grows():
    assert expected_runs_to_detect(0.9, 0.5) < expected_runs_to_detect(0.9, 0.7)


def test_fixed_sample_size_090_to_070():
    assert fixed_sample_size(P0, P1) == pytest.approx(29.20, abs=0.05)


def test_fixed_sample_size_aiobs_rates():
    assert fixed_sample_size(B0, B1) == pytest.approx(46.06, abs=0.05)


def test_fixed_sample_size_exceeds_sprt_expectation():
    assert fixed_sample_size(P0, P1) > expected_runs_to_detect(P0, P1)


def test_fixed_sample_size_rejects_other_error_rates():
    with pytest.raises(ValueError):
        fixed_sample_size(P0, P1, alpha=0.01, beta=0.10)


def test_detection_delay_scales_with_coverage():
    assert detection_delay(24, 0.01) == pytest.approx(2400.0)
    assert detection_delay(24, 1.0) == pytest.approx(24.0)
    assert detection_delay(24, 0.5) == pytest.approx(48.0)


def test_detection_delay_rejects_bad_coverage():
    with pytest.raises(ValueError):
        detection_delay(24, 0.0)
    with pytest.raises(ValueError):
        detection_delay(24, 1.5)


def test_detection_delay_rejects_negative_runs():
    with pytest.raises(ValueError):
        detection_delay(-1, 0.01)


def test_apm_misses_the_silent_drop_shape():
    # The simulation's shape: latency down 37%, errors flat.
    assert apm_would_alert(-37.0, 0.0) is False


def test_apm_fires_on_latency_rise():
    assert apm_would_alert(15.0, 0.0) is True


def test_apm_fires_on_error_rise():
    assert apm_would_alert(0.0, 2.0) is True


def test_apm_stays_quiet_below_thresholds():
    assert apm_would_alert(5.0, 0.5) is False


def test_score_stream_block_on_regression():
    receipt = score_stream([0, 0, 0], P0, P1)
    assert receipt["verdict"] == VERDICT_BLOCK
    assert receipt["decision"] == DECISION_REGRESSION
    assert receipt["runs_used"] == 3
    assert receipt["detection_delay_runs"] == pytest.approx(300.0)


def test_score_stream_pass_on_no_regression():
    receipt = score_stream([1] * 9, P0, P1)
    assert receipt["verdict"] == VERDICT_PASS
    assert receipt["decision"] == DECISION_NO_REGRESSION
    assert receipt["detection_delay_runs"] == pytest.approx(900.0)


def test_score_stream_review_on_inconclusive():
    receipt = score_stream([1] * 8, P0, P1)
    assert receipt["verdict"] == VERDICT_REVIEW
    assert receipt["decision"] == DECISION_INCONCLUSIVE
    assert receipt["detection_delay_runs"] is None


def test_score_stream_review_on_empty_stream():
    receipt = score_stream([], P0, P1)
    assert receipt["verdict"] == VERDICT_REVIEW
    assert receipt["runs_used"] == 0


def test_score_campaign_worst_verdict_wins():
    campaign = score_campaign(
        [[0, 0, 0], [1] * 9, [1] * 8], P0, P1
    )
    assert campaign["verdict"] == VERDICT_BLOCK
    assert campaign["verdicts"] == {
        VERDICT_BLOCK: 1,
        VERDICT_REVIEW: 1,
        VERDICT_PASS: 1,
    }
    assert campaign["streams"] == 3


def test_score_campaign_mean_runs_covers_decided_only():
    campaign = score_campaign(
        [[0, 0, 0], [1] * 9, [1] * 8], P0, P1
    )
    assert campaign["mean_runs_to_decision"] == pytest.approx(6.0)
    assert campaign["mean_detection_delay_runs"] == pytest.approx(300.0)


def test_score_campaign_all_pass_when_nothing_regresses():
    campaign = score_campaign([[1] * 9, [1] * 9], P0, P1)
    assert campaign["verdict"] == VERDICT_PASS
    assert campaign["mean_detection_delay_runs"] is None


def test_score_campaign_carries_expected_and_fixed_sizes():
    campaign = score_campaign([[0, 0, 0]], P0, P1)
    assert campaign["expected_runs_to_detect"] == pytest.approx(15.46, abs=0.01)
    assert campaign["fixed_sample_size"] == pytest.approx(29.20, abs=0.05)


def test_score_campaign_rejects_non_list():
    with pytest.raises(ValueError):
        score_campaign("not a list", P0, P1)


def test_format_summary_names_counts_and_verdict():
    campaign = score_campaign(
        [[0, 0, 0], [1] * 9, [1] * 8], P0, P1
    )
    text = format_summary(campaign)
    assert "3 streams" in text
    assert "1 BLOCK / 1 REVIEW / 1 PASS" in text
    assert "6.00 runs to decision" in text
    assert "300 production runs" in text
    assert "verdict BLOCK" in text
