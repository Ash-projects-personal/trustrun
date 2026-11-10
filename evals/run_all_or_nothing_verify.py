"""Focused verification for TRUSTRUN-AllOrNothing.

Scores the module's 25 labeled cases: the delivered outcome, the
ViBench 2.0 headline shape (49 of 50 plans pass, product not
delivered), the 90% partial-credit line, interaction-only
failures, ungraded plans (explicit None and missing from the
results), plain low-rate failures, per-feature delivery, and the
outcome precedence when several checks fire at once. Every case
is a fixed scripted product spec with an expected overall outcome
and an expected verdict for its key check, scored by
trustrun.all_or_nothing.

Writes a machine-readable summary into
reports/all-or-nothing-verify/summary.json. Expected yield: 25
labeled probe cases, 25/25 match. Exits non-zero on any mismatch.

This script was derived from the claim-audit labeled cases in
evals/run_claim_audit_verify.py. Its REPORTS constant was verified
to point at all-or-nothing-verify/ before the run, so it cannot
overwrite any round directory.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.all_or_nothing import (  # noqa: E402
    OVERALL_DELIVERED,
    OVERALL_FAILED,
    OVERALL_INTERACTION_BREAK,
    OVERALL_PARTIAL_CREDIT_TRAP,
    OVERALL_UNGRADED,
    VERDICT_PASS,
    VERDICT_VIOLATION,
    score_build,
)

REPORTS = os.path.join(HERE, "reports", "all-or-nothing-verify")


def _product(n_plans, n_features=1, combine_from=None):
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


def all_or_nothing_cases():
    """25 labeled all-or-nothing cases: (case_id, key check,
    product, results, expected outcome, expected key-check
    verdict)."""
    cases = []

    # Clean delivery: every plan passes.
    product = _product(10, n_features=2)
    cases.append((
        "clean_delivered", "not_delivered",
        product, _results(product),
        OVERALL_DELIVERED, VERDICT_PASS,
    ))

    # The ViBench headline shape: 49 of 50 plans pass, yet the
    # product is not delivered.
    product = _product(50, n_features=5)
    cases.append((
        "vibench_gap_98_percent", "partial_credit_masks_failure",
        product, _results(product, failed=("p50",)),
        OVERALL_PARTIAL_CREDIT_TRAP, VERDICT_VIOLATION,
    ))

    # Same shape at a smaller scale: 19 of 20 plans pass.
    product = _product(20, n_features=4)
    cases.append((
        "vibench_gap_95_percent", "partial_credit_masks_failure",
        product, _results(product, failed=("p20",)),
        OVERALL_PARTIAL_CREDIT_TRAP, VERDICT_VIOLATION,
    ))

    # Exactly at the 90% line, the trap still fires.
    product = _product(10, n_features=2)
    cases.append((
        "at_partial_credit_line", "partial_credit_masks_failure",
        product, _results(product, failed=("p10",)),
        OVERALL_PARTIAL_CREDIT_TRAP, VERDICT_VIOLATION,
    ))

    # Just below the line, the failure is plain, not masked.
    product = _product(10, n_features=2)
    cases.append((
        "below_partial_credit_line", "partial_credit_masks_failure",
        product, _results(product, failed=("p9", "p10")),
        OVERALL_FAILED, VERDICT_PASS,
    ))

    # A low plan rate is a plain failure.
    product = _product(10, n_features=2)
    cases.append((
        "low_rate_failure", "not_delivered",
        product,
        _results(product, failed=("p6", "p7", "p8", "p9", "p10")),
        OVERALL_FAILED, VERDICT_VIOLATION,
    ))

    # Interaction-only failure: every single-feature plan passed,
    # only combination plans failed.
    product = _product(6, n_features=3, combine_from=4)
    cases.append((
        "interaction_only_failure", "interaction_failure",
        product, _results(product, failed=("p5", "p6")),
        OVERALL_INTERACTION_BREAK, VERDICT_VIOLATION,
    ))

    # One combination plan failing alone is still interaction-only.
    product = _product(6, n_features=3, combine_from=4)
    cases.append((
        "interaction_single_failure", "interaction_failure",
        product, _results(product, failed=("p6",)),
        OVERALL_INTERACTION_BREAK, VERDICT_VIOLATION,
    ))

    # A single-feature failure alongside a combination failure is
    # not an interaction break.
    product = _product(6, n_features=3, combine_from=4)
    cases.append((
        "not_interaction_break", "interaction_failure",
        product, _results(product, failed=("p1", "p5")),
        OVERALL_FAILED, VERDICT_PASS,
    ))

    # One ungraded plan means the delivery claim is unverified.
    product = _product(5, n_features=1)
    cases.append((
        "ungraded_one", "ungraded_plan",
        product, _results(product, ungraded=("p5",)),
        OVERALL_UNGRADED, VERDICT_VIOLATION,
    ))

    # A plan missing from the results counts as ungraded, not
    # as a pass.
    product = _product(3, n_features=1)
    cases.append((
        "ungraded_missing_from_results", "ungraded_plan",
        product, {"p1": True, "p2": True},
        OVERALL_UNGRADED, VERDICT_VIOLATION,
    ))

    # 49 passed and 1 ungraded: the rate still masks the failure.
    product = _product(50, n_features=5)
    cases.append((
        "ungraded_high_rate", "ungraded_plan",
        product, _results(product, ungraded=("p50",)),
        OVERALL_PARTIAL_CREDIT_TRAP, VERDICT_VIOLATION,
    ))

    # Interaction failure plus an ungraded plan: the interaction
    # break names the outcome.
    product = _product(10, n_features=2, combine_from=8)
    cases.append((
        "interaction_plus_ungraded", "interaction_failure",
        product,
        _results(product, failed=("p9",), ungraded=("p10",)),
        OVERALL_INTERACTION_BREAK, VERDICT_VIOLATION,
    ))

    # Every plan failed: a plain failure at rate zero.
    product = _product(4, n_features=1)
    cases.append((
        "all_plans_failed", "not_delivered",
        product,
        _results(product, failed=("p1", "p2", "p3", "p4")),
        OVERALL_FAILED, VERDICT_VIOLATION,
    ))

    # A one-plan product delivers when its plan passes.
    product = _product(1, n_features=1)
    cases.append((
        "single_plan_delivered", "not_delivered",
        product, _results(product),
        OVERALL_DELIVERED, VERDICT_PASS,
    ))

    # A one-plan product fails when its plan fails.
    product = _product(1, n_features=1)
    cases.append((
        "single_plan_failed", "not_delivered",
        product, _results(product, failed=("p1",)),
        OVERALL_FAILED, VERDICT_VIOLATION,
    ))

    # One feature broken, the other delivered: still a failed
    # build.
    product = _product(4, n_features=2)
    cases.append((
        "one_feature_broken", "not_delivered",
        product, _results(product, failed=("p2",)),
        OVERALL_FAILED, VERDICT_VIOLATION,
    ))

    # All combination plans failed at a low rate: still an
    # interaction break.
    product = _product(8, n_features=2, combine_from=4)
    cases.append((
        "all_combination_failed_low_rate", "interaction_failure",
        product,
        _results(product, failed=("p5", "p6", "p7", "p8")),
        OVERALL_INTERACTION_BREAK, VERDICT_VIOLATION,
    ))

    # A single-feature failure plus a combination failure at the
    # 90% line: the trap fires, the interaction check does not.
    product = _product(20, n_features=4)
    cases.append((
        "high_rate_mixed_failures", "partial_credit_masks_failure",
        product, _results(product, failed=("p1", "p20")),
        OVERALL_PARTIAL_CREDIT_TRAP, VERDICT_VIOLATION,
    ))

    # No grades at all: every plan ungraded, delivery unverified.
    product = _product(4, n_features=1)
    cases.append((
        "no_grades_at_all", "ungraded_plan",
        product, {},
        OVERALL_UNGRADED, VERDICT_VIOLATION,
    ))

    # Twelve plans over three features, all passing.
    product = _product(12, n_features=3)
    cases.append((
        "delivered_multi_feature", "not_delivered",
        product, _results(product),
        OVERALL_DELIVERED, VERDICT_PASS,
    ))

    # One whole feature failed: a plain failure, not an
    # interaction break (its plans are single-feature).
    product = _product(6, n_features=2)
    cases.append((
        "whole_feature_failed", "interaction_failure",
        product, _results(product, failed=("p2", "p4", "p6")),
        OVERALL_FAILED, VERDICT_PASS,
    ))

    # Three failed plans and one ungraded: ungraded names the
    # outcome, since no other diagnostic check fires.
    product = _product(4, n_features=1)
    cases.append((
        "failed_plus_ungraded", "ungraded_plan",
        product,
        _results(product, failed=("p1", "p2", "p3"),
                 ungraded=("p4",)),
        OVERALL_UNGRADED, VERDICT_VIOLATION,
    ))

    # 98% with a combination-plan failure: both the trap and the
    # interaction check fire; the trap names the outcome.
    product = _product(50, n_features=5, combine_from=40)
    cases.append((
        "high_rate_combination_failure", "partial_credit_masks_failure",
        product, _results(product, failed=("p50",)),
        OVERALL_PARTIAL_CREDIT_TRAP, VERDICT_VIOLATION,
    ))

    # 96% with a single-feature failure and an ungraded plan:
    # the trap fires, and the ungraded check fires with it.
    product = _product(50, n_features=5)
    cases.append((
        "high_rate_single_fail_plus_ungraded",
        "partial_credit_masks_failure",
        product,
        _results(product, failed=("p1",), ungraded=("p50",)),
        OVERALL_PARTIAL_CREDIT_TRAP, VERDICT_VIOLATION,
    ))

    return cases


def main():
    assert REPORTS.endswith("all-or-nothing-verify"), REPORTS
    os.makedirs(REPORTS, exist_ok=True)
    results = []
    for case in all_or_nothing_cases():
        (case_id, check, product, build_results,
         expected_outcome, expected_check) = case
        score = score_build(product, build_results)
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
    print("all-or-nothing labeled cases: %d/%d match"
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
