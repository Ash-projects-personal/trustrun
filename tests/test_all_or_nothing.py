"""Tests for the all-or-nothing long-horizon build scorer.

All deterministic, fixed product specs and grade sets. Each check
is tested in its verdicts (pass and violation), plus the false
positive guards (a plain low-rate failure is not a masked
failure, a single-feature failure is not an interaction break,
a missing grade is ungraded rather than a pass) and the batch
pass@1 axis.
"""

import pytest

from trustrun.all_or_nothing import (
    CHECK_IDS,
    CHECKS,
    OVERALL_DELIVERED,
    OVERALL_FAILED,
    OVERALL_INTERACTION_BREAK,
    OVERALL_PARTIAL_CREDIT_TRAP,
    OVERALL_UNGRADED,
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_VIOLATION,
    build_all_or_nothing_report,
    format_batch_summary,
    format_summary,
    score_batch,
    score_build,
)


def _product(n_plans, n_features=1, combine_from=None):
    """A product with n_plans plans spread over n_features
    features; plans from index combine_from on combine features."""
    plans = []
    for index in range(n_plans):
        plans.append({
            "id": "p%d" % (index + 1),
            "feature": "f%d" % ((index % n_features) + 1),
            "combines_features": (
                combine_from is not None and index >= combine_from
            ),
        })
    return {"name": "shop", "plans": plans}


def _results(product, failed=(), ungraded=()):
    """All plans pass except the named failed and ungraded ones."""
    results = {}
    for plan in product["plans"]:
        plan_id = plan["id"]
        if plan_id in failed:
            results[plan_id] = False
        elif plan_id in ungraded:
            results[plan_id] = None
        else:
            results[plan_id] = True
    return results


def test_clean_build_delivered():
    product = _product(10, n_features=2)
    score = score_build(product, _results(product))
    assert score["verdict"] == VERDICT_PASS
    assert score["outcome"] == OVERALL_DELIVERED
    assert score["delivered"] is True
    assert score["plan_pass_rate"] == 1.0
    assert score["delivery_gap"] == 0.0
    assert score["plans_passed"] == 10
    assert score["features_delivered"] == 2
    assert score["pass_count"] == 4
    assert score["pass_rate"] == 1.0


def test_vibench_gap_shape_98_percent():
    """The paper's headline shape: 49 of 50 plans pass, yet the
    product is not delivered."""
    product = _product(50, n_features=5)
    score = score_build(product, _results(product, failed=("p50",)))
    assert score["verdict"] == VERDICT_BLOCK
    assert score["outcome"] == OVERALL_PARTIAL_CREDIT_TRAP
    assert score["delivered"] is False
    assert score["plan_pass_rate"] == 0.98
    assert score["delivery_gap"] == 0.98
    assert score["checks"]["not_delivered"]["verdict"] == (
        VERDICT_VIOLATION
    )
    assert score["checks"]["partial_credit_masks_failure"][
        "verdict"
    ] == VERDICT_VIOLATION
    assert score["checks"]["interaction_failure"]["verdict"] == (
        VERDICT_PASS
    )
    assert score["checks"]["ungraded_plan"]["verdict"] == VERDICT_PASS


def test_below_partial_credit_line_is_plain_failure():
    product = _product(10, n_features=2)
    score = score_build(
        product, _results(product, failed=("p9", "p10"))
    )
    assert score["plan_pass_rate"] == 0.8
    assert score["outcome"] == OVERALL_FAILED
    assert score["verdict"] == VERDICT_BLOCK
    assert score["checks"]["partial_credit_masks_failure"][
        "verdict"
    ] == VERDICT_PASS
    assert score["pass_count"] == 3


def test_at_partial_credit_line_masks_failure():
    product = _product(10, n_features=2)
    score = score_build(product, _results(product, failed=("p10",)))
    assert score["plan_pass_rate"] == 0.9
    assert score["outcome"] == OVERALL_PARTIAL_CREDIT_TRAP
    assert score["checks"]["partial_credit_masks_failure"][
        "verdict"
    ] == VERDICT_VIOLATION


def test_interaction_only_failure():
    """All single-feature plans pass; only combination plans
    fail, so the build broke where features interact."""
    product = _product(6, n_features=3, combine_from=4)
    score = score_build(
        product, _results(product, failed=("p5", "p6"))
    )
    assert score["verdict"] == VERDICT_BLOCK
    assert score["outcome"] == OVERALL_INTERACTION_BREAK
    assert score["checks"]["interaction_failure"]["verdict"] == (
        VERDICT_VIOLATION
    )
    assert score["checks"]["partial_credit_masks_failure"][
        "verdict"
    ] == VERDICT_PASS


def test_single_feature_failure_is_not_interaction_break():
    product = _product(6, n_features=3, combine_from=4)
    score = score_build(
        product, _results(product, failed=("p1", "p5"))
    )
    assert score["outcome"] == OVERALL_FAILED
    assert score["checks"]["interaction_failure"]["verdict"] == (
        VERDICT_PASS
    )


def test_ungraded_plan_is_not_a_pass():
    product = _product(5, n_features=1)
    score = score_build(
        product, _results(product, ungraded=("p5",))
    )
    assert score["delivered"] is False
    assert score["plan_pass_rate"] == 0.8
    assert score["plans_ungraded"] == 1
    assert score["outcome"] == OVERALL_UNGRADED
    assert score["checks"]["ungraded_plan"]["verdict"] == (
        VERDICT_VIOLATION
    )


def test_missing_plan_in_results_counts_as_ungraded():
    product = _product(3, n_features=1)
    results = {"p1": True, "p2": True}
    score = score_build(product, results)
    assert score["plans_ungraded"] == 1
    assert score["delivered"] is False
    assert score["outcome"] == OVERALL_UNGRADED


def test_ungraded_plus_high_rate_is_partial_credit_trap():
    """49 passed, 1 ungraded: the delivery claim is unverified
    and the plan rate still masks the failure."""
    product = _product(50, n_features=5)
    score = score_build(
        product, _results(product, ungraded=("p50",))
    )
    assert score["plan_pass_rate"] == 0.98
    assert score["outcome"] == OVERALL_PARTIAL_CREDIT_TRAP
    assert score["checks"]["ungraded_plan"]["verdict"] == (
        VERDICT_VIOLATION
    )
    assert score["checks"]["partial_credit_masks_failure"][
        "verdict"
    ] == VERDICT_VIOLATION


def test_interaction_break_beats_ungraded_in_outcome():
    product = _product(10, n_features=2, combine_from=8)
    score = score_build(
        product,
        _results(product, failed=("p9",), ungraded=("p10",)),
    )
    assert score["plan_pass_rate"] == 0.8
    assert score["outcome"] == OVERALL_INTERACTION_BREAK
    assert score["checks"]["interaction_failure"]["verdict"] == (
        VERDICT_VIOLATION
    )
    assert score["checks"]["ungraded_plan"]["verdict"] == (
        VERDICT_VIOLATION
    )


def test_per_feature_verdicts():
    product = _product(4, n_features=2)
    score = score_build(product, _results(product, failed=("p2",)))
    features = {entry["feature"]: entry for entry in score["features"]}
    # Round-robin assignment: p1 and p3 are f1, p2 and p4 are f2.
    assert features["f1"]["delivered"] is True
    assert features["f1"]["passed"] == 2
    assert features["f2"]["delivered"] is False
    assert features["f2"]["passed"] == 1
    assert score["features_delivered"] == 1


def test_delivery_gap_zero_when_delivered():
    product = _product(4, n_features=1)
    score = score_build(product, _results(product))
    assert score["delivery_gap"] == 0.0


def test_single_plan_product():
    product = _product(1, n_features=1)
    delivered = score_build(product, _results(product))
    assert delivered["delivered"] is True
    failed = score_build(product, _results(product, failed=("p1",)))
    assert failed["delivered"] is False
    assert failed["plan_pass_rate"] == 0.0
    assert failed["delivery_gap"] == 0.0
    assert failed["outcome"] == OVERALL_FAILED


def test_plans_without_feature_key_group_together():
    product = {"name": "tool", "plans": [{"id": "a"}, {"id": "b"}]}
    score = score_build(product, {"a": True, "b": True})
    assert score["feature_count"] == 1
    assert score["features"][0]["feature"] == ""
    assert score["delivered"] is True


def test_empty_product_raises():
    with pytest.raises(ValueError):
        score_build({"name": "empty", "plans": []}, {})


def test_duplicate_plan_id_raises():
    product = {"name": "dup", "plans": [
        {"id": "p1"}, {"id": "p1"},
    ]}
    with pytest.raises(ValueError):
        score_build(product, {"p1": True})


def test_unknown_plan_in_results_raises():
    product = _product(2, n_features=1)
    with pytest.raises(ValueError):
        score_build(product, {"p1": True, "p2": True, "p9": True})


def test_bad_grade_type_raises():
    product = _product(2, n_features=1)
    with pytest.raises(TypeError):
        score_build(product, {"p1": "passed", "p2": True})


def test_bad_product_shape_raises():
    with pytest.raises(TypeError):
        score_build("not a dict", {})
    with pytest.raises(TypeError):
        score_build({"name": "x", "plans": "p1"}, {})
    with pytest.raises(TypeError):
        score_build({"name": "x", "plans": ["p1"]}, {})
    with pytest.raises(TypeError):
        score_build({"name": "x", "plans": [{}]}, {})
    with pytest.raises(TypeError):
        score_build(
            {"name": "x", "plans": [{"id": "p1", "feature": 3}]},
            {"p1": True},
        )
    with pytest.raises(TypeError):
        score_build(
            {"name": "x",
             "plans": [{"id": "p1", "combines_features": "yes"}]},
            {"p1": True},
        )


def test_bad_results_shape_raises():
    product = _product(2, n_features=1)
    with pytest.raises(TypeError):
        score_build(product, ["p1"])


def test_batch_pass_at_1():
    product = _product(4, n_features=1)
    builds = [
        _results(product),
        _results(product),
        _results(product, failed=("p4",)),
        _results(product, failed=("p1", "p2")),
    ]
    batch = score_batch(product, builds)
    assert batch["build_count"] == 4
    assert batch["builds_delivered"] == 2
    assert batch["pass_at_1"] == 0.5
    assert batch["mean_plan_pass_rate"] == pytest.approx(0.8125)
    assert batch["mean_delivery_gap"] == pytest.approx(0.3125)
    assert batch["outcomes"] == [
        OVERALL_DELIVERED,
        OVERALL_DELIVERED,
        OVERALL_FAILED,
        OVERALL_FAILED,
    ]


def test_batch_all_delivered_gap_zero():
    product = _product(4, n_features=1)
    batch = score_batch(product, [_results(product)] * 3)
    assert batch["pass_at_1"] == 1.0
    assert batch["mean_delivery_gap"] == 0.0
    assert batch["mean_plan_pass_rate"] == 1.0


def test_batch_none_delivered():
    product = _product(4, n_features=1)
    batch = score_batch(
        product, [_results(product, failed=("p1",))] * 2
    )
    assert batch["pass_at_1"] == 0.0
    assert batch["mean_plan_pass_rate"] == 0.75
    assert batch["mean_delivery_gap"] == 0.75


def test_batch_empty_raises():
    product = _product(2, n_features=1)
    with pytest.raises(ValueError):
        score_batch(product, [])
    with pytest.raises(TypeError):
        score_batch(product, "not a list")


def test_batch_vibench_shape_three_of_four():
    """Four builds, three delivered: pass@1 0.75 with a mean
    plan rate above it, the gap the paper reports."""
    product = _product(20, n_features=4)
    builds = [
        _results(product),
        _results(product),
        _results(product),
        _results(product, failed=("p20",)),
    ]
    batch = score_batch(product, builds)
    assert batch["pass_at_1"] == 0.75
    assert batch["mean_plan_pass_rate"] == pytest.approx(0.9875)
    assert batch["mean_delivery_gap"] == pytest.approx(0.2375)


def test_report_wrapper_carries_names():
    product = _product(4, n_features=1)
    report = build_all_or_nothing_report(
        "nearly_agent", "shop", product,
        _results(product, failed=("p4",)),
    )
    assert report["agent"] == "nearly_agent"
    assert report["product"] == "shop"
    assert report["outcome"] == OVERALL_FAILED
    assert report["verdict"] == VERDICT_BLOCK
    summary = format_summary(report)
    assert "nearly_agent" in summary
    assert "shop" in summary
    assert "failed" in summary
    assert "BLOCK" in summary


def test_format_summary_delivered():
    product = _product(4, n_features=1)
    report = build_all_or_nothing_report(
        "clean_agent", "shop", product, _results(product)
    )
    summary = format_summary(report)
    assert "delivered" in summary
    assert "PASS" in summary
    assert "no failure recorded" in summary


def test_format_batch_summary():
    product = _product(4, n_features=1)
    batch = score_batch(
        product, [_results(product), _results(product, failed=("p1",))]
    )
    summary = format_batch_summary(batch)
    assert "pass@1 0.50" in summary
    assert "2 builds" in summary


def test_checks_table_shape():
    assert len(CHECKS) == 4
    assert CHECK_IDS == tuple(check["id"] for check in CHECKS)
    assert CHECK_IDS == (
        "not_delivered",
        "partial_credit_masks_failure",
        "interaction_failure",
        "ungraded_plan",
    )
    for check in CHECKS:
        assert check["name"]
        assert "arXiv:2611.05620" in check["incident"]


def test_plan_records_carry_grades():
    product = _product(3, n_features=1)
    score = score_build(
        product, _results(product, failed=("p2",), ungraded=("p3",))
    )
    records = {record["id"]: record for record in score["plans"]}
    assert records["p1"]["grade"] is True
    assert records["p2"]["grade"] is False
    assert records["p3"]["grade"] is None
    assert records["p1"]["passed"] is True
    assert records["p2"]["passed"] is False


def test_not_delivered_evidence_names_failed_plans():
    product = _product(4, n_features=1)
    score = score_build(product, _results(product, failed=("p3",)))
    evidence = score["checks"]["not_delivered"]["evidence"]
    assert evidence["plans"] == ["p3"]
    assert "3 of 4" in evidence["detail"]
