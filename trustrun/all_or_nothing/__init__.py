"""All-or-nothing long-horizon build scoring, adopting ViBench 2.0's
grading rule as a Trustrun Contract eval target.

Trustrun's contract module judges delivered claims against what was
AGREED. This module scores a different axis: whether a long-horizon
software BUILD is delivered. A build can satisfy the wording of its
feature requests while still not being a working product, because one
test plan somewhere failed. That is the gap ViBench 2.0 measures, and
it is the gap this module scores: partial credit (the share of test
plans that pass) against delivery (the product works end to end),
with the difference reported as the reliability gap. The consistency
module scores pass^k over repeated runs of the same task; this
module scores one build of one product against its full test-plan
suite, and a batch of builds of the same product as pass@1.

The method is ViBench 2.0's. ViBench 2.0 (Furman et al., Replit,
arXiv:2611.05620, submitted Nov 3, 2026) benchmarks long-horizon
software building: 17 full-stack web products, modeled on widely
used software, grow over 241 feature requests and are judged only
when finished, as a user would judge them: a browser agent runs
544 test plans, and a build passes only if every plan does, under
a grading protocol validated to keep this strict score reliable
(failed plans are re-graded until three of up to five grades
agree; the protocol caught all 34 planted bugs and only 0.8% of
its passes are false). Evaluating nine models, the paper finds the
reliability gap: the three strongest pass up to 98% of test plans
yet deliver a fully working product in at most 65% of builds, and
no open-weight model delivers one. Across three releases of one
model family, pass@1 on the public products rises from 3% to 53%
while the cost per build falls by more than half. Eight products
ship with the harness and grader
(github.com/ViBench/vibench-public); nine are held out. The
Replit write-up names the three strongest: GPT-6.1 Sol 65%,
GPT-6 Astra 60%, Opus 5.5 49% pass@1, all three passing more
than 90% of their test plans, and reports that nearly
three-quarters of their failed builds broke where features
interact; 85% of the 544 test plans combine features.

Four checks, each PASS or VIOLATION:

* not_delivered: the ViBench rule itself, a build passes only
  when every test plan passes. Any failed or ungraded plan means
  the product is not delivered.
* partial_credit_masks_failure: the test-plan pass rate is at
  least 90% while the product is not delivered. The 90% line is
  Trustrun's own: ViBench's strongest pass "up to 98%" of plans
  and "more than 90%", so a build above 90% that still fails
  delivery is the paper's headline case. Below the line the
  failure is plain, not masked.
* interaction_failure: the build failed and every failed plan
  combines features, while every single-feature plan passed.
  The build broke only where features interact, the failure
  mode behind nearly three-quarters of the strongest models'
  failed ViBench builds.
* ungraded_plan: at least one test plan has no recorded grade
  (never run, or missing from the results). An ungraded plan is
  not a pass, so the delivery claim is unverified, never
  delivered. This is the same rule the grader-sabotage probe
  applies to crashed attempts: no grade, no pass.

Rates are reported as signals, not checks: the test-plan pass
rate (passed plans over all plans, ungraded plans counting as
not passed), the per-feature delivery rate, and the delivery
gap, the plan pass rate minus the delivery rate (1 when the
product is delivered, 0 when it is not). A batch of builds of
the same product also reports pass@1, the share of builds in
which every test plan passes, the ViBench headline metric, and
the mean delivery gap across the batch.

Prior art, stated plainly: the all-or-nothing rule, the grading
protocol, the 98%-vs-65% gap, and the pass@1 numbers are
ViBench 2.0's, and this module does not claim them. The
benchmark itself (vibench-public) runs its eight public
products through a browser-agent grader; this module is a
scorer for recorded build results, not the benchmark: it never
runs a product, never grades a plan itself, and takes the
caller's grades as given. SWE-bench Verified and Terminal-Bench
grade single fully specified tasks, not a product grown over
feature requests, so they cannot produce the partial-credit
gap. No shipped stdlib-only all-or-nothing build scorer fused
into a trust report was found.

Honest limits, read before quoting any number from this module:
this scores recorded grades, nothing more. It cannot tell
whether a plan grade is correct: a wrong pass stands, exactly
as in ViBench, where passed plans are not graded again and a
second grader puts wrong passes at 0.8%. It cannot tell whether
a real model would deliver a real product; a build that passes
every recorded plan is delivered under the grades given, not
certified working. In Trustrun's clean-room evals the grades
are scripted, so the verdicts measure the scoring logic
against known cases, not real-model behavior. A PASS verdict
is a statement about one build's recorded grades, not a
shipping certification. The module never executes code and
never touches a network; the "products", "features", and
"plans" it names are strings in a caller-supplied spec.
"""

# Overall verdicts.
VERDICT_BLOCK = "BLOCK"
VERDICT_PASS = "PASS"

# Per-check verdicts.
VERDICT_VIOLATION = "VIOLATION"

# Overall outcomes, worst first for reporting.
OVERALL_PARTIAL_CREDIT_TRAP = "partial_credit_trap"
OVERALL_INTERACTION_BREAK = "interaction_break"
OVERALL_UNGRADED = "ungraded"
OVERALL_FAILED = "failed"
OVERALL_DELIVERED = "delivered"

# Trustrun's own line for the partial-credit trap: ViBench's
# strongest pass "up to 98%" of test plans and "more than 90%",
# so a build above 90% that still fails delivery is the paper's
# headline case.
PARTIAL_CREDIT_LINE = 0.90

CHECKS = (
    {
        "id": "not_delivered",
        "name": "Build not delivered: a test plan did not pass",
        "incident": "ViBench 2.0: a build passes only if every "
        "plan does (arXiv:2611.05620)",
    },
    {
        "id": "partial_credit_masks_failure",
        "name": "High plan pass rate hides a failed delivery",
        "incident": "ViBench 2.0: the three strongest pass up to "
        "98% of test plans yet deliver a fully working product "
        "in at most 65% of builds (arXiv:2611.05620)",
    },
    {
        "id": "interaction_failure",
        "name": "Build failed only where features interact",
        "incident": "ViBench 2.0: nearly three-quarters of the "
        "strongest models' failed builds broke where features "
        "interact (arXiv:2611.05620)",
    },
    {
        "id": "ungraded_plan",
        "name": "A test plan has no recorded grade",
        "incident": "ViBench 2.0: passed plans are not graded "
        "again, so an ungraded plan is unverified, never a pass "
        "(arXiv:2611.05620)",
    },
)

CHECK_IDS = tuple(c["id"] for c in CHECKS)


def _validate_product(product):
    """Validate the product spec and return its plan list. A plan
    is a dict with a string "id", an optional string "feature",
    and an optional boolean "combines_features" (default False).
    Duplicate plan ids and an empty plan list are spec errors."""
    if not isinstance(product, dict):
        raise TypeError("product must be a dict")
    plans = product.get("plans")
    if not isinstance(plans, list):
        raise TypeError("product plans must be a list")
    if not plans:
        raise ValueError("product has no test plans")
    seen = set()
    for index, plan in enumerate(plans):
        if not isinstance(plan, dict):
            raise TypeError("plan %d must be a dict" % index)
        plan_id = plan.get("id")
        if not isinstance(plan_id, str) or not plan_id:
            raise TypeError(
                "plan %d must carry a non-empty string id" % index
            )
        if plan_id in seen:
            raise ValueError("duplicate plan id %r" % plan_id)
        seen.add(plan_id)
        feature = plan.get("feature", "")
        if not isinstance(feature, str):
            raise TypeError(
                "plan %r feature must be a string" % plan_id
            )
        combines = plan.get("combines_features", False)
        if not isinstance(combines, bool):
            raise TypeError(
                "plan %r combines_features must be a boolean"
                % plan_id
            )
    return plans


def _validate_results(results, plan_ids):
    """Validate the build results: a dict from plan id to True
    (passed), False (failed), or None (ungraded). A result for an
    unknown plan id is a data error. A plan missing from the
    results was never graded, so it reads as ungraded, not as a
    pass."""
    if not isinstance(results, dict):
        raise TypeError("results must be a dict from plan id to grade")
    for plan_id, grade in results.items():
        if plan_id not in plan_ids:
            raise ValueError("result for unknown plan id %r" % plan_id)
        if grade is not None and not isinstance(grade, bool):
            raise TypeError(
                "grade for plan %r must be True, False, or None"
                % plan_id
            )
    return {plan_id: results.get(plan_id) for plan_id in plan_ids}


def score_build(product, results):
    """Score one long-horizon build under ViBench 2.0's
    all-or-nothing rule.

    product: a dict with a "plans" list; each plan is a dict
    with a string "id", an optional string "feature", and an
    optional boolean "combines_features".
    results: a dict from plan id to True (passed), False
    (failed), or None (ungraded). A plan missing from the
    results counts as ungraded.

    Returns a dict with the overall verdict (BLOCK when any
    check is VIOLATION, else PASS), the outcome, the delivery
    flag, the plan pass rate, the delivery gap, per-feature
    verdicts, per-plan records, and the per-check verdicts
    with evidence.
    """
    plans = _validate_product(product)
    plan_ids = [plan["id"] for plan in plans]
    grades = _validate_results(results, set(plan_ids))

    total = len(plans)
    passed = sum(1 for plan_id in plan_ids if grades[plan_id] is True)
    failed = sum(
        1 for plan_id in plan_ids if grades[plan_id] is False
    )
    ungraded = sum(
        1 for plan_id in plan_ids if grades[plan_id] is None
    )
    plan_pass_rate = passed / total if total else 0.0
    delivered = passed == total

    # The delivery gap: the plan pass rate minus the delivery
    # rate (1 when delivered, 0 when not). A build at 98% of
    # plans with no delivery carries a 0.98 gap: almost every
    # plan passed, and the user still has no working product.
    delivery_gap = plan_pass_rate - (1.0 if delivered else 0.0)

    plan_records = []
    for plan in plans:
        grade = grades[plan["id"]]
        plan_records.append({
            "id": plan["id"],
            "feature": plan.get("feature", ""),
            "combines_features": plan.get("combines_features", False),
            "grade": grade,
            "passed": grade is True,
        })

    features = {}
    for record in plan_records:
        feature = record["feature"]
        entry = features.setdefault(feature, {
            "feature": feature,
            "plans": 0,
            "passed": 0,
            "delivered": True,
        })
        entry["plans"] += 1
        if record["passed"]:
            entry["passed"] += 1
        else:
            entry["delivered"] = False
    feature_list = [features[name] for name in sorted(features)]
    features_delivered = sum(
        1 for entry in feature_list if entry["delivered"]
    )

    failed_plans = [
        record for record in plan_records if record["grade"] is False
    ]
    ungraded_plans = [
        record for record in plan_records if record["grade"] is None
    ]

    per_check = {}
    for check in CHECKS:
        per_check[check["id"]] = {"verdict": VERDICT_PASS,
                                  "evidence": None}

    if not delivered:
        per_check["not_delivered"]["verdict"] = VERDICT_VIOLATION
        per_check["not_delivered"]["evidence"] = {
            "plans": [record["id"] for record in plan_records
                      if not record["passed"]],
            "detail": "%d of %d test plans passed; a build passes "
            "only if every plan does" % (passed, total),
        }

    if not delivered and plan_pass_rate >= PARTIAL_CREDIT_LINE:
        per_check["partial_credit_masks_failure"]["verdict"] = (
            VERDICT_VIOLATION
        )
        per_check["partial_credit_masks_failure"]["evidence"] = {
            "plans": [record["id"] for record in plan_records
                      if not record["passed"]],
            "detail": "plan pass rate %.2f at or above %.2f, "
            "yet the product is not delivered"
            % (plan_pass_rate, PARTIAL_CREDIT_LINE),
        }

    if (
        not delivered
        and failed_plans
        and all(
            record["combines_features"] for record in failed_plans
        )
    ):
        per_check["interaction_failure"]["verdict"] = (
            VERDICT_VIOLATION
        )
        per_check["interaction_failure"]["evidence"] = {
            "plans": [record["id"] for record in failed_plans],
            "detail": "all %d failed plans combine features; "
            "every single-feature plan passed"
            % len(failed_plans),
        }

    if ungraded_plans:
        per_check["ungraded_plan"]["verdict"] = VERDICT_VIOLATION
        per_check["ungraded_plan"]["evidence"] = {
            "plans": [record["id"] for record in ungraded_plans],
            "detail": "%d of %d test plans have no recorded grade"
            % (len(ungraded_plans), total),
        }

    passed_checks = sum(
        1
        for check in CHECKS
        if per_check[check["id"]]["verdict"] == VERDICT_PASS
    )
    verdict = (
        VERDICT_BLOCK if passed_checks < len(CHECKS) else VERDICT_PASS
    )
    if delivered:
        outcome = OVERALL_DELIVERED
    elif per_check["partial_credit_masks_failure"]["verdict"] == (
        VERDICT_VIOLATION
    ):
        outcome = OVERALL_PARTIAL_CREDIT_TRAP
    elif per_check["interaction_failure"]["verdict"] == (
        VERDICT_VIOLATION
    ):
        outcome = OVERALL_INTERACTION_BREAK
    elif per_check["ungraded_plan"]["verdict"] == VERDICT_VIOLATION:
        outcome = OVERALL_UNGRADED
    else:
        outcome = OVERALL_FAILED
    return {
        "verdict": verdict,
        "outcome": outcome,
        "delivered": delivered,
        "plan_pass_rate": plan_pass_rate,
        "delivery_gap": delivery_gap,
        "plan_count": total,
        "plans_passed": passed,
        "plans_failed": failed,
        "plans_ungraded": ungraded,
        "feature_count": len(feature_list),
        "features_delivered": features_delivered,
        "features": feature_list,
        "plans": plan_records,
        "checks": per_check,
        "pass_count": passed_checks,
        "check_count": len(CHECKS),
        "pass_rate": passed_checks / len(CHECKS),
    }


def score_batch(product, builds):
    """Score a batch of builds of the same product, the ViBench
    pass@1 axis: the share of builds in which every test plan
    passes, averaged over the batch, plus the mean plan pass rate
    and the mean delivery gap. builds is a list of result dicts,
    one per build, each in the score_build results shape. An
    empty batch is a caller error."""
    if not isinstance(builds, list):
        raise TypeError("builds must be a list of result dicts")
    if not builds:
        raise ValueError("batch has no builds")
    scores = [score_build(product, results) for results in builds]
    delivered_count = sum(
        1 for score in scores if score["delivered"]
    )
    pass_at_1 = delivered_count / len(scores)
    mean_plan_rate = sum(
        score["plan_pass_rate"] for score in scores
    ) / len(scores)
    mean_gap = sum(
        score["delivery_gap"] for score in scores
    ) / len(scores)
    return {
        "build_count": len(scores),
        "builds_delivered": delivered_count,
        "pass_at_1": pass_at_1,
        "mean_plan_pass_rate": mean_plan_rate,
        "mean_delivery_gap": mean_gap,
        "outcomes": [score["outcome"] for score in scores],
        "builds": scores,
    }


def build_all_or_nothing_report(agent_name, product_name, product,
                                results):
    """Wrap score_build with the agent and product it describes."""
    score = score_build(product, results)
    return {
        "agent": agent_name,
        "product": product_name,
        "verdict": score["verdict"],
        "outcome": score["outcome"],
        "delivered": score["delivered"],
        "plan_pass_rate": score["plan_pass_rate"],
        "delivery_gap": score["delivery_gap"],
        "plan_count": score["plan_count"],
        "plans_passed": score["plans_passed"],
        "plans_failed": score["plans_failed"],
        "plans_ungraded": score["plans_ungraded"],
        "feature_count": score["feature_count"],
        "features_delivered": score["features_delivered"],
        "features": score["features"],
        "plans": score["plans"],
        "pass_rate": score["pass_rate"],
        "pass_count": score["pass_count"],
        "check_count": score["check_count"],
        "checks": score["checks"],
    }


def format_summary(report):
    """One paragraph: outcome, verdict, what went wrong."""
    bad = [
        check_id
        for check_id in CHECK_IDS
        if report["checks"][check_id]["verdict"] != VERDICT_PASS
    ]
    if bad:
        bad_text = "failure: " + ", ".join(
            "%s (%s)"
            % (
                check_id,
                report["checks"][check_id]["verdict"],
            )
            for check_id in bad
        )
    else:
        bad_text = "no failure recorded"
    return (
        "All-or-nothing build for %s on %s: %s (%s). %d of %d "
        "test plans passed (rate %.2f), %d of %d features "
        "delivered, delivery gap %.2f. Passed %d of %d checks. "
        "%s."
        % (
            report["agent"],
            report["product"],
            report["outcome"],
            report["verdict"],
            report["plans_passed"],
            report["plan_count"],
            report["plan_pass_rate"],
            report["features_delivered"],
            report["feature_count"],
            report["delivery_gap"],
            report["pass_count"],
            report["check_count"],
            bad_text,
        )
    )


def format_batch_summary(batch):
    """One paragraph for a batch: pass@1 against the plan rate."""
    return (
        "All-or-nothing batch: %d builds, %d delivered, pass@1 "
        "%.2f, mean plan pass rate %.2f, mean delivery gap %.2f."
        % (
            batch["build_count"],
            batch["builds_delivered"],
            batch["pass_at_1"],
            batch["mean_plan_pass_rate"],
            batch["mean_delivery_gap"],
        )
    )
