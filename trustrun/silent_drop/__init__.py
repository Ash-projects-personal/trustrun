"""SilentDrop: a sequential-testing silent-regression detector for production agents.

Production agents get worse while every dashboard gets better, and no
shipped detector catches it. The evidence is a simulation published
Nov 6, 2026 (aiobs.cloud, reproducible, seeded RNG): cutting
verification coverage from 90% to 50% drops correct answers from
91% to 76% while latency falls 37% (5.3s to 3.3s), tokens fall 17%,
and errors stay flat. A dashboard watching latency and errors sees
an improvement. The same simulation reports about 100 labeled runs
are needed for 92% detection power with a fixed-threshold judge,
and about 10,000 production runs wait at 1% label coverage (the
author's assumption). The Anthropic April 2026 Claude Code
postmortem (via secondary summaries) is the real-world version:
an effort cut from high to medium on Mar 4, a caching bug on
Mar 26, and a verbosity cap on Apr 16 left the product degraded
for six weeks before the fix in v2.1.116. GitHub issue #42796
telemetry (6,852 sessions) shows median visible thinking down
73%. The LangChain survey puts 57% of teams with agents in
production, quality as the top barrier, and only about 52% running
offline evals.

What is new here is the detector, not the statistics. Wald's
sequential probability ratio test (SPRT, 1945) is old, and mixture
SPRT is the standard tool for early stopping in A/B testing at
Uber and Netflix. Online eval platforms (LangSmith, Braintrust,
Langfuse, Arize) score sampled production traces, and the
regression-testing guides all use the same shape: a golden test
set plus a fixed threshold, typically flagging an aggregate
quality drop of more than 5 points. No shipped tool found
publishes a sequential-testing silent-regression detector for
production agents with a label-sparsity-aware detection-delay
estimate. That combination, plus the receipt it emits inside
Trustrun's trust report, is the new piece. Distinct from
ProcedureGate (a pre-deployment gate) and TakeoverReceipt (an
acceptance gate): SilentDrop is live detection during production
runs. Distinct from the Nov 7 held same-version receipt (model-side
drift): this is harness and config-side drops, the verification
cut in the simulation being the example.

The detector runs Wald's SPRT over labeled outcome labels
(1 = success, 0 = failure) from a production stream. H0 is the
baseline success rate p0; H1 is the degraded rate p1 < p0. Each
observation adds log(p1/p0) on a success and log((1-p1)/(1-p0))
on a failure to the cumulative log likelihood ratio. The test
stops and reports REGRESSION when the ratio reaches the upper
Wald boundary log((1-beta)/alpha), NO_REGRESSION when it
reaches the lower boundary log(beta/(1-alpha)), and
INCONCLUSIVE when the stream ends between the boundaries.
Alpha is the false-alarm rate (calling a regression that is not
there); beta is the miss rate (missing a real regression).

The delay estimate is the other half. Expected labeled runs to
detect a real drop come from Wald's approximation, and dividing
by the label coverage turns labeled runs into production runs
waited: at 1% coverage, 24 labeled runs mean about 2,400
production runs pass before the alarm. The fixed-sample
comparison is a normal-approximation two-proportion sample size
at the same alpha and beta, so the receipt can report how many
fewer labeled runs the sequential test needs than the
fixed-threshold judge baseline on the same rates.

An APM-only baseline is scored alongside: it alerts only when
latency rises past a threshold or the error rate rises past a
threshold. On the simulation's shape (latency down 37%, errors
flat) it never fires, which is the point: a quality drop that
makes the agent faster and no noisier is invisible to APM.

Verdicts. A stream is BLOCK when the SPRT reports REGRESSION,
PASS when it reports NO_REGRESSION, and REVIEW when it ends
INCONCLUSIVE or is empty. An empty stream is REVIEW: there is
nothing to score, so it is unscored, never passed.

Honest limits, read before quoting any number from this module:
the SPRT assumes independent Bernoulli outcomes with a fixed
baseline and a fixed degraded rate, so a drifting baseline, a
changing task mix, or correlated failures (one bad deploy hitting
many runs at once) all violate the model and the alpha/beta
guarantees with them; the expected-runs and fixed-sample figures
are Wald and normal approximations, not exact values, and the
1.89x sequential-vs-fixed ratio measured on the 0.90 to 0.70
rates is a property of those rates, not a general claim; the
5x win bar in the queue's experiment plan is untested and is
not claimed here. The labeled cases in the verify script are
synthetic streams with hand-computed verdicts, not production
traces; the run over a labeled SWE-bench Verified trace corpus
stays future work.
"""

import math

VERDICT_BLOCK = "BLOCK"
VERDICT_REVIEW = "REVIEW"
VERDICT_PASS = "PASS"

DECISION_REGRESSION = "REGRESSION"
DECISION_NO_REGRESSION = "NO_REGRESSION"
DECISION_INCONCLUSIVE = "INCONCLUSIVE"

# One-sided normal quantiles used by the fixed-sample comparison.
_Z_ALPHA_005 = 1.6448536269514722
_Z_BETA_010 = 1.2815515655446004


def _check_rates(p0, p1):
    if not (0.0 < p0 < 1.0):
        raise ValueError("p0 must be strictly between 0 and 1")
    if not (0.0 < p1 < 1.0):
        raise ValueError("p1 must be strictly between 0 and 1")
    if p1 >= p0:
        raise ValueError("p1 (degraded rate) must be below p0 (baseline rate)")


def _check_error_rates(alpha, beta):
    if not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be strictly between 0 and 1")
    if not (0.0 < beta < 1.0):
        raise ValueError("beta must be strictly between 0 and 1")


def sprt_thresholds(alpha=0.05, beta=0.10):
    """Wald boundaries (upper, lower) for the log likelihood ratio."""
    _check_error_rates(alpha, beta)
    upper = math.log((1.0 - beta) / alpha)
    lower = math.log(beta / (1.0 - alpha))
    return (upper, lower)


def run_sprt(outcomes, p0, p1, alpha=0.05, beta=0.10):
    """Run Wald's SPRT over a labeled outcome stream.

    outcomes is a list of 1 (success) or 0 (failure); any other
    value raises ValueError. Stops at the first boundary crossing
    and ignores the rest of the stream. Returns a dict with the
    decision, the runs used, the final log likelihood ratio, which
    boundary was crossed (or None), and the full trace.
    """
    _check_rates(p0, p1)
    _check_error_rates(alpha, beta)
    if not isinstance(outcomes, list):
        raise ValueError("outcomes must be a list")
    upper, lower = sprt_thresholds(alpha, beta)
    step_success = math.log(p1 / p0)
    step_failure = math.log((1.0 - p1) / (1.0 - p0))
    llr = 0.0
    trace = []
    for outcome in outcomes:
        if outcome not in (0, 1, True, False):
            raise ValueError("outcomes must be 0 or 1")
        llr += step_success if outcome else step_failure
        trace.append(llr)
        if llr >= upper:
            return {
                "decision": DECISION_REGRESSION,
                "runs_used": len(trace),
                "final_llr": llr,
                "boundary": "upper",
                "trace": trace,
            }
        if llr <= lower:
            return {
                "decision": DECISION_NO_REGRESSION,
                "runs_used": len(trace),
                "final_llr": llr,
                "boundary": "lower",
                "trace": trace,
            }
    return {
        "decision": DECISION_INCONCLUSIVE,
        "runs_used": len(trace),
        "final_llr": llr,
        "boundary": None,
        "trace": trace,
    }


def expected_runs_to_detect(p0, p1, alpha=0.05, beta=0.10):
    """Wald's approximation of expected labeled runs to detect a real drop.

    E[N | H1] = ((1-beta) * A + beta * B) / D(p1 || p0), where A and
    B are the Wald boundaries and D is the KL divergence from the
    degraded rate to the baseline rate.
    """
    _check_rates(p0, p1)
    _check_error_rates(alpha, beta)
    upper, lower = sprt_thresholds(alpha, beta)
    divergence = p1 * math.log(p1 / p0) + (1.0 - p1) * math.log(
        (1.0 - p1) / (1.0 - p0)
    )
    return ((1.0 - beta) * upper + beta * lower) / divergence


def expected_runs_to_clear(p0, p1, alpha=0.05, beta=0.10):
    """Wald's approximation of expected labeled runs to accept no regression.

    E[N | H0] = (beta * A + (1-beta) * B) / E[log LR | H0]; the
    denominator is negative, so the ratio is positive.
    """
    _check_rates(p0, p1)
    _check_error_rates(alpha, beta)
    upper, lower = sprt_thresholds(alpha, beta)
    mean_step = p0 * math.log(p1 / p0) + (1.0 - p0) * math.log(
        (1.0 - p1) / (1.0 - p0)
    )
    return (beta * upper + (1.0 - beta) * lower) / mean_step


def fixed_sample_size(p0, p1, alpha=0.05, beta=0.10):
    """Normal-approximation fixed sample size for the same test.

    One-sided comparison of two proportions at the same alpha and
    beta. This is the fixed-threshold judge baseline the SPRT is
    measured against; it is an approximation, not an exact size.
    Only the standard (alpha 0.05, beta 0.10) quantiles are built
    in; any other pair raises ValueError rather than silently
    using the wrong z values.
    """
    _check_rates(p0, p1)
    _check_error_rates(alpha, beta)
    if alpha != 0.05 or beta != 0.10:
        raise ValueError(
            "fixed_sample_size only supports alpha=0.05, beta=0.10"
        )
    numerator = _Z_ALPHA_005 * math.sqrt(p0 * (1.0 - p0)) + _Z_BETA_010 * math.sqrt(
        p1 * (1.0 - p1)
    )
    return (numerator / (p0 - p1)) ** 2


def detection_delay(labeled_runs, label_coverage):
    """Production runs waited before a decision, given label coverage.

    Only a fraction of production runs carry a label, so the
    labeled runs the test needs take labeled_runs / coverage
    production runs to arrive. At 1% coverage, 24 labeled runs
    mean about 2,400 production runs pass first.
    """
    if labeled_runs < 0:
        raise ValueError("labeled_runs must not be negative")
    if not (0.0 < label_coverage <= 1.0):
        raise ValueError("label_coverage must be in (0, 1]")
    return labeled_runs / label_coverage


def apm_would_alert(latency_change_pct, error_change_pp,
                    latency_threshold_pct=10.0, error_threshold_pp=1.0):
    """Whether APM-only alerting fires on a production change.

    Alerts only on a latency rise past the threshold or an error
    rate rise past the threshold. A quality drop that makes the
    agent faster and no noisier never fires: the simulation's
    shape (latency -37%, errors flat) is the silent case.
    """
    return (
        latency_change_pct >= latency_threshold_pct
        or error_change_pp >= error_threshold_pp
    )


def score_stream(outcomes, p0, p1, alpha=0.05, beta=0.10,
                 label_coverage=0.01):
    """Score one labeled production stream and return its receipt.

    Verdict BLOCK on REGRESSION, PASS on NO_REGRESSION, REVIEW on
    INCONCLUSIVE or an empty stream. The receipt carries the
    decision, the runs used, the final log likelihood ratio, and
    the detection delay in production runs at the given label
    coverage (only meaningful when the test decided).
    """
    result = run_sprt(outcomes, p0, p1, alpha, beta)
    decision = result["decision"]
    if decision == DECISION_REGRESSION:
        verdict = VERDICT_BLOCK
    elif decision == DECISION_NO_REGRESSION:
        verdict = VERDICT_PASS
    else:
        verdict = VERDICT_REVIEW
    decided = decision in (DECISION_REGRESSION, DECISION_NO_REGRESSION)
    delay = (
        detection_delay(result["runs_used"], label_coverage)
        if decided
        else None
    )
    return {
        "verdict": verdict,
        "decision": decision,
        "runs_used": result["runs_used"],
        "final_llr": result["final_llr"],
        "boundary": result["boundary"],
        "detection_delay_runs": delay,
    }


def score_campaign(streams, p0, p1, alpha=0.05, beta=0.10,
                   label_coverage=0.01):
    """Score a campaign of labeled streams and aggregate the receipt.

    streams is a list of outcome lists. The campaign verdict is
    the worst stream verdict. Mean runs to decision covers decided
    streams only; mean detection delay covers BLOCK streams only,
    in production runs at the given label coverage.
    """
    if not isinstance(streams, list):
        raise ValueError("streams must be a list")
    scored = [
        score_stream(s, p0, p1, alpha, beta, label_coverage)
        for s in streams
    ]
    verdicts = {
        VERDICT_BLOCK: 0,
        VERDICT_REVIEW: 0,
        VERDICT_PASS: 0,
    }
    for item in scored:
        verdicts[item["verdict"]] += 1
    decided = [
        item["runs_used"]
        for item in scored
        if item["decision"] != DECISION_INCONCLUSIVE
    ]
    blocked = [
        item["detection_delay_runs"]
        for item in scored
        if item["verdict"] == VERDICT_BLOCK
    ]
    if VERDICT_BLOCK in (item["verdict"] for item in scored):
        verdict = VERDICT_BLOCK
    elif VERDICT_REVIEW in (item["verdict"] for item in scored):
        verdict = VERDICT_REVIEW
    else:
        verdict = VERDICT_PASS
    return {
        "verdicts": verdicts,
        "streams": len(scored),
        "mean_runs_to_decision": (
            sum(decided) / len(decided) if decided else None
        ),
        "mean_detection_delay_runs": (
            sum(blocked) / len(blocked) if blocked else None
        ),
        "expected_runs_to_detect": expected_runs_to_detect(
            p0, p1, alpha, beta
        ),
        "fixed_sample_size": fixed_sample_size(p0, p1, alpha, beta),
        "verdict": verdict,
        "results": scored,
    }


def format_summary(campaign):
    """One-line human summary of a scored campaign."""
    verdicts = campaign["verdicts"]
    mean_runs = campaign["mean_runs_to_decision"]
    delay = campaign["mean_detection_delay_runs"]
    runs_text = "%.2f" % mean_runs if mean_runs is not None else "n/a"
    delay_text = "%.0f" % delay if delay is not None else "n/a"
    return (
        "SilentDrop: %d streams, %d BLOCK / %d REVIEW / %d PASS, "
        "mean %s runs to decision, mean %s production runs to "
        "detection at the campaign label coverage, verdict %s"
        % (
            campaign["streams"],
            verdicts[VERDICT_BLOCK],
            verdicts[VERDICT_REVIEW],
            verdicts[VERDICT_PASS],
            runs_text,
            delay_text,
            campaign["verdict"],
        )
    )
