"""Tests for the task-turnover (preservation) scorer.

All deterministic, fixed snapshot pairs. Each check is tested
in its verdicts (pass and violation), plus the false positive
guards (a flat headline with churn is still masking, a cost rise
with flat reliability is not a costly gain, a missing cost dict
leaves the cost check unevaluated) and the signal arithmetic
(rates, net turnover, turnover rate, cost deltas).
"""

import pytest

from trustrun.preservation_aware import (
    CHECK_IDS,
    CHECKS,
    CLASS_GAINED,
    CLASS_PRESERVED,
    CLASS_REGRESSED,
    CLASS_STILL_FAILED,
    OVERALL_CLEAN_IMPROVEMENT,
    OVERALL_COSTLY_GAIN,
    OVERALL_MASKED_IMPROVEMENT,
    OVERALL_NET_REGRESSION,
    OVERALL_UNCHANGED,
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_VIOLATION,
    build_preservation_aware_report,
    format_summary,
    score_turnover,
)


def _snapshots(n_tasks, baseline_passed, new_passed):
    """Two snapshots over n_tasks tasks named t1..tn. The first
    baseline_passed tasks pass in the baseline, the first
    new_passed tasks pass in the new version, so gains and
    regressions overlap on the shared prefix in a known way."""
    baseline = {}
    new = {}
    for index in range(n_tasks):
        task_id = "t%d" % (index + 1)
        baseline[task_id] = index < baseline_passed
        new[task_id] = index < new_passed
    return baseline, new


def _snapshot_with(baseline_true=(), new_true=(), n_tasks=10):
    """Snapshots where exactly the named tasks pass on each
    side; every other task fails on both sides."""
    baseline = {}
    new = {}
    for index in range(n_tasks):
        task_id = "t%d" % (index + 1)
        baseline[task_id] = task_id in baseline_true
        new[task_id] = task_id in new_true
    return baseline, new


def _costs(n_tasks, per_task):
    return {"t%d" % (index + 1): per_task
            for index in range(n_tasks)}


def test_clean_improvement_no_regressions():
    baseline, new = _snapshots(10, 6, 8)
    score = score_turnover(baseline, new)
    assert score["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_CLEAN_IMPROVEMENT
    assert score["gains"] == 2
    assert score["regressions"] == 0
    assert score["preserved"] == 6
    assert score["still_failed"] == 2
    assert score["net_turnover"] == 2
    assert score["headline_delta"] == pytest.approx(0.2)


def test_paper_shape_rise_with_ten_lost_tasks():
    # The paper's headline case: reliability rises while ten
    # previously covered tasks are lost. 100 tasks, baseline
    # 80 pass, new 85 pass, 10 regressions, 15 gains.
    baseline_true = {"t%d" % i for i in range(1, 81)}
    new_true = (
        {"t%d" % i for i in range(1, 71)}
        | {"t%d" % i for i in range(81, 96)}
    )
    baseline, new = _snapshot_with(
        baseline_true=baseline_true, new_true=new_true,
        n_tasks=100,
    )
    score = score_turnover(baseline, new)
    assert score["verdict"] == VERDICT_BLOCK
    assert score["outcome"] == OVERALL_MASKED_IMPROVEMENT
    assert score["regressions"] == 10
    assert score["gains"] == 15
    assert score["net_turnover"] == 5
    assert score["headline_delta"] == pytest.approx(0.05)
    assert score["checks"]["regression"]["verdict"] == (
        VERDICT_VIOLATION
    )
    assert score["checks"]["headline_masks_regression"][
        "verdict"] == VERDICT_VIOLATION
    assert score["checks"]["net_negative_turnover"][
        "verdict"] == VERDICT_PASS
    assert score["checks"]["headline_masks_regression"][
        "evidence"]["detail"].startswith(
        "headline pass rate moved +0.05")


def test_single_regression_is_net_regression():
    baseline, new = _snapshot_with(
        baseline_true=("t1", "t2", "t3"),
        new_true=("t1", "t2"),
    )
    score = score_turnover(baseline, new)
    assert score["verdict"] == VERDICT_BLOCK
    assert score["outcome"] == OVERALL_NET_REGRESSION
    assert score["regressions"] == 1
    assert score["gains"] == 0
    assert score["net_turnover"] == -1
    assert score["checks"]["regression"]["verdict"] == (
        VERDICT_VIOLATION
    )
    assert score["checks"]["net_negative_turnover"][
        "verdict"] == VERDICT_VIOLATION
    assert score["checks"]["headline_masks_regression"][
        "verdict"] == VERDICT_PASS


def test_flat_headline_with_churn_is_masking():
    # Gains exactly cover the regressions, so the headline
    # says "no change" while three covered tasks were lost.
    baseline, new = _snapshot_with(
        baseline_true=("t1", "t2", "t3", "t4", "t5", "t6"),
        new_true=("t1", "t2", "t3", "t7", "t8", "t9"),
    )
    score = score_turnover(baseline, new)
    assert score["headline_delta"] == pytest.approx(0.0)
    assert score["regressions"] == 3
    assert score["gains"] == 3
    assert score["verdict"] == VERDICT_BLOCK
    assert score["outcome"] == OVERALL_MASKED_IMPROVEMENT
    assert score["checks"]["headline_masks_regression"][
        "verdict"] == VERDICT_VIOLATION
    assert score["checks"]["net_negative_turnover"][
        "verdict"] == VERDICT_PASS


def test_net_negative_more_regressions_than_gains():
    baseline, new = _snapshot_with(
        baseline_true=("t1", "t2", "t3", "t4", "t5", "t6",
                       "t7", "t8"),
        new_true=("t1", "t2", "t9", "t10"),
    )
    score = score_turnover(baseline, new)
    assert score["verdict"] == VERDICT_BLOCK
    assert score["outcome"] == OVERALL_NET_REGRESSION
    assert score["regressions"] == 6
    assert score["gains"] == 2
    assert score["net_turnover"] == -4
    assert score["headline_delta"] == pytest.approx(-0.4)


def test_costly_reliability_gain():
    baseline, new = _snapshots(10, 6, 8)
    score = score_turnover(
        baseline, new,
        baseline_costs=_costs(10, 1.00),
        new_costs=_costs(10, 1.50),
    )
    assert score["verdict"] == VERDICT_BLOCK
    assert score["outcome"] == OVERALL_COSTLY_GAIN
    assert score["checks"]["costly_reliability_gain"][
        "verdict"] == VERDICT_VIOLATION
    assert score["mean_baseline_cost"] == pytest.approx(1.00)
    assert score["mean_new_cost"] == pytest.approx(1.50)
    assert score["cost_delta"] == pytest.approx(0.50)
    assert score["costs_supplied"] is True


def test_clean_gain_cheaper_is_clean_improvement():
    baseline, new = _snapshots(10, 6, 8)
    score = score_turnover(
        baseline, new,
        baseline_costs=_costs(10, 1.50),
        new_costs=_costs(10, 1.00),
    )
    assert score["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_CLEAN_IMPROVEMENT
    assert score["cost_delta"] == pytest.approx(-0.50)


def test_cost_flat_with_gain_is_clean_improvement():
    baseline, new = _snapshots(10, 6, 8)
    score = score_turnover(
        baseline, new,
        baseline_costs=_costs(10, 1.00),
        new_costs=_costs(10, 1.00),
    )
    assert score["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_CLEAN_IMPROVEMENT
    assert score["checks"]["costly_reliability_gain"][
        "verdict"] == VERDICT_PASS


def test_cost_rise_with_flat_reliability_is_not_costly_gain():
    # Identical outcomes, cost up: the cost check needs a
    # reliability rise, so it stays PASS; the signals still
    # carry the cost delta.
    baseline, new = _snapshot_with(
        baseline_true=("t1", "t2", "t3"),
        new_true=("t1", "t2", "t3"),
    )
    score = score_turnover(
        baseline, new,
        baseline_costs=_costs(10, 1.00),
        new_costs=_costs(10, 2.00),
    )
    assert score["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_UNCHANGED
    assert score["checks"]["costly_reliability_gain"][
        "verdict"] == VERDICT_PASS
    assert score["cost_delta"] == pytest.approx(1.00)


def test_no_cost_data_leaves_cost_check_unevaluated():
    baseline, new = _snapshots(10, 6, 8)
    score = score_turnover(baseline, new)
    assert score["costs_supplied"] is False
    assert score["mean_baseline_cost"] is None
    assert score["mean_new_cost"] is None
    assert score["cost_delta"] is None
    assert score["checks"]["costly_reliability_gain"][
        "verdict"] == VERDICT_PASS
    assert "no cost data supplied" in score["checks"][
        "costly_reliability_gain"]["evidence"]["detail"]


def test_one_sided_cost_data_is_an_error():
    baseline, new = _snapshots(10, 6, 8)
    with pytest.raises(ValueError):
        score_turnover(
            baseline, new,
            baseline_costs=_costs(10, 1.00),
        )


def test_unchanged_identical_snapshots():
    baseline, new = _snapshot_with(
        baseline_true=("t1", "t2", "t3"),
        new_true=("t1", "t2", "t3"),
    )
    score = score_turnover(baseline, new)
    assert score["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_UNCHANGED
    assert score["gains"] == 0
    assert score["regressions"] == 0
    assert score["preserved"] == 3
    assert score["still_failed"] == 7
    assert score["turnover_rate"] == pytest.approx(0.0)
    assert score["pass_count"] == 4


def test_unchanged_all_failed():
    baseline, new = _snapshot_with(n_tasks=5)
    score = score_turnover(baseline, new)
    assert score["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_UNCHANGED
    assert score["still_failed"] == 5


def test_all_tasks_regressed():
    baseline, new = _snapshot_with(
        baseline_true=("t%d" % i for i in range(1, 11)),
        new_true=(),
    )
    score = score_turnover(baseline, new)
    assert score["verdict"] == VERDICT_BLOCK
    assert score["outcome"] == OVERALL_NET_REGRESSION
    assert score["regressions"] == 10
    assert score["new_pass_rate"] == pytest.approx(0.0)


def test_all_tasks_gained():
    baseline, new = _snapshot_with(
        baseline_true=(),
        new_true=("t%d" % i for i in range(1, 11)),
    )
    score = score_turnover(baseline, new)
    assert score["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_CLEAN_IMPROVEMENT
    assert score["gains"] == 10
    assert score["headline_delta"] == pytest.approx(1.0)


def test_single_task_gain():
    score = score_turnover({"t1": False}, {"t1": True})
    assert score["outcome"] == OVERALL_CLEAN_IMPROVEMENT
    assert score["verdict"] == VERDICT_PASS


def test_single_task_regression():
    score = score_turnover({"t1": True}, {"t1": False})
    assert score["outcome"] == OVERALL_NET_REGRESSION
    assert score["verdict"] == VERDICT_BLOCK


def test_single_task_unchanged_pass():
    score = score_turnover({"t1": True}, {"t1": True})
    assert score["outcome"] == OVERALL_UNCHANGED
    assert score["verdict"] == VERDICT_PASS


def test_single_task_unchanged_fail():
    score = score_turnover({"t1": False}, {"t1": False})
    assert score["outcome"] == OVERALL_UNCHANGED
    assert score["verdict"] == VERDICT_PASS


def test_masked_beats_costly_in_outcome():
    # Headline up with regressions and cost up: the masked
    # improvement names the outcome, the cost check fires too.
    baseline, new = _snapshot_with(
        baseline_true=("t1", "t2", "t3", "t4", "t5", "t6",
                       "t7", "t8"),
        new_true=("t1", "t2", "t3", "t4", "t5", "t6", "t7",
                  "t9", "t10"),
        n_tasks=10,
    )
    score = score_turnover(
        baseline, new,
        baseline_costs=_costs(10, 1.00),
        new_costs=_costs(10, 1.25),
    )
    assert score["regressions"] == 1
    assert score["gains"] == 2
    assert score["outcome"] == OVERALL_MASKED_IMPROVEMENT
    assert score["checks"]["costly_reliability_gain"][
        "verdict"] == VERDICT_VIOLATION


def test_turnover_rate_counts_changed_tasks():
    baseline, new = _snapshot_with(
        baseline_true=("t1", "t2", "t3", "t4", "t5"),
        new_true=("t1", "t2", "t3", "t6", "t7"),
    )
    score = score_turnover(baseline, new)
    # 2 regressions (t4, t5) + 2 gains (t6, t7) over 10 tasks.
    assert score["turnover_rate"] == pytest.approx(0.4)
    assert score["net_turnover"] == 0


def test_per_task_records_carry_classes():
    baseline, new = _snapshot_with(
        baseline_true=("t1", "t2"),
        new_true=("t2", "t3"),
        n_tasks=4,
    )
    score = score_turnover(baseline, new)
    by_id = {record["id"]: record for record in score["tasks"]}
    assert by_id["t1"]["class"] == CLASS_REGRESSED
    assert by_id["t2"]["class"] == CLASS_PRESERVED
    assert by_id["t3"]["class"] == CLASS_GAINED
    assert by_id["t4"]["class"] == CLASS_STILL_FAILED
    assert [record["id"] for record in score["tasks"]] == [
        "t1", "t2", "t3", "t4",
    ]


def test_regression_evidence_names_lost_tasks():
    baseline, new = _snapshot_with(
        baseline_true=("t2", "t5"),
        new_true=("t2",),
    )
    score = score_turnover(baseline, new)
    evidence = score["checks"]["regression"]["evidence"]
    assert evidence["tasks"] == ["t5"]
    assert "1 of 10 tasks" in evidence["detail"]


def test_mismatched_task_sets_raise():
    with pytest.raises(ValueError):
        score_turnover(
            {"t1": True, "t2": False},
            {"t1": True, "t3": False},
        )


def test_empty_snapshot_raises():
    with pytest.raises(ValueError):
        score_turnover({}, {"t1": True})
    with pytest.raises(ValueError):
        score_turnover({"t1": True}, {})


def test_non_boolean_outcome_raises():
    with pytest.raises(TypeError):
        score_turnover({"t1": 1}, {"t1": True})


def test_bad_snapshot_shape_raises():
    with pytest.raises(TypeError):
        score_turnover([("t1", True)], {"t1": True})
    with pytest.raises(TypeError):
        score_turnover({"t1": True}, "not a dict")


def test_bad_cost_type_raises():
    baseline, new = _snapshots(2, 1, 1)
    with pytest.raises(TypeError):
        score_turnover(
            baseline, new,
            baseline_costs={"t1": "cheap", "t2": 1.0},
            new_costs={"t1": 1.0, "t2": 1.0},
        )


def test_cost_for_unknown_task_raises():
    baseline, new = _snapshots(2, 1, 1)
    with pytest.raises(ValueError):
        score_turnover(
            baseline, new,
            baseline_costs={"t1": 1.0, "t2": 1.0, "t9": 1.0},
            new_costs={"t1": 1.0, "t2": 1.0},
        )


def test_cost_missing_a_task_raises():
    baseline, new = _snapshots(2, 1, 1)
    with pytest.raises(ValueError):
        score_turnover(
            baseline, new,
            baseline_costs={"t1": 1.0},
            new_costs={"t1": 1.0, "t2": 1.0},
        )


def test_report_wrapper_carries_names():
    baseline, new = _snapshots(10, 6, 8)
    report = build_preservation_aware_report(
        "steady", "v1", "v2", baseline, new
    )
    assert report["agent"] == "steady"
    assert report["baseline_version"] == "v1"
    assert report["new_version"] == "v2"
    assert report["outcome"] == OVERALL_CLEAN_IMPROVEMENT
    assert report["verdict"] == VERDICT_PASS
    assert report["gains"] == 2
    assert report["regressions"] == 0


def test_format_summary_clean():
    baseline, new = _snapshots(10, 6, 8)
    report = build_preservation_aware_report(
        "steady", "v1", "v2", baseline, new
    )
    text = format_summary(report)
    assert "clean_improvement" in text
    assert "2 gains, 0 regressions" in text
    assert "no failure recorded" in text


def test_format_summary_blocked():
    baseline, new = _snapshot_with(
        baseline_true=("t1", "t2", "t3"),
        new_true=("t1", "t2"),
    )
    report = build_preservation_aware_report(
        "steady", "v1", "v2", baseline, new
    )
    text = format_summary(report)
    assert "net_regression" in text
    assert "failure: regression (VIOLATION)" in text


def test_checks_table_shape():
    assert len(CHECKS) == 4
    assert CHECK_IDS == tuple(c["id"] for c in CHECKS)
    assert CHECK_IDS == (
        "regression",
        "headline_masks_regression",
        "net_negative_turnover",
        "costly_reliability_gain",
    )
    for check in CHECKS:
        assert check["id"]
        assert check["name"]
        assert "2611.07624" in check["incident"]
