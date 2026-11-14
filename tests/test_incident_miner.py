"""Tests for trustrun.incident_miner."""

import pytest

from trustrun.incident_miner import (
    BASELINE_VIOLATION_RATE,
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_REVIEW,
    format_summary,
    mine_rules,
    rule_fires,
    score_campaign,
    score_rule,
)


def _inc(incident_id, kind, removed, added=None, repo="acme/web",
         metric_before=None, metric_after=None, downtime=None,
         tests_passed=True, stage="final"):
    incident = {
        "incident_id": incident_id,
        "kind": kind,
        "removed": removed,
        "added": added,
        "repo": repo,
        "tests_passed": tests_passed,
        "stage": stage,
    }
    if metric_before is not None:
        incident["metric_before"] = metric_before
    if metric_after is not None:
        incident["metric_after"] = metric_after
    if downtime is not None:
        incident["downtime_minutes"] = downtime
    return incident


def _run(calls, violated, resolved, searched, rules_applied):
    return {
        "calls": calls,
        "violated_policy": violated,
        "resolved": resolved,
        "searched_policies": searched,
        "rules_applied": rules_applied,
    }


INCIDENTS = [
    _inc("INC-001", "api_substitution", "queueAnalyticsEvent",
         "analytics.track", repo="acme/web",
         metric_before=200.0, metric_after=8000.0, downtime=180),
    _inc("INC-002", "api_substitution", "queueAnalyticsEvent",
         "analytics.track", repo="acme/web"),
    _inc("INC-003", "api_substitution", "queueAnalyticsEvent",
         "analytics.track", repo="acme/api"),
    _inc("INC-004", "test_execution", "run_tests_without_coverage",
         "run_tests_with_coverage", repo="acme/web"),
    _inc("INC-005", "test_execution", "run_tests_without_coverage",
         "run_tests_with_coverage", repo="acme/api"),
    _inc("INC-006", "api_substitution", "legacy_send", "queue.send",
         repo="acme/web"),
    _inc("INC-007", "metric_regression", "full_table_scan",
         "indexed_query", repo="acme/db",
         metric_before=50.0, metric_after=400.0),
]


def test_mine_groups_support_three_pattern():
    result = mine_rules(INCIDENTS)
    assert result["incidents"] == 7
    assert result["patterns"] == 4
    assert len(result["rules"]) == 3
    first = result["rules"][0]
    assert first["rule_id"] == "RULE-001"
    assert first["kind"] == "api_substitution"
    assert first["removed"] == "queueAnalyticsEvent"
    assert first["added"] == "analytics.track"
    assert first["support"] == 3
    assert first["repos"] == ["acme/api", "acme/web"]
    assert first["incident_ids"] == ["INC-001", "INC-002", "INC-003"]
    assert first["severe"] is True
    assert first["text"] == (
        "Do not use queueAnalyticsEvent; use analytics.track instead."
    )


def test_mine_orders_by_support_then_kind():
    result = mine_rules(INCIDENTS)
    supports = [rule["support"] for rule in result["rules"]]
    assert supports == [3, 2, 1]
    second = result["rules"][1]
    assert second["rule_id"] == "RULE-002"
    assert second["kind"] == "test_execution"
    assert second["text"] == (
        "Do not run run_tests_without_coverage; "
        "run run_tests_with_coverage instead."
    )
    third = result["rules"][2]
    assert third["kind"] == "metric_regression"
    assert third["severe"] is True
    assert third["text"] == (
        "Do not call full_table_scan on the hot path; "
        "use indexed_query instead."
    )


def test_mine_drops_non_severe_singleton():
    result = mine_rules(INCIDENTS)
    assert len(result["dropped"]) == 1
    dropped = result["dropped"][0]
    assert dropped["removed"] == "legacy_send"
    assert dropped["support"] == 1
    assert "below minimum 2" in dropped["reason"]
    assert "not severe" in dropped["reason"]


def test_mine_severe_singleton_by_metric_ratio():
    incidents = [
        _inc("INC-101", "metric_regression", "nested_loop_join",
             "hash_join", metric_before=10.0, metric_after=45.0),
    ]
    result = mine_rules(incidents)
    assert len(result["rules"]) == 1
    assert result["rules"][0]["severe"] is True
    assert result["dropped"] == []


def test_mine_severe_singleton_by_downtime():
    incidents = [
        _inc("INC-102", "scope_violation", "prod_db_write",
             "staging_db_write", downtime=60),
    ]
    result = mine_rules(incidents)
    assert len(result["rules"]) == 1
    assert result["rules"][0]["severe"] is True


def test_mine_ratio_below_four_is_not_severe():
    incidents = [
        _inc("INC-103", "metric_regression", "slow_query",
             "fast_query", metric_before=100.0, metric_after=399.0),
    ]
    result = mine_rules(incidents)
    assert result["rules"] == []
    assert len(result["dropped"]) == 1


def test_mine_downtime_below_sixty_is_not_severe():
    incidents = [
        _inc("INC-104", "scope_violation", "prod_db_write",
             "staging_db_write", downtime=59),
    ]
    result = mine_rules(incidents)
    assert result["rules"] == []
    assert len(result["dropped"]) == 1


def test_mine_min_support_three_keeps_severe_singleton():
    result = mine_rules(INCIDENTS, min_support=3)
    assert [rule["rule_id"] for rule in result["rules"]] == [
        "RULE-001", "RULE-002",
    ]
    assert result["rules"][1]["kind"] == "metric_regression"
    assert len(result["dropped"]) == 2


def test_mine_empty_incidents():
    result = mine_rules([])
    assert result == {
        "rules": [], "dropped": [], "incidents": 0, "patterns": 0,
    }


def test_mine_rule_text_without_replacement():
    incidents = [
        _inc("INC-105", "other", "rm_rf_tmp", None),
        _inc("INC-106", "other", "rm_rf_tmp", None),
    ]
    result = mine_rules(incidents)
    assert result["rules"][0]["text"] == "Avoid rm_rf_tmp."


def test_mine_rule_text_unknown_kind_with_replacement():
    incidents = [
        _inc("INC-107", "custom_kind", "old_flag", "new_flag"),
        _inc("INC-108", "custom_kind", "old_flag", "new_flag"),
    ]
    result = mine_rules(incidents)
    assert result["rules"][0]["text"] == (
        "Do not use old_flag; use new_flag instead."
    )


def test_mine_rejects_non_list():
    with pytest.raises(ValueError):
        mine_rules({"incident_id": "INC-001"})


def test_mine_rejects_missing_fields():
    with pytest.raises(ValueError):
        mine_rules([{"incident_id": "INC-001", "kind": "other"}])
    with pytest.raises(ValueError):
        mine_rules([{"kind": "other", "removed": "x"}])
    with pytest.raises(ValueError):
        mine_rules([{"incident_id": "INC-001", "removed": "x"}])


def test_mine_rejects_bad_min_support():
    with pytest.raises(ValueError):
        mine_rules([], min_support=0)
    with pytest.raises(ValueError):
        mine_rules([], min_support=True)


def test_mine_bool_metric_is_not_a_ratio():
    incidents = [
        _inc("INC-109", "metric_regression", "flag_on", "flag_off",
             metric_before=True, metric_after=False),
    ]
    result = mine_rules(incidents)
    assert result["rules"] == []


def test_mine_zero_before_metric_is_not_severe():
    incidents = [
        _inc("INC-110", "metric_regression", "cold_start",
             "warm_start", metric_before=0, metric_after=500.0),
    ]
    result = mine_rules(incidents)
    assert result["rules"] == []


RULE_A = {
    "rule_id": "RULE-001",
    "kind": "api_substitution",
    "removed": "queueAnalyticsEvent",
    "added": "analytics.track",
}


def test_rule_fires_on_forbidden_call():
    assert rule_fires(RULE_A, {"calls": ["setup", "queueAnalyticsEvent"]})


def test_rule_does_not_fire_on_replacement():
    assert not rule_fires(RULE_A, {"calls": ["analytics.track"]})


def test_rule_does_not_fire_without_calls():
    assert not rule_fires(RULE_A, {})
    assert not rule_fires(RULE_A, {"calls": []})


def test_rule_with_no_removed_never_fires():
    assert not rule_fires({"removed": None}, {"calls": ["anything"]})


def test_score_rule_counts_and_rates():
    runs = [
        _run(["queueAnalyticsEvent"], True, True, False, False),
        _run(["queueAnalyticsEvent"], True, True, False, False),
        _run(["queueAnalyticsEvent"], False, True, False, False),
        _run(["analytics.track"], False, True, False, False),
        _run(["other_call"], True, True, False, False),
    ]
    scored = score_rule(RULE_A, runs)
    assert scored["true_positive"] == 2
    assert scored["false_positive"] == 1
    assert scored["false_negative"] == 1
    assert scored["true_negative"] == 1
    assert scored["precision"] == pytest.approx(2 / 3)
    assert scored["recall"] == pytest.approx(2 / 3)
    assert scored["f1"] == pytest.approx(2 / 3)


def test_score_rule_never_fires_precision_none():
    runs = [_run(["analytics.track"], True, True, False, False)]
    scored = score_rule(RULE_A, runs)
    assert scored["precision"] is None
    assert scored["recall"] == 0.0
    assert scored["f1"] is None


def test_score_rule_no_violations_recall_none():
    runs = [
        _run(["queueAnalyticsEvent"], False, True, False, False),
        _run(["analytics.track"], False, True, False, False),
    ]
    scored = score_rule(RULE_A, runs)
    assert scored["precision"] == 0.0
    assert scored["recall"] is None
    assert scored["f1"] is None


def test_score_rule_empty_runs():
    scored = score_rule(RULE_A, [])
    assert scored["true_positive"] == 0
    assert scored["precision"] is None
    assert scored["recall"] is None
    assert scored["f1"] is None


def test_score_rule_rejects_non_list():
    with pytest.raises(ValueError):
        score_rule(RULE_A, {"calls": []})


RULE_B = {
    "rule_id": "RULE-002",
    "kind": "test_execution",
    "removed": "run_tests_without_coverage",
    "added": "run_tests_with_coverage",
}
RULE_C = {
    "rule_id": "RULE-003",
    "kind": "metric_regression",
    "removed": "full_table_scan",
    "added": "indexed_query",
}
RULES = [RULE_A, RULE_B, RULE_C]

READY_RUNS = [
    _run(["analytics.track"], False, True, True, True),
    _run(["analytics.track"], False, True, True, True),
    _run(["analytics.track"], False, True, False, True),
    _run(["queueAnalyticsEvent"], True, True, True, True),
    _run(["run_tests_with_coverage"], False, True, True, True),
    _run(["run_tests_with_coverage"], False, False, True, True),
    _run(["queueAnalyticsEvent"], True, True, False, False),
    _run(["queueAnalyticsEvent"], True, True, False, False),
    _run(["full_table_scan"], True, True, True, False),
    _run(["run_tests_without_coverage"], True, False, False, False),
    _run(["analytics.track"], False, True, False, False),
    _run(["analytics.track"], False, True, False, False),
]


def test_campaign_ready_fixture():
    campaign = score_campaign(RULES, READY_RUNS)
    assert campaign["rules"] == 3
    assert campaign["runs"] == 12
    assert campaign["with_rules"]["runs"] == 6
    assert campaign["with_rules"]["violation_rate"] == pytest.approx(1 / 6)
    assert campaign["with_rules"]["resolution_rate"] == pytest.approx(5 / 6)
    assert campaign["with_rules"]["search_rate"] == pytest.approx(5 / 6)
    assert campaign["without_rules"]["violation_rate"] == pytest.approx(4 / 6)
    assert campaign["without_rules"]["resolution_rate"] == pytest.approx(5 / 6)
    assert campaign["without_rules"]["search_rate"] == pytest.approx(1 / 6)
    assert campaign["violating_runs"] == 5
    assert campaign["covered_violating_runs"] == 5
    assert campaign["coverage"] == 1.0
    assert campaign["mean_precision"] == 1.0
    assert campaign["mean_recall"] == pytest.approx(1 / 3)
    assert campaign["verdict"] == VERDICT_PASS


def test_campaign_block_above_baseline():
    runs = [
        _run(["queueAnalyticsEvent"], True, True, False, True),
        _run(["queueAnalyticsEvent"], True, True, False, True),
        _run(["queueAnalyticsEvent"], True, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["analytics.track"], False, True, False, False),
        _run(["analytics.track"], False, True, False, False),
    ]
    campaign = score_campaign(RULES, runs)
    assert campaign["with_rules"]["violation_rate"] == 0.5
    assert campaign["verdict"] == VERDICT_BLOCK


def test_campaign_review_between_bars():
    runs = [
        _run(["queueAnalyticsEvent"], True, True, False, True),
        _run(["queueAnalyticsEvent"], True, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["queueAnalyticsEvent"], True, True, False, False),
        _run(["queueAnalyticsEvent"], True, True, False, False),
        _run(["queueAnalyticsEvent"], True, True, False, False),
        _run(["queueAnalyticsEvent"], True, True, False, False),
        _run(["analytics.track"], False, True, False, False),
        _run(["analytics.track"], False, True, False, False),
    ]
    campaign = score_campaign(RULES, runs)
    assert campaign["with_rules"]["violation_rate"] == pytest.approx(1 / 3)
    assert campaign["verdict"] == VERDICT_REVIEW


def test_campaign_resolution_loss_is_review_not_ready():
    runs = [
        _run(["queueAnalyticsEvent"], True, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["analytics.track"], False, False, False, True),
        _run(["analytics.track"], False, False, False, True),
        _run(["analytics.track"], False, False, False, True),
        _run(["queueAnalyticsEvent"], True, True, False, False),
        _run(["queueAnalyticsEvent"], True, True, False, False),
        _run(["analytics.track"], False, True, False, False),
        _run(["analytics.track"], False, True, False, False),
        _run(["analytics.track"], False, True, False, False),
        _run(["analytics.track"], False, True, False, False),
    ]
    campaign = score_campaign(RULES, runs)
    assert campaign["with_rules"]["violation_rate"] == pytest.approx(1 / 6)
    assert campaign["with_rules"]["resolution_rate"] == 0.5
    assert campaign["without_rules"]["resolution_rate"] == 1.0
    assert campaign["verdict"] == VERDICT_REVIEW


def test_campaign_empty_runs_is_review():
    campaign = score_campaign(RULES, [])
    assert campaign["verdict"] == VERDICT_REVIEW
    assert campaign["with_rules"]["violation_rate"] is None
    assert campaign["coverage"] is None
    assert campaign["mean_precision"] is None


def test_campaign_only_with_rules_group():
    runs = READY_RUNS[:6]
    campaign = score_campaign(RULES, runs)
    assert campaign["without_rules"]["runs"] == 0
    assert campaign["without_rules"]["violation_rate"] is None
    assert campaign["verdict"] == VERDICT_PASS


def test_campaign_no_with_rules_group_is_review():
    runs = READY_RUNS[6:]
    campaign = score_campaign(RULES, runs)
    assert campaign["with_rules"]["runs"] == 0
    assert campaign["verdict"] == VERDICT_REVIEW


def test_campaign_partial_coverage():
    rules = [RULE_A]
    runs = [
        _run(["queueAnalyticsEvent"], True, True, False, True),
        _run(["unknown_call"], True, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["analytics.track"], False, True, False, True),
        _run(["analytics.track"], False, True, False, True),
    ]
    campaign = score_campaign(rules, runs)
    assert campaign["violating_runs"] == 2
    assert campaign["covered_violating_runs"] == 1
    assert campaign["coverage"] == 0.5


def test_campaign_rejects_bad_baseline():
    with pytest.raises(ValueError):
        score_campaign(RULES, READY_RUNS, baseline_violation_rate=1.0)
    with pytest.raises(ValueError):
        score_campaign(RULES, READY_RUNS, baseline_violation_rate=0.0)


def test_baseline_constant_matches_swe_cc():
    assert BASELINE_VIOLATION_RATE == 0.431


def test_format_summary_ready_campaign():
    campaign = score_campaign(RULES, READY_RUNS)
    summary = format_summary(campaign)
    assert summary.startswith("IncidentMiner: 3 rules, 12 runs, ")
    assert "violation rate 0.1667 with rules vs 0.6667 without" in summary
    assert "coverage 1.00 of violating runs" in summary
    assert summary.endswith("verdict PASS")


def test_format_summary_empty_campaign():
    campaign = score_campaign(RULES, [])
    summary = format_summary(campaign)
    assert "violation rate n/a with rules vs n/a without" in summary
    assert "coverage n/a of violating runs" in summary
    assert summary.endswith("verdict REVIEW")
