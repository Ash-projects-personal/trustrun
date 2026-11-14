"""Failure-cause receipt: why a run failed, and what to do about it.

Teams burn agent budget on the wrong fix because failure predictors
grade the task, not the run. Shi and Assuncao, "Hard Issue, Weak
Model, or Bad Run? Rethinking Failure Prediction for Coding Agents"
(arXiv:2611.08285, submitted Nov 5 2026; abstract read in full this
run): on public SWE-bench Verified trajectories, 500 issues, 3,492
runs, 7 models, 994 failures, a difficulty-only reference score
that never looks at the run reaches 0.92 pooled AUROC, while
trajectory predictors reach about 0.62. Of 494,109 failed/successful
pairs in the test folds, 99.66% compare different issues. Within an
issue, knowing which model ran predicts failure better than the
predictors do (model identity 0.72 within-issue AUROC, predictors
0.60-0.61; detailed counts via the dev.to summary of the paper,
read this run). What the trajectory adds beyond issue difficulty and
model ability is statistically equivalent to zero in all 18
configurations tested. The repeated-run pilot (522 issues) splits
the variation into 53% issue difficulty, 42% run-to-run, and 4.6%
model-issue; 45% of failures sit on 64 issues no model solves; the
best single model solves 76.8%, any-model 86.8%; per-issue model
switching gains nothing on held-out runs. The paper calls for
failure prediction evaluated on repeated-run benchmarks in
closed-loop equal-budget settings. A companion study (Esfandyari
Doulabi et al., arXiv:2610.05572) reaches the same shape
independently: a difficulty oracle up to 0.945 pooled AUROC with
more than 99.93% of pairs cross-unit, while early stopping only
pays once within-task AUROC reaches roughly 0.84-0.93, far above
the 0.50-0.55 observed for early monitors.

This module is the decision layer the paper calls for, as a
receipt over recorded runs. Given a failed run plus three facts
the paper shows actually matter - how hard the issue is for other
models, how good this model is, and whether repeated runs of the
same issue and model disagree - it attributes the failure to one
of four causes and routes one recovery decision under an equal
token budget: retry the same model, switch to another model,
escalate to a human, or (never chosen by this router) abandon.
The campaign scores the router against three baselines at the
same budget: always retry, always switch, and the trajectory-flag
rule (retry whatever the trajectory predictor flagged, which the
paper shows grades the task, not the run).

A run is a dict with "outcome" ("failed" or "passed") and any of:
"issue_difficulty" (share of OTHER models or runs that failed this
issue, 0 to 1, or None when unknown), "model_pass_rate" (this
model's pass rate on comparable issues, or None), "best_other_
pass_rate" (the best other model's pass rate on THIS issue, or
None), "repeat_outcomes" (a list of booleans, one per repeated run
of the same issue and model, True when that repeat solved it, or
None), "other_model_outcome" (whether the best other model solves
this issue, True/False/None), "trajectory_flag" (whether a
trajectory predictor flagged this run, True/False/None), and
"tokens" (agent tokens spent on the run, 0 when absent).

Attribution, in priority order. A repeated run that solved the
issue is direct observation that the run itself was the variable,
so it beats the population statistics: any True in
repeat_outcomes attributes "bad_run". Otherwise, an issue no
model solves is the issue's fault: issue_difficulty at or above
DIFFICULTY_BAR (0.9, Trustrun's chosen bar; the paper's unsolved
issues sit at 1.0) attributes "issue_difficulty". Otherwise, a
model beaten by a wide margin on this exact issue is the model's
fault: best_other_pass_rate minus model_pass_rate at or above
ABILITY_GAP_BAR (0.25, Trustrun's chosen bar) attributes
"model_ability". Anything else attributes "unknown": no evidence
for any cause, and the receipt says so instead of guessing. A run
whose outcome is not "failed" attributes "not_a_failure". Missing
fields are skipped, never assumed: a cause is attributed only on
evidence present in the record.

Routing. "bad_run" routes "retry": the same model solved this
issue in another attempt, so a fresh run is the cheapest recovery.
"model_ability" routes "switch": another model has a materially
better record on this issue. "issue_difficulty" and "unknown"
route "escalate": retrying or switching an issue no model solves
wastes budget (the paper: switching gains nothing, and 45% of
failures sit on unsolvable issues), and with no evidence for any
cause the fail-closed choice is a human, not another blind
attempt. Escalation never recovers inside the agent budget: it
hands the run to a human, so the campaign counts it as not
recovered by the agent, at zero agent tokens. A passed run
attributes "not_a_failure" with no decision; a run with no
recorded outcome attributes "unknown", never an assumed pass.

Campaign. score_campaign runs the router and the three baselines
over the failed runs, each strategy allowed at most one extra
attempt per failed run, so the budget is equal by construction.
Recovery is read off the labeled record, never assumed: a retry
recovers when a repeat solved the issue, a switch recovers when
the best other model solves it. Tokens spent are the run's own
tokens per attempt; tokens spent on attempts that did not
recover are wasted tokens. The campaign verdict is READY when
every failed run has a known cause and the router recovers at
least as many runs as the best baseline at no more waste; it is
REVIEW when any failure is unattributed, or the router loses to
a baseline on recovery or waste. An empty campaign is REVIEW
with the evidence saying so: a receipt over no runs proves
nothing.

Honest limits, read before quoting any number from this module:
it scores recorded runs, nothing more. The attribution is only
as good as the three facts it is given: without repeat outcomes
it cannot tell a bad run from a hard issue, and without another
model's record on the same issue it cannot tell model ability
from anything else. The 0.9 and 0.25 bars are Trustrun's chosen
bars, not the paper's: the paper reports the population numbers,
not thresholds. The recovery simulation is deterministic
bookkeeping over labeled repeat outcomes, not a live re-run: a
retry that "recovers" in the receipt is a repeat that already
solved the issue in the record. The trajectory-flag baseline
retries exactly what the flag says; a flag that correlates with
difficulty wastes budget by design, which is the paper's point,
not a straw man. A PASS / READY verdict is a statement about
the recorded runs, not a certification of the agent.
"""

CAUSE_BAD_RUN = "bad_run"
CAUSE_ISSUE_DIFFICULTY = "issue_difficulty"
CAUSE_MODEL_ABILITY = "model_ability"
CAUSE_UNKNOWN = "unknown"
CAUSE_NOT_A_FAILURE = "not_a_failure"

DECISION_RETRY = "retry"
DECISION_SWITCH = "switch"
DECISION_ESCALATE = "escalate"
DECISION_NONE = "none"

# Trustrun's chosen bars, documented in the module docstring.
# DIFFICULTY_BAR: an issue at or above this difficulty is treated
# as unsolvable in practice (the paper's unsolved issues sit at
# 1.0). ABILITY_GAP_BAR: the margin by which the best other model
# must beat this model on the same issue for the failure to be
# the model's fault.
DIFFICULTY_BAR = 0.9
ABILITY_GAP_BAR = 0.25


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def attribute_failure(run):
    """Attribute one failed run and route its recovery.

    Returns a dict with "cause", "decision", and "evidence".
    A passed run attributes CAUSE_NOT_A_FAILURE with decision
    DECISION_NONE. Missing fields are skipped, never assumed.
    """
    if not isinstance(run, dict):
        return {
            "cause": CAUSE_UNKNOWN,
            "decision": DECISION_ESCALATE,
            "evidence": "no run record to attribute",
        }
    if run.get("outcome") == "passed":
        return {
            "cause": CAUSE_NOT_A_FAILURE,
            "decision": DECISION_NONE,
            "evidence": "outcome is passed, not a failure to attribute",
        }
    if run.get("outcome") != "failed":
        return {
            "cause": CAUSE_UNKNOWN,
            "decision": DECISION_ESCALATE,
            "evidence": "no failed outcome recorded, so the run is "
            "unattributed rather than assumed passed",
        }

    repeats = run.get("repeat_outcomes")
    if isinstance(repeats, list) and any(outcome is True for outcome in repeats):
        return {
            "cause": CAUSE_BAD_RUN,
            "decision": DECISION_RETRY,
            "evidence": "a repeated run of the same issue and model "
            "solved it, so this run was the variable",
        }

    difficulty = run.get("issue_difficulty")
    if _is_number(difficulty) and difficulty >= DIFFICULTY_BAR:
        return {
            "cause": CAUSE_ISSUE_DIFFICULTY,
            "decision": DECISION_ESCALATE,
            "evidence": "issue difficulty %.2f at or above the %.2f "
            "bar: no model solves this issue in practice" % (difficulty, DIFFICULTY_BAR),
        }

    model_rate = run.get("model_pass_rate")
    best_other = run.get("best_other_pass_rate")
    if _is_number(model_rate) and _is_number(best_other):
        gap = best_other - model_rate
        if gap >= ABILITY_GAP_BAR:
            return {
                "cause": CAUSE_MODEL_ABILITY,
                "decision": DECISION_SWITCH,
                "evidence": "best other model beats this model by "
                "%.2f on this issue, at or above the %.2f bar"
                % (gap, ABILITY_GAP_BAR),
            }

    return {
        "cause": CAUSE_UNKNOWN,
        "decision": DECISION_ESCALATE,
        "evidence": "no repeat solved it, difficulty below the bar "
        "or unknown, and no ability gap at or above the bar",
    }


def _tokens(run):
    tokens = run.get("tokens", 0)
    if _is_number(tokens) and tokens > 0:
        return tokens
    return 0


def _retry_recovers(run):
    repeats = run.get("repeat_outcomes")
    return isinstance(repeats, list) and any(
        outcome is True for outcome in repeats)


def _switch_recovers(run):
    return run.get("other_model_outcome") is True


def _strategy_result(runs, attempt, recovers):
    """One recovery strategy over the failed runs.

    attempt(run) says whether the strategy spends an attempt on
    the run; recovers(run) says whether that attempt solves it.
    Every strategy gets at most one attempt per failed run, so
    the budget is equal by construction.
    """
    spent = 0
    wasted = 0
    recovered = 0
    attempts = 0
    for run in runs:
        if run.get("outcome") != "failed":
            continue
        if not attempt(run):
            continue
        attempts += 1
        cost = _tokens(run)
        spent += cost
        if recovers(run):
            recovered += 1
        else:
            wasted += cost
    return {
        "attempts": attempts,
        "recovered": recovered,
        "tokens_spent": spent,
        "tokens_wasted": wasted,
    }


def score_campaign(runs):
    """Score the router against three baselines on recorded runs.

    Returns a dict with the attribution counts, the per-strategy
    recovery and token numbers, the attribution accuracy when
    every failed run carries "expected_cause", and the campaign
    verdict. The baselines are always_retry (one retry per failed
    run), always_switch (one switch per failed run), and
    trajectory_flag (one retry per flagged failed run). The
    router attempts only where its decision is retry or switch.
    """
    runs = list(runs or [])
    failed = [run for run in runs if isinstance(run, dict)
              and run.get("outcome") == "failed"]
    attributions = {}
    unknown_count = 0
    for run in failed:
        result = attribute_failure(run)
        attributions[result["cause"]] = attributions.get(
            result["cause"], 0) + 1
        if result["cause"] == CAUSE_UNKNOWN:
            unknown_count += 1

    router = _strategy_result(
        runs,
        attempt=lambda run: attribute_failure(run)["decision"]
        in (DECISION_RETRY, DECISION_SWITCH),
        recovers=lambda run: (
            _retry_recovers(run)
            if attribute_failure(run)["decision"] == DECISION_RETRY
            else _switch_recovers(run)
            if attribute_failure(run)["decision"] == DECISION_SWITCH
            else False
        ),
    )
    always_retry = _strategy_result(
        runs, attempt=lambda run: True, recovers=_retry_recovers)
    always_switch = _strategy_result(
        runs, attempt=lambda run: True, recovers=_switch_recovers)
    trajectory_flag = _strategy_result(
        runs,
        attempt=lambda run: run.get("trajectory_flag") is True,
        recovers=_retry_recovers,
    )

    accuracy = None
    labeled = [run for run in failed
               if isinstance(run.get("expected_cause"), str)]
    if labeled and len(labeled) == len(failed):
        correct = sum(
            1 for run in labeled
            if attribute_failure(run)["cause"] == run["expected_cause"])
        accuracy = correct / len(labeled)

    best_baseline_recovered = max(
        always_retry["recovered"],
        always_switch["recovered"],
        trajectory_flag["recovered"],
    )
    best_baseline_wasted = min(
        always_retry["tokens_wasted"],
        always_switch["tokens_wasted"],
        trajectory_flag["tokens_wasted"],
    )
    if not failed:
        verdict = "REVIEW"
        verdict_evidence = "no failed runs to attribute"
    elif unknown_count:
        verdict = "REVIEW"
        verdict_evidence = "%d of %d failures unattributed" % (
            unknown_count, len(failed))
    elif router["recovered"] < best_baseline_recovered:
        verdict = "REVIEW"
        verdict_evidence = "router recovers %d, best baseline %d" % (
            router["recovered"], best_baseline_recovered)
    elif router["tokens_wasted"] > best_baseline_wasted:
        verdict = "REVIEW"
        verdict_evidence = "router wastes %d tokens, best baseline %d" % (
            router["tokens_wasted"], best_baseline_wasted)
    else:
        verdict = "READY"
        verdict_evidence = "every failure attributed; router recovers "
        verdict_evidence += "%d at %d wasted tokens, best baseline %d at %d" % (
            router["recovered"], router["tokens_wasted"],
            best_baseline_recovered, best_baseline_wasted)

    return {
        "runs": len(runs),
        "failed": len(failed),
        "attributions": attributions,
        "unknown": unknown_count,
        "attribution_accuracy": accuracy,
        "router": router,
        "always_retry": always_retry,
        "always_switch": always_switch,
        "trajectory_flag": trajectory_flag,
        "verdict": verdict,
        "verdict_evidence": verdict_evidence,
    }


def format_summary(campaign):
    """One-paragraph human-readable summary of a campaign."""
    parts = [
        "CauseReceipt: %d failed runs in %d recorded runs; "
        "attributions %s; " % (
            campaign["failed"], campaign["runs"],
            campaign["attributions"]),
    ]
    if campaign["attribution_accuracy"] is not None:
        parts.append("attribution accuracy %.2f; "
                     % campaign["attribution_accuracy"])
    router = campaign["router"]
    parts.append(
        "router recovers %d/%d at %d tokens (%d wasted); "
        "always-retry %d/%d (%d wasted), always-switch %d/%d "
        "(%d wasted), trajectory-flag %d/%d (%d wasted); "
        "verdict %s (%s)." % (
            router["recovered"], campaign["failed"],
            router["tokens_spent"], router["tokens_wasted"],
            campaign["always_retry"]["recovered"], campaign["failed"],
            campaign["always_retry"]["tokens_wasted"],
            campaign["always_switch"]["recovered"], campaign["failed"],
            campaign["always_switch"]["tokens_wasted"],
            campaign["trajectory_flag"]["recovered"], campaign["failed"],
            campaign["trajectory_flag"]["tokens_wasted"],
            campaign["verdict"], campaign["verdict_evidence"]))
    return "".join(parts)
