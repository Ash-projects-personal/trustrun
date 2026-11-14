"""Focused verification for TRUSTRUN-IncidentMiner.

Scores the module's 25 labeled cases: mine the seven-incident
fixture (three-pattern grouping, severe metric singleton, severe
downtime singleton, non-severe singleton dropped, min_support 3,
empty incidents, substitution/metric/no-replacement rule text, a
missing-kind rejection), rule firing and rule precision/recall
(the five-run fixture: 2 true positive, 1 false positive, 1
false negative, 1 true negative; never-fires; no violations;
empty runs), and campaign verdicts (the 12-run READY fixture,
BLOCK above the SWE-CC baseline, REVIEW between the bars,
resolution-loss REVIEW, empty campaign, with-rules-only,
without-rules-only, partial coverage, and the one-line summary).
Every case is a fixed recorded incident or run set with a
hand-computed score, scored by trustrun.incident_miner. The
campaign block checks the aggregate numbers by hand: 12 runs,
violation rate 1/6 with rules vs 4/6 without, resolution 5/6
both sides, search 5/6 vs 1/6, coverage 1.00 of the 5 violating
runs, mean precision 1.0000, mean recall 0.3333, verdict PASS.

Writes a machine-readable summary into
reports/incident-miner-verify/summary.json. Expected yield: 25
labeled cases, 25/25 match, campaign block matches.
Exits non-zero on any mismatch.

The cases are synthetic incidents and runs with hand-computed
scores, not SWE-CC trajectories.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.incident_miner import (  # noqa: E402
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_REVIEW,
    format_summary,
    mine_rules,
    rule_fires,
    score_campaign,
    score_rule,
)

REPORTS = os.path.join(HERE, "reports", "incident-miner-verify")


def _inc(incident_id, kind, removed, added=None, repo="acme/web",
         metric_before=None, metric_after=None, downtime=None):
    incident = {
        "incident_id": incident_id,
        "kind": kind,
        "removed": removed,
        "added": added,
        "repo": repo,
        "tests_passed": True,
        "stage": "final",
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

RULE_A = {
    "rule_id": "RULE-001",
    "kind": "api_substitution",
    "removed": "queueAnalyticsEvent",
    "added": "analytics.track",
}
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

SCORE_RUNS = [
    _run(["queueAnalyticsEvent"], True, True, False, False),
    _run(["queueAnalyticsEvent"], True, True, False, False),
    _run(["queueAnalyticsEvent"], False, True, False, False),
    _run(["analytics.track"], False, True, False, False),
    _run(["other_call"], True, True, False, False),
]

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

BLOCK_RUNS = [
    _run(["queueAnalyticsEvent"], True, True, False, True),
    _run(["queueAnalyticsEvent"], True, True, False, True),
    _run(["queueAnalyticsEvent"], True, True, False, True),
    _run(["analytics.track"], False, True, False, True),
    _run(["analytics.track"], False, True, False, True),
    _run(["analytics.track"], False, True, False, True),
    _run(["analytics.track"], False, True, False, False),
    _run(["analytics.track"], False, True, False, False),
]

REVIEW_RUNS = [
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

RESOLUTION_LOSS_RUNS = [
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

PARTIAL_COVERAGE_RUNS = [
    _run(["queueAnalyticsEvent"], True, True, False, True),
    _run(["unknown_call"], True, True, False, True),
    _run(["analytics.track"], False, True, False, True),
    _run(["analytics.track"], False, True, False, True),
    _run(["analytics.track"], False, True, False, True),
    _run(["analytics.track"], False, True, False, True),
]

# (case_id, kind, payload, expected)
CASES = [
    ("mine-groups", "mine", (INCIDENTS, {}),
     {"rules": 3, "dropped": 1, "first_rule_id": "RULE-001",
      "first_support": 3, "first_severe": True}),
    ("mine-severe-metric-singleton", "mine",
     ([INCIDENTS[6]], {}),
     {"rules": 1, "dropped": 0, "first_rule_id": "RULE-001",
      "first_support": 1, "first_severe": True}),
    ("mine-severe-downtime-singleton", "mine",
     ([_inc("INC-102", "scope_violation", "prod_db_write",
            "staging_db_write", downtime=60)], {}),
     {"rules": 1, "dropped": 0, "first_support": 1,
      "first_severe": True}),
    ("mine-non-severe-singleton-dropped", "mine",
     ([INCIDENTS[5]], {}),
     {"rules": 0, "dropped": 1}),
    ("mine-min-support-3", "mine", (INCIDENTS, {"min_support": 3}),
     {"rules": 2, "dropped": 2, "first_rule_id": "RULE-001",
      "first_support": 3}),
    ("mine-empty", "mine", ([], {}),
     {"rules": 0, "dropped": 0, "incidents": 0, "patterns": 0}),
    ("mine-text-substitution", "mine_text", (INCIDENTS, {}),
     "Do not use queueAnalyticsEvent; use analytics.track instead."),
    ("mine-text-metric", "mine_text",
     ([INCIDENTS[6]], {}),
     "Do not call full_table_scan on the hot path; "
     "use indexed_query instead."),
    ("mine-text-no-replacement", "mine_text",
     ([_inc("INC-105", "other", "rm_rf_tmp", None),
       _inc("INC-106", "other", "rm_rf_tmp", None)], {}),
     "Avoid rm_rf_tmp."),
    ("mine-rejects-missing-kind", "mine_error",
     ([{"incident_id": "INC-001", "kind": "other"}], {}),
     "ValueError"),
    ("fires-true", "fires",
     (RULE_A, {"calls": ["setup", "queueAnalyticsEvent"]}), True),
    ("fires-false", "fires",
     (RULE_A, {"calls": ["analytics.track"]}), False),
    ("score-rule-counts", "score_rule", (RULE_A, SCORE_RUNS),
     {"true_positive": 2, "false_positive": 1,
      "false_negative": 1, "true_negative": 1,
      "precision": 0.6667, "recall": 0.6667, "f1": 0.6667}),
    ("score-rule-never-fires", "score_rule",
     (RULE_A, [_run(["analytics.track"], True, True, False, False)]),
     {"true_positive": 0, "false_positive": 0,
      "false_negative": 1, "true_negative": 0,
      "precision": None, "recall": 0.0, "f1": None}),
    ("score-rule-no-violations", "score_rule",
     (RULE_A, [_run(["queueAnalyticsEvent"], False, True, False, False),
               _run(["analytics.track"], False, True, False, False)]),
     {"true_positive": 0, "false_positive": 1,
      "false_negative": 0, "true_negative": 1,
      "precision": 0.0, "recall": None, "f1": None}),
    ("score-rule-empty", "score_rule", (RULE_A, []),
     {"true_positive": 0, "false_positive": 0,
      "false_negative": 0, "true_negative": 0,
      "precision": None, "recall": None, "f1": None}),
    ("campaign-ready", "campaign", (RULES, READY_RUNS),
     {"verdict": VERDICT_PASS,
      "violation_with": 0.1667, "violation_without": 0.6667,
      "resolution_with": 0.8333, "resolution_without": 0.8333,
      "search_with": 0.8333, "search_without": 0.1667,
      "coverage": 1.0, "mean_precision": 1.0,
      "mean_recall": 0.3333}),
    ("campaign-block", "campaign", (RULES, BLOCK_RUNS),
     {"verdict": VERDICT_BLOCK, "violation_with": 0.5}),
    ("campaign-review", "campaign", (RULES, REVIEW_RUNS),
     {"verdict": VERDICT_REVIEW, "violation_with": 0.3333}),
    ("campaign-resolution-loss", "campaign",
     (RULES, RESOLUTION_LOSS_RUNS),
     {"verdict": VERDICT_REVIEW, "violation_with": 0.1667,
      "resolution_with": 0.5, "resolution_without": 1.0}),
    ("campaign-empty", "campaign", (RULES, []),
     {"verdict": VERDICT_REVIEW, "violation_with": None,
      "coverage": None}),
    ("campaign-only-with-rules", "campaign",
     (RULES, READY_RUNS[:6]),
     {"verdict": VERDICT_PASS, "violation_with": 0.1667,
      "violation_without": None}),
    ("campaign-no-with-rules", "campaign", (RULES, READY_RUNS[6:]),
     {"verdict": VERDICT_REVIEW, "violation_with": None}),
    ("campaign-partial-coverage", "campaign",
     ([RULE_A], PARTIAL_COVERAGE_RUNS),
     {"verdict": VERDICT_REVIEW, "coverage": 0.5,
      "violating_runs": 2, "covered_violating_runs": 1}),
    ("format-summary", "summary", (RULES, READY_RUNS),
     "IncidentMiner: 3 rules, 12 runs, violation rate 0.1667 "
     "with rules vs 0.6667 without, coverage 1.00 of violating "
     "runs, verdict PASS"),
]

EXPECTED_CAMPAIGN = {
    "rules": 3,
    "runs": 12,
    "verdict": VERDICT_PASS,
    "violation_with": 0.1667,
    "violation_without": 0.6667,
    "resolution_with": 0.8333,
    "resolution_without": 0.8333,
    "search_with": 0.8333,
    "search_without": 0.1667,
    "coverage": 1.0,
    "mean_precision": 1.0,
    "mean_recall": 0.3333,
}


def _round(value):
    return None if value is None else round(value, 4)


def _check(kind, payload, expected):
    if kind == "mine":
        incidents, kwargs = payload
        result = mine_rules(incidents, **kwargs)
        got = {
            "rules": len(result["rules"]),
            "dropped": len(result["dropped"]),
        }
        if result["rules"]:
            got["first_rule_id"] = result["rules"][0]["rule_id"]
            got["first_support"] = result["rules"][0]["support"]
            got["first_severe"] = result["rules"][0]["severe"]
        if "incidents" in expected:
            got["incidents"] = result["incidents"]
        if "patterns" in expected:
            got["patterns"] = result["patterns"]
        got = {key: value for key, value in got.items()
               if key in expected}
        return got == expected, got
    if kind == "mine_text":
        incidents, kwargs = payload
        result = mine_rules(incidents, **kwargs)
        got = result["rules"][0]["text"] if result["rules"] else None
        return got == expected, got
    if kind == "mine_error":
        incidents, kwargs = payload
        try:
            mine_rules(incidents, **kwargs)
        except ValueError:
            return expected == "ValueError", "ValueError"
        return False, "no error"
    if kind == "fires":
        rule, run = payload
        got = rule_fires(rule, run)
        return got == expected, got
    if kind == "score_rule":
        rule, runs = payload
        scored = score_rule(rule, runs)
        got = {
            "true_positive": scored["true_positive"],
            "false_positive": scored["false_positive"],
            "false_negative": scored["false_negative"],
            "true_negative": scored["true_negative"],
            "precision": _round(scored["precision"]),
            "recall": _round(scored["recall"]),
            "f1": _round(scored["f1"]),
        }
        return got == expected, got
    if kind == "campaign":
        rules, runs = payload
        campaign = score_campaign(rules, runs)
        got = {"verdict": campaign["verdict"]}
        if "violation_with" in expected:
            got["violation_with"] = _round(
                campaign["with_rules"]["violation_rate"]
            )
        if "violation_without" in expected:
            got["violation_without"] = _round(
                campaign["without_rules"]["violation_rate"]
            )
        if "resolution_with" in expected:
            got["resolution_with"] = _round(
                campaign["with_rules"]["resolution_rate"]
            )
        if "resolution_without" in expected:
            got["resolution_without"] = _round(
                campaign["without_rules"]["resolution_rate"]
            )
        if "search_with" in expected:
            got["search_with"] = _round(
                campaign["with_rules"]["search_rate"]
            )
        if "search_without" in expected:
            got["search_without"] = _round(
                campaign["without_rules"]["search_rate"]
            )
        if "coverage" in expected:
            got["coverage"] = _round(campaign["coverage"])
        if "mean_precision" in expected:
            got["mean_precision"] = _round(campaign["mean_precision"])
        if "mean_recall" in expected:
            got["mean_recall"] = _round(campaign["mean_recall"])
        if "violating_runs" in expected:
            got["violating_runs"] = campaign["violating_runs"]
        if "covered_violating_runs" in expected:
            got["covered_violating_runs"] = campaign[
                "covered_violating_runs"
            ]
        return got == expected, got
    if kind == "summary":
        rules, runs = payload
        campaign = score_campaign(rules, runs)
        got = format_summary(campaign)
        return got == expected, got
    raise ValueError("unknown case kind %s" % kind)


def main():
    rows = []
    matched = 0
    for case_id, kind, payload, expected in CASES:
        match, got = _check(kind, payload, expected)
        matched += 1 if match else 0
        rows.append({
            "case_id": case_id,
            "kind": kind,
            "expected": expected,
            "actual": got,
            "match": match,
        })

    campaign = score_campaign(RULES, READY_RUNS)
    campaign_block = {
        "rules": campaign["rules"],
        "runs": campaign["runs"],
        "verdict": campaign["verdict"],
        "violation_with": _round(
            campaign["with_rules"]["violation_rate"]
        ),
        "violation_without": _round(
            campaign["without_rules"]["violation_rate"]
        ),
        "resolution_with": _round(
            campaign["with_rules"]["resolution_rate"]
        ),
        "resolution_without": _round(
            campaign["without_rules"]["resolution_rate"]
        ),
        "search_with": _round(campaign["with_rules"]["search_rate"]),
        "search_without": _round(
            campaign["without_rules"]["search_rate"]
        ),
        "coverage": _round(campaign["coverage"]),
        "mean_precision": _round(campaign["mean_precision"]),
        "mean_recall": _round(campaign["mean_recall"]),
    }
    campaign_ok = campaign_block == EXPECTED_CAMPAIGN

    summary = {
        "cases": rows,
        "matched": matched,
        "total": len(CASES),
        "campaign": campaign_block,
        "campaign_match": campaign_ok,
    }
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2)

    print("IncidentMiner verify: %d/%d cases matched"
          % (matched, len(CASES)))
    print("campaign:", json.dumps(campaign_block, sort_keys=True))
    ok = matched == len(CASES) and campaign_ok
    if not ok:
        print("MISMATCH: see summary.json")
        return 1
    print("25/25 match, campaign block matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
