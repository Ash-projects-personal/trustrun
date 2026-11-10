"""Task-turnover (preservation) scoring for agent versions, adopting
"Beneath the Surface" (Wang et al., arXiv:2611.07624, Nov 5, 2026)
as a Trustrun Consistency eval target.

Trustrun's consistency module scores pass^k over repeated runs of
the SAME agent version on the same task: does it do it every time.
This module scores a different axis: when the agent version
CHANGES, does the new version keep what the old version could
do. A version can improve its headline score while losing tasks
it used to pass, and a headline delta alone cannot see that.
That is the gap "Beneath the Surface" measures, and it is the
gap this module scores: task turnover (gains minus regressions)
reported next to the headline delta, so an improvement that
loses covered tasks is scored as what it is.

The method is the paper's turnover accounting. The paper
evaluates four harness-evolution methods (AHE, HyperAgents,
A-Evolve, GEPA) with MiniSWE and Codex on general and coding
tasks, using repeated evaluations and Avg@k (reliability) against
Pass@k (coverage). Its finding: all sixteen evolved agents gained
previously uncovered tasks while losing previously covered ones.
In one general-task case reliability rose by 5.2 points despite
losing ten previously covered tasks. Most reliability gains also
increased deployment cost. The highest-scoring agent did not yield
the largest mean improvement in any of four pools, and stricter
admission can discard useful alternatives. The paper's follow-up
method, EvoAudit, revises select, analyze, mutate, and gate
around preservation. The paper's code is RSIHub
(github.com/simple-agent-lab/RSIHub).

Four checks, each PASS or VIOLATION:

* regression: at least one task the baseline version passed, the
  new version fails. A lost covered task, whatever the headline
  says.
* headline_masks_regression: the headline pass rate did not fall
  (it rose, or stayed flat because gains offset the losses)
  while regressions exist. The paper's headline case is a
  reliability rise of 5.2 points alongside ten lost tasks; the
  flat case is the same shape with the gains exactly covering
  the losses, so the headline says "no change" while covered
  tasks were lost.
* net_negative_turnover: regressions outnumber gains, so the new
  version covers fewer tasks than the baseline. A headline fall
  always means this (a fall needs more regressions than gains),
  so this check names the outcome when the headline does fall.
* costly_reliability_gain: reliability rose while the mean cost
  per task also rose. The paper reports most reliability gains
  also increased deployment cost; a gain bought with higher cost
  is a tradeoff the report should name, not a clean win. This
  check only runs when the caller supplies per-task costs for
  both versions; without cost data it is not evaluated and stays
  PASS with that noted in its evidence.

Rates are reported as signals, not checks: the baseline and new
pass rates, the headline delta, the gain and regression counts,
the net turnover (gains minus regressions), the turnover rate
(tasks that changed status, gained or regressed, over all tasks),
and the mean cost per task on each side with the cost delta when
costs are supplied. Per-task records name every task's class:
gained, regressed, preserved, or still_failed.

Prior art, stated plainly: the turnover accounting, the 16-agent
finding, the 5.2-point rise with ten lost tasks, and the
cost pattern are the paper's, and this module does not claim
them. RSIHub is the paper's evolution framework with shared
evaluation and lineage tracking; this module is a scorer for
two recorded evaluation snapshots, not the framework: it never
evolves an agent and never runs a task. "The Regression Tax"
(Jul 2026) decomposes skill effects into regressions (previously
passing tasks that now fail) and residual failures across nearly
6,000 runs, and recommends measuring newly solved and
previously passing tasks separately; it is a measurement study
of skills, not a version audit. "Learning to Solve, Forgetting
to Retain" (arXiv:2606.03087) frames the same dynamics as
correct-set turnover inside RL training and proposes ReMind, a
retention-aware review mechanism; it is a training method, not
an audit probe for deployed agent versions. EvoAudit is the
paper's own proposed follow-up; this module implements the
audit side of its gate (score the turnover, flag the masked
improvement), not EvoAudit itself. No shipped stdlib-only
task-turnover audit fused into a trust report was found.

Honest limits, read before quoting any number from this module:
this scores two recorded snapshots, nothing more. A task is
covered when its recorded outcome passes; the module cannot
tell whether a recorded pass was earned or gamed, and it cannot
tell whether a real model would keep a real task. A task set
that differs between the two snapshots is a caller error, not
a turnover: turnover is only defined over a fixed task set, so
mismatched sets are rejected rather than silently aligned. A
cost rise with flat or falling reliability is reported in the
signals, not a check: the paper's cost pattern is about gains
that cost more, and a version that costs more while doing worse
is already BLOCKed by its regressions. In Trustrun's clean-room
evals the snapshots are scripted, so the verdicts measure the
scoring logic against known cases, not real-model behavior. A
PASS verdict is a statement about two recorded snapshots, not a
shipping certification. The module never executes code and never
touches a network; the "tasks" and "versions" it names are
strings and booleans in caller-supplied dicts.
"""

# Overall verdicts.
VERDICT_BLOCK = "BLOCK"
VERDICT_PASS = "PASS"

# Per-check verdicts.
VERDICT_VIOLATION = "VIOLATION"

# Overall outcomes, worst first for reporting.
OVERALL_MASKED_IMPROVEMENT = "masked_improvement"
OVERALL_NET_REGRESSION = "net_regression"
OVERALL_COSTLY_GAIN = "costly_gain"
OVERALL_CLEAN_IMPROVEMENT = "clean_improvement"
OVERALL_UNCHANGED = "unchanged"

# Per-task turnover classes.
CLASS_GAINED = "gained"
CLASS_REGRESSED = "regressed"
CLASS_PRESERVED = "preserved"
CLASS_STILL_FAILED = "still_failed"

CHECKS = (
    {
        "id": "regression",
        "name": "A previously covered task was lost",
        "incident": "Beneath the Surface: all sixteen evolved "
        "agents lost previously covered tasks (arXiv:2611.07624)",
    },
    {
        "id": "headline_masks_regression",
        "name": "Headline did not fall while covered tasks "
        "were lost",
        "incident": "Beneath the Surface: reliability rose by "
        "5.2 points despite losing ten previously covered tasks "
        "(arXiv:2611.07624)",
    },
    {
        "id": "net_negative_turnover",
        "name": "Regressions outnumber gains",
        "incident": "Beneath the Surface: task-turnover "
        "accounting, gains minus regressions (arXiv:2611.07624)",
    },
    {
        "id": "costly_reliability_gain",
        "name": "Reliability rose while mean cost per task rose",
        "incident": "Beneath the Surface: most reliability "
        "gains also increased deployment cost "
        "(arXiv:2611.07624)",
    },
)

CHECK_IDS = tuple(c["id"] for c in CHECKS)


def _validate_snapshot(snapshot, name):
    """Validate one evaluation snapshot: a dict from task id to
    a boolean (True passed, False failed). An empty snapshot and
    a non-boolean outcome are caller errors."""
    if not isinstance(snapshot, dict):
        raise TypeError("%s must be a dict from task id to bool"
                        % name)
    if not snapshot:
        raise ValueError("%s has no tasks" % name)
    for task_id, outcome in snapshot.items():
        if not isinstance(task_id, str) or not task_id:
            raise TypeError(
                "%s task ids must be non-empty strings" % name
            )
        if not isinstance(outcome, bool):
            raise TypeError(
                "%s outcome for task %r must be True or False"
                % (name, task_id)
            )
    return snapshot


def _validate_costs(costs, task_ids, name):
    """Validate one per-task cost dict: a dict from task id to a
    number, covering exactly the snapshot's task set. A missing
    task or an unknown task is a caller error; costs are only
    compared when both sides supply them."""
    if costs is None:
        return None
    if not isinstance(costs, dict):
        raise TypeError("%s must be a dict from task id to number"
                        % name)
    for task_id, cost in costs.items():
        if task_id not in task_ids:
            raise ValueError(
                "%s has a cost for unknown task %r" % (name, task_id)
            )
        if not isinstance(cost, (int, float)) or isinstance(
            cost, bool
        ):
            raise TypeError(
                "%s cost for task %r must be a number"
                % (name, task_id)
            )
    missing = [task_id for task_id in task_ids
               if task_id not in costs]
    if missing:
        raise ValueError(
            "%s is missing costs for tasks %s" % (name, missing)
        )
    return costs


def score_turnover(baseline, new, baseline_costs=None,
                   new_costs=None):
    """Score the turnover between two recorded evaluation
    snapshots of the same agent over the same task set.

    baseline: dict from task id to True (passed) or False
      (failed) for the old version.
    new: the same shape for the new version. The task sets
      must match exactly; a task present in one snapshot and
      absent from the other is a caller error, because turnover
      is only defined over a fixed task set.
    baseline_costs, new_costs: optional dicts from task id to a
      number (cost per task, same units on both sides). The
      cost check only runs when both are supplied; supplying
      costs for only one snapshot is a caller error.

    Returns a dict with the overall verdict (BLOCK when any
    check is VIOLATION, else PASS), the outcome, the headline
    rates and delta, the turnover counts, the per-task records,
    the mean costs when supplied, and the per-check verdicts
    with evidence.
    """
    _validate_snapshot(baseline, "baseline")
    _validate_snapshot(new, "new")
    baseline_ids = set(baseline)
    new_ids = set(new)
    if baseline_ids != new_ids:
        only_baseline = sorted(baseline_ids - new_ids)
        only_new = sorted(new_ids - baseline_ids)
        raise ValueError(
            "snapshots cover different task sets: only in "
            "baseline %s, only in new %s"
            % (only_baseline, only_new)
        )
    baseline_costs = _validate_costs(
        baseline_costs, baseline_ids, "baseline_costs"
    )
    new_costs = _validate_costs(
        new_costs, baseline_ids, "new_costs"
    )
    if (baseline_costs is None) != (new_costs is None):
        raise ValueError(
            "costs must be supplied for both snapshots or "
            "neither; one side is missing"
        )

    task_ids = sorted(baseline_ids)
    total = len(task_ids)
    baseline_passed = sum(
        1 for task_id in task_ids if baseline[task_id] is True
    )
    new_passed = sum(
        1 for task_id in task_ids if new[task_id] is True
    )
    baseline_rate = baseline_passed / total
    new_rate = new_passed / total
    headline_delta = new_rate - baseline_rate

    records = []
    gains = 0
    regressions = 0
    preserved = 0
    still_failed = 0
    for task_id in task_ids:
        old = baseline[task_id]
        current = new[task_id]
        if old is False and current is True:
            task_class = CLASS_GAINED
            gains += 1
        elif old is True and current is False:
            task_class = CLASS_REGRESSED
            regressions += 1
        elif old is True and current is True:
            task_class = CLASS_PRESERVED
            preserved += 1
        else:
            task_class = CLASS_STILL_FAILED
            still_failed += 1
        records.append({
            "id": task_id,
            "baseline": old,
            "new": current,
            "class": task_class,
        })

    net_turnover = gains - regressions
    turnover_rate = (gains + regressions) / total if total else 0.0

    mean_baseline_cost = None
    mean_new_cost = None
    cost_delta = None
    costs_supplied = (
        baseline_costs is not None and new_costs is not None
    )
    if costs_supplied:
        mean_baseline_cost = sum(
            baseline_costs[task_id] for task_id in task_ids
        ) / total
        mean_new_cost = sum(
            new_costs[task_id] for task_id in task_ids
        ) / total
        cost_delta = mean_new_cost - mean_baseline_cost

    per_check = {}
    for check in CHECKS:
        per_check[check["id"]] = {"verdict": VERDICT_PASS,
                                  "evidence": None}

    if regressions:
        per_check["regression"]["verdict"] = VERDICT_VIOLATION
        per_check["regression"]["evidence"] = {
            "tasks": [record["id"] for record in records
                      if record["class"] == CLASS_REGRESSED],
            "detail": "%d of %d tasks passed by the baseline "
            "version fail under the new version"
            % (regressions, total),
        }

    if regressions and headline_delta >= 0:
        per_check["headline_masks_regression"]["verdict"] = (
            VERDICT_VIOLATION
        )
        per_check["headline_masks_regression"]["evidence"] = {
            "tasks": [record["id"] for record in records
                      if record["class"] == CLASS_REGRESSED],
            "detail": "headline pass rate moved %+.2f while %d "
            "previously covered tasks were lost"
            % (headline_delta, regressions),
        }

    if regressions > gains:
        per_check["net_negative_turnover"]["verdict"] = (
            VERDICT_VIOLATION
        )
        per_check["net_negative_turnover"]["evidence"] = {
            "tasks": [record["id"] for record in records
                      if record["class"] == CLASS_REGRESSED],
            "detail": "%d regressions against %d gains: net "
            "turnover %d, the new version covers fewer tasks"
            % (regressions, gains, net_turnover),
        }

    if costs_supplied:
        if headline_delta > 0 and cost_delta > 0:
            per_check["costly_reliability_gain"]["verdict"] = (
                VERDICT_VIOLATION
            )
            per_check["costly_reliability_gain"]["evidence"] = {
                "tasks": [],
                "detail": "reliability rose %+.2f while mean "
                "cost per task rose %+.4f"
                % (headline_delta, cost_delta),
            }
        else:
            per_check["costly_reliability_gain"]["evidence"] = {
                "tasks": [],
                "detail": "cost data supplied; mean cost per "
                "task moved %+.4f with headline delta %+.2f"
                % (cost_delta, headline_delta),
            }
    else:
        per_check["costly_reliability_gain"]["evidence"] = {
            "tasks": [],
            "detail": "no cost data supplied; the cost check "
            "was not evaluated",
        }

    passed_checks = sum(
        1
        for check in CHECKS
        if per_check[check["id"]]["verdict"] == VERDICT_PASS
    )
    verdict = (
        VERDICT_BLOCK if passed_checks < len(CHECKS) else VERDICT_PASS
    )
    if per_check["headline_masks_regression"]["verdict"] == (
        VERDICT_VIOLATION
    ):
        outcome = OVERALL_MASKED_IMPROVEMENT
    elif per_check["net_negative_turnover"]["verdict"] == (
        VERDICT_VIOLATION
    ):
        outcome = OVERALL_NET_REGRESSION
    elif per_check["costly_reliability_gain"]["verdict"] == (
        VERDICT_VIOLATION
    ):
        outcome = OVERALL_COSTLY_GAIN
    elif gains == 0 and regressions == 0:
        outcome = OVERALL_UNCHANGED
    else:
        outcome = OVERALL_CLEAN_IMPROVEMENT
    return {
        "verdict": verdict,
        "outcome": outcome,
        "task_count": total,
        "baseline_passed": baseline_passed,
        "new_passed": new_passed,
        "baseline_pass_rate": baseline_rate,
        "new_pass_rate": new_rate,
        "headline_delta": headline_delta,
        "gains": gains,
        "regressions": regressions,
        "preserved": preserved,
        "still_failed": still_failed,
        "net_turnover": net_turnover,
        "turnover_rate": turnover_rate,
        "mean_baseline_cost": mean_baseline_cost,
        "mean_new_cost": mean_new_cost,
        "cost_delta": cost_delta,
        "costs_supplied": costs_supplied,
        "tasks": records,
        "checks": per_check,
        "pass_count": passed_checks,
        "check_count": len(CHECKS),
        "pass_rate": passed_checks / len(CHECKS),
    }


def build_preservation_aware_report(agent_name, baseline_name,
                                    new_name, baseline, new,
                                    baseline_costs=None,
                                    new_costs=None):
    """Wrap score_turnover with the agent and the two versions
    it compares."""
    score = score_turnover(
        baseline, new, baseline_costs, new_costs
    )
    return {
        "agent": agent_name,
        "baseline_version": baseline_name,
        "new_version": new_name,
        "verdict": score["verdict"],
        "outcome": score["outcome"],
        "task_count": score["task_count"],
        "baseline_passed": score["baseline_passed"],
        "new_passed": score["new_passed"],
        "baseline_pass_rate": score["baseline_pass_rate"],
        "new_pass_rate": score["new_pass_rate"],
        "headline_delta": score["headline_delta"],
        "gains": score["gains"],
        "regressions": score["regressions"],
        "preserved": score["preserved"],
        "still_failed": score["still_failed"],
        "net_turnover": score["net_turnover"],
        "turnover_rate": score["turnover_rate"],
        "mean_baseline_cost": score["mean_baseline_cost"],
        "mean_new_cost": score["mean_new_cost"],
        "cost_delta": score["cost_delta"],
        "costs_supplied": score["costs_supplied"],
        "tasks": score["tasks"],
        "pass_rate": score["pass_rate"],
        "pass_count": score["pass_count"],
        "check_count": score["check_count"],
        "checks": score["checks"],
    }


def format_summary(report):
    """One paragraph: outcome, verdict, what changed."""
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
        "Preservation audit for %s (%s -> %s): %s (%s). "
        "Headline pass rate %.2f -> %.2f (%+.2f): %d gains, %d "
        "regressions, net turnover %+d, %d preserved. Passed %d "
        "of %d checks. %s."
        % (
            report["agent"],
            report["baseline_version"],
            report["new_version"],
            report["outcome"],
            report["verdict"],
            report["baseline_pass_rate"],
            report["new_pass_rate"],
            report["headline_delta"],
            report["gains"],
            report["regressions"],
            report["net_turnover"],
            report["preserved"],
            report["pass_count"],
            report["check_count"],
            bad_text,
        )
    )
