"""Focused verification for TRUSTRUN-PreservationAware.

Scores the module's 25 labeled cases: the clean improvement,
the paper's headline shape (reliability rises while ten
previously covered tasks are lost), the flat-headline churn
case, net-negative turnover, the costly-reliability-gain cost
axis (supplied, flat, rising, and absent), single-task edges,
and the outcome precedence when several checks fire at once.
Every case is a fixed scripted snapshot pair with an expected
overall outcome and an expected verdict for its key check,
scored by trustrun.preservation_aware.

Writes a machine-readable summary into
reports/preservation-aware-verify/summary.json. Expected yield:
25 labeled probe cases, 25/25 match. Exits non-zero on any
mismatch.

This script was derived from the all-or-nothing labeled cases
in evals/run_all_or_nothing_verify.py. Its REPORTS constant was
verified to point at preservation-aware-verify/ before the run,
so it cannot overwrite any round directory.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.preservation_aware import (  # noqa: E402
    OVERALL_CLEAN_IMPROVEMENT,
    OVERALL_COSTLY_GAIN,
    OVERALL_MASKED_IMPROVEMENT,
    OVERALL_NET_REGRESSION,
    OVERALL_UNCHANGED,
    VERDICT_PASS,
    VERDICT_VIOLATION,
    score_turnover,
)

REPORTS = os.path.join(HERE, "reports", "preservation-aware-verify")


def _snapshots(baseline_true, new_true, n_tasks=10):
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


def preservation_aware_cases():
    """25 labeled preservation cases: (case_id, key check,
    baseline, new, baseline_costs, new_costs, expected
    outcome, expected key-check verdict)."""
    cases = []

    # Clean improvement: two gains, no regressions.
    baseline, new = _snapshots(
        {"t1", "t2", "t3", "t4", "t5", "t6"},
        {"t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"},
    )
    cases.append((
        "clean_improvement", "regression",
        baseline, new, None, None,
        OVERALL_CLEAN_IMPROVEMENT, VERDICT_PASS,
    ))

    # The paper's headline shape: reliability rises 5 points
    # while ten previously covered tasks are lost.
    baseline_true = {"t%d" % i for i in range(1, 81)}
    new_true = (
        {"t%d" % i for i in range(1, 71)}
        | {"t%d" % i for i in range(81, 96)}
    )
    baseline, new = _snapshots(
        baseline_true, new_true, n_tasks=100
    )
    cases.append((
        "paper_shape_rise_with_ten_lost", "headline_masks_regression",
        baseline, new, None, None,
        OVERALL_MASKED_IMPROVEMENT, VERDICT_VIOLATION,
    ))

    # All sixteen agents lost tasks: gains and regressions
    # both present, headline up.
    baseline, new = _snapshots(
        {"t%d" % i for i in range(1, 9)},
        {"t%d" % i for i in range(1, 8)}
        | {"t9", "t10"},
    )
    cases.append((
        "gains_and_losses_headline_up", "headline_masks_regression",
        baseline, new, None, None,
        OVERALL_MASKED_IMPROVEMENT, VERDICT_VIOLATION,
    ))

    # Flat headline with churn: gains exactly cover the
    # regressions, so the headline says "no change" while
    # three covered tasks were lost.
    baseline, new = _snapshots(
        {"t1", "t2", "t3", "t4", "t5", "t6"},
        {"t1", "t2", "t3", "t7", "t8", "t9"},
    )
    cases.append((
        "flat_headline_churn", "headline_masks_regression",
        baseline, new, None, None,
        OVERALL_MASKED_IMPROVEMENT, VERDICT_VIOLATION,
    ))

    # Net negative: six regressions against two gains.
    baseline, new = _snapshots(
        {"t%d" % i for i in range(1, 9)},
        {"t1", "t2", "t9", "t10"},
    )
    cases.append((
        "net_negative_turnover", "net_negative_turnover",
        baseline, new, None, None,
        OVERALL_NET_REGRESSION, VERDICT_VIOLATION,
    ))

    # A single lost task: regressions outnumber gains 1 to 0.
    baseline, new = _snapshots(
        {"t1", "t2", "t3"}, {"t1", "t2"},
    )
    cases.append((
        "single_regression", "regression",
        baseline, new, None, None,
        OVERALL_NET_REGRESSION, VERDICT_VIOLATION,
    ))

    # Costly gain: reliability up, mean cost per task up.
    baseline, new = _snapshots(
        {"t1", "t2", "t3", "t4", "t5", "t6"},
        {"t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"},
    )
    cases.append((
        "costly_reliability_gain", "costly_reliability_gain",
        baseline, new, _costs(10, 1.00), _costs(10, 1.50),
        OVERALL_COSTLY_GAIN, VERDICT_VIOLATION,
    ))

    # Clean gain, cheaper: reliability up, cost down.
    baseline, new = _snapshots(
        {"t1", "t2", "t3", "t4", "t5", "t6"},
        {"t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"},
    )
    cases.append((
        "clean_gain_cheaper", "costly_reliability_gain",
        baseline, new, _costs(10, 1.50), _costs(10, 1.00),
        OVERALL_CLEAN_IMPROVEMENT, VERDICT_PASS,
    ))

    # Cost flat with a gain: no costly-gain violation.
    baseline, new = _snapshots(
        {"t1", "t2", "t3", "t4", "t5", "t6"},
        {"t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"},
    )
    cases.append((
        "cost_flat_with_gain", "costly_reliability_gain",
        baseline, new, _costs(10, 1.00), _costs(10, 1.00),
        OVERALL_CLEAN_IMPROVEMENT, VERDICT_PASS,
    ))

    # Identical outcomes with cost up: not a costly gain,
    # because reliability did not rise.
    baseline, new = _snapshots(
        {"t1", "t2", "t3"}, {"t1", "t2", "t3"},
    )
    cases.append((
        "cost_up_flat_reliability", "costly_reliability_gain",
        baseline, new, _costs(10, 1.00), _costs(10, 2.00),
        OVERALL_UNCHANGED, VERDICT_PASS,
    ))

    # Identical snapshots: unchanged, all checks pass.
    baseline, new = _snapshots(
        {"t1", "t2", "t3"}, {"t1", "t2", "t3"},
    )
    cases.append((
        "unchanged_identical", "regression",
        baseline, new, None, None,
        OVERALL_UNCHANGED, VERDICT_PASS,
    ))

    # All failed on both sides: unchanged.
    baseline, new = _snapshots(set(), set(), n_tasks=5)
    cases.append((
        "unchanged_all_failed", "regression",
        baseline, new, None, None,
        OVERALL_UNCHANGED, VERDICT_PASS,
    ))

    # Every task regressed.
    baseline, new = _snapshots(
        {"t%d" % i for i in range(1, 11)}, set(),
    )
    cases.append((
        "all_tasks_regressed", "net_negative_turnover",
        baseline, new, None, None,
        OVERALL_NET_REGRESSION, VERDICT_VIOLATION,
    ))

    # Every task gained from an all-fail baseline.
    baseline, new = _snapshots(
        set(), {"t%d" % i for i in range(1, 11)},
    )
    cases.append((
        "all_tasks_gained", "regression",
        baseline, new, None, None,
        OVERALL_CLEAN_IMPROVEMENT, VERDICT_PASS,
    ))

    # Single task, gained.
    baseline = {"t1": False}
    new = {"t1": True}
    cases.append((
        "single_task_gain", "regression",
        baseline, new, None, None,
        OVERALL_CLEAN_IMPROVEMENT, VERDICT_PASS,
    ))

    # Single task, regressed.
    baseline = {"t1": True}
    new = {"t1": False}
    cases.append((
        "single_task_regression", "regression",
        baseline, new, None, None,
        OVERALL_NET_REGRESSION, VERDICT_VIOLATION,
    ))

    # Single task, unchanged pass.
    baseline = {"t1": True}
    new = {"t1": True}
    cases.append((
        "single_task_unchanged_pass", "regression",
        baseline, new, None, None,
        OVERALL_UNCHANGED, VERDICT_PASS,
    ))

    # Single task, unchanged fail.
    baseline = {"t1": False}
    new = {"t1": False}
    cases.append((
        "single_task_unchanged_fail", "regression",
        baseline, new, None, None,
        OVERALL_UNCHANGED, VERDICT_PASS,
    ))

    # Masked improvement beats costly gain in the outcome:
    # headline up with a regression and cost up.
    baseline, new = _snapshots(
        {"t%d" % i for i in range(1, 9)},
        {"t%d" % i for i in range(1, 8)} | {"t9", "t10"},
    )
    cases.append((
        "masked_beats_costly", "headline_masks_regression",
        baseline, new, _costs(10, 1.00), _costs(10, 1.25),
        OVERALL_MASKED_IMPROVEMENT, VERDICT_VIOLATION,
    ))

    # Regressions with cost down: still a net regression,
    # and the cost check does not fire.
    baseline, new = _snapshots(
        {"t%d" % i for i in range(1, 9)},
        {"t1", "t2", "t9", "t10"},
    )
    cases.append((
        "regressions_cost_down", "costly_reliability_gain",
        baseline, new, _costs(10, 1.50), _costs(10, 1.00),
        OVERALL_NET_REGRESSION, VERDICT_PASS,
    ))

    # Large scale: 500 tasks, 480 baseline pass, 490 new
    # pass, 15 regressions, 25 gains.
    baseline_true = {"t%d" % i for i in range(1, 481)}
    new_true = (
        {"t%d" % i for i in range(1, 466)}
        | {"t%d" % i for i in range(481, 506)}
    )
    baseline, new = _snapshots(
        baseline_true, new_true, n_tasks=500
    )
    cases.append((
        "large_scale_masked", "headline_masks_regression",
        baseline, new, None, None,
        OVERALL_MASKED_IMPROVEMENT, VERDICT_VIOLATION,
    ))

    # Preserved only: every passing task stays passing, one
    # task stays failed.
    baseline, new = _snapshots(
        {"t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9"},
        {"t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8", "t9"},
    )
    cases.append((
        "preserved_only", "regression",
        baseline, new, None, None,
        OVERALL_UNCHANGED, VERDICT_PASS,
    ))

    # Flat headline with churn and cost up: the masked
    # improvement names the outcome.
    baseline, new = _snapshots(
        {"t1", "t2", "t3", "t4", "t5", "t6"},
        {"t1", "t2", "t3", "t7", "t8", "t9"},
    )
    cases.append((
        "flat_churn_cost_up", "headline_masks_regression",
        baseline, new, _costs(10, 1.00), _costs(10, 1.10),
        OVERALL_MASKED_IMPROVEMENT, VERDICT_VIOLATION,
    ))

    # Ten gains, no regressions, no cost data: clean.
    baseline, new = _snapshots(
        set(), {"t%d" % i for i in range(1, 11)},
    )
    cases.append((
        "gains_only_many", "regression",
        baseline, new, None, None,
        OVERALL_CLEAN_IMPROVEMENT, VERDICT_PASS,
    ))

    # Cost supplied, gain, cost down slightly: clean.
    baseline, new = _snapshots(
        {"t1", "t2", "t3", "t4", "t5"},
        {"t1", "t2", "t3", "t4", "t5", "t6", "t7"},
    )
    cases.append((
        "gain_cost_down_slightly", "costly_reliability_gain",
        baseline, new, _costs(10, 1.00), _costs(10, 0.95),
        OVERALL_CLEAN_IMPROVEMENT, VERDICT_PASS,
    ))

    return cases


def main():
    assert REPORTS.endswith("preservation-aware-verify"), REPORTS
    os.makedirs(REPORTS, exist_ok=True)
    results = []
    for case in preservation_aware_cases():
        (case_id, check, baseline, new, baseline_costs,
         new_costs, expected_outcome, expected_check) = case
        score = score_turnover(
            baseline, new, baseline_costs, new_costs
        )
        actual_outcome = score["outcome"]
        actual_check = score["checks"][check]["verdict"]
        match = (
            actual_outcome == expected_outcome
            and actual_check == expected_check
        )
        results.append({
            "case_id": case_id,
            "check": check,
            "expected_outcome": expected_outcome,
            "actual_outcome": actual_outcome,
            "expected_check_verdict": expected_check,
            "actual_check_verdict": actual_check,
            "match": match,
        })
    matched = sum(1 for item in results if item["match"])
    summary = {
        "cases": len(results),
        "matched": matched,
        "results": results,
    }
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=1)
    print("preservation-aware labeled cases: %d/%d match"
          % (matched, len(results)))
    for item in results:
        if not item["match"]:
            print(
                "MISMATCH %s: expected %s/%s, got %s/%s"
                % (
                    item["case_id"],
                    item["expected_outcome"],
                    item["expected_check_verdict"],
                    item["actual_outcome"],
                    item["actual_check_verdict"],
                )
            )
    if matched != len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
