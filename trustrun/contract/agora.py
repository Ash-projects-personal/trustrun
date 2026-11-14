"""IRT reliability-weighted judge-panel aggregation: TRUSTRUN-AGORA-Aggregate.

Method source: Ahn, "AGORA: Reliability-Aware Aggregation of LLM Judges
via Item-Response Theory", arXiv:2611.05556 (Nov 3, 2026), abstract and
Sections 1-3 verified against the arXiv HTML 2026-11-10. AGORA fits a
graded-response model (Samejima 1969): one latent quality per item, one
discrimination (sensitivity) per judge, ordered rating thresholds per
judge, learned jointly without human labels. The discrimination acts as
the reliability weight; a regularized-horseshoe prior shrinks
uninformative judges toward zero. A label-free agreement-dispersion
statistic indicates in advance when trust weighting helps (Spearman
+0.73 and +0.61 against AGORA's gain over the per-item mean).

Trustrun's adaptation, stated plainly where it differs from the paper:

- Ratings are Trustrun's three verdict categories, mapped onto a
  3-point ordinal scale: fail=0, unverified=1, pass=2. "Unverified"
  sits in the middle: a judge that could not decide is between a pass
  and a fail on the quality scale.
- The fit is marginal maximum likelihood over a fixed theta grid with
  plain-Python EM (the project core is stdlib-only), not the paper's
  Bayesian augmentation. Shrinkage is a small ridge on log
  discrimination toward 0 (discrimination toward 1), not the paper's
  regularized-horseshoe prior.
- Dispersion is Trustrun's operationalization: the mean over items of
  the share of judge pairs disagreeing on that item. The paper names
  the statistic "agreement dispersion" but the abstract does not give
  its formula, so this formula is ours and is labeled as such.
- The go/no-go cut (0.05) is Trustrun's operational rule, not the
  paper's: below it the panel nearly always agrees, so weighting can
  change almost no verdict; above it weighting can matter.
- The per-item read-out is the paper's discrimination-weighted
  combination of judge scores: each category's weighted vote share is
  computed with weights from the learned discriminations, and the
  verdict is the category with the largest share, with a tie
  resolving to unverified (the same rule as the shipped majority
  vote, which this reproduces exactly when all weights are equal).
  The fitted latent quality (theta), the panel-median thresholds,
  and the discrimination-weighted mean score are reported alongside
  as diagnostics.
- Fallbacks never produce a silent pass: when the matrix cannot
  support an IRT fit (fewer than two judges, fewer than two items, no
  disagreement anywhere, or a non-finite fit), the result reports the
  majority verdicts with method "majority" and a note naming the
  reason. The majority verdict is the shipped JudgeRedesign behavior.
"""

import math

from trustrun.contract.judge import CATEGORIES, majority_vote

SCORES = {"fail": 0, "unverified": 1, "pass": 2}
SCORE_CATEGORIES = ("fail", "unverified", "pass")

# Theta grid for the EM fit: -4 to 4 in 0.5 steps, standard normal prior.
_GRID = [x * 0.5 for x in range(-8, 9)]
_GRID_PRIOR = [math.exp(-0.5 * t * t) for t in _GRID]
_GRID_TOTAL = sum(_GRID_PRIOR)
_GRID_PRIOR = [p / _GRID_TOTAL for p in _GRID_PRIOR]

_RIDGE_LAMBDA = 0.1
_LEARNING_RATE = 0.2
_INNER_STEPS = 5
_MAX_ITER = 60
_TOLERANCE = 1e-3

# Trustrun's operational go/no-go cut for the dispersion statistic.
# Not the paper's number: the abstract gives no threshold.
DISPERSION_CUT = 0.05


def _sigmoid(x):
    if x > 30.0:
        return 1.0
    if x < -30.0:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def _category_probs(theta, a, b1, b2):
    """GRM category probabilities P(fail), P(unverified), P(pass)."""
    s1 = _sigmoid(a * (theta - b1))
    s2 = _sigmoid(a * (theta - b2))
    middle = max(s1 - s2, 1e-12)
    return (1.0 - s1, middle, s2)


def _validate_ratings(ratings):
    if not ratings:
        raise ValueError("ratings must be a non-empty list of items")
    width = None
    for item in ratings:
        if not isinstance(item, (list, tuple)) or not item:
            raise ValueError("each item must be a non-empty list of ratings")
        if width is None:
            width = len(item)
        elif len(item) != width:
            raise ValueError("every item needs the same number of ratings")
        for rating in item:
            if rating not in CATEGORIES:
                raise ValueError("ratings must be pass/fail/unverified")
    return len(ratings), width


def dispersion(ratings):
    """Mean over items of the share of judge pairs disagreeing.

    Label-free: needs no ground truth. 0.0 when every judge agrees on
    every item; 1.0 when every pair disagrees on every item. This is
    Trustrun's operationalization of AGORA's "agreement dispersion":
    the paper names the statistic but the abstract gives no formula.
    """
    n_items, n_judges = _validate_ratings(ratings)
    if n_judges < 2:
        return 0.0
    pairs = n_judges * (n_judges - 1) / 2.0
    total = 0.0
    for item in ratings:
        disagree = 0
        for i in range(n_judges):
            for j in range(i + 1, n_judges):
                if item[i] != item[j]:
                    disagree += 1
        total += disagree / pairs
    return total / n_items


def _e_step(ratings, discriminations, thresholds):
    """Posterior over the theta grid for each item; returns posteriors."""
    posteriors = []
    for item in ratings:
        weights = list(_GRID_PRIOR)
        for judge_index, rating in enumerate(item):
            score = SCORES[rating]
            a = discriminations[judge_index]
            b1, b2 = thresholds[judge_index]
            for gi, theta in enumerate(_GRID):
                probs = _category_probs(theta, a, b1, b2)
                weights[gi] *= max(probs[score], 1e-12)
        total = sum(weights)
        if total <= 0.0 or not math.isfinite(total):
            weights = list(_GRID_PRIOR)
            total = sum(weights)
        posteriors.append([w / total for w in weights])
    return posteriors


def _eap_theta(posterior):
    return sum(w * t for w, t in zip(posterior, _GRID))


def _m_step(ratings, posteriors, discriminations, thresholds):
    """A few gradient-ascent steps on each judge's (log a, b1, b2)."""
    n_judges = len(discriminations)
    for judge_index in range(n_judges):
        a = discriminations[judge_index]
        b1, b2 = thresholds[judge_index]
        log_a = math.log(a)
        for _ in range(_INNER_STEPS):
            grad_log_a = -2.0 * _RIDGE_LAMBDA * log_a
            grad_b1 = 0.0
            grad_b2 = 0.0
            for item, posterior in zip(ratings, posteriors):
                score = SCORES[item[judge_index]]
                for weight, theta in zip(posterior, _GRID):
                    if weight == 0.0:
                        continue
                    s1 = _sigmoid(a * (theta - b1))
                    s2 = _sigmoid(a * (theta - b2))
                    if score == 0:  # fail: log(1 - s1)
                        grad_log_a += weight * a * (-(theta - b1) * s1)
                        grad_b1 += weight * a * s1
                    elif score == 2:  # pass: log s2
                        grad_log_a += weight * a * (theta - b2) * (1.0 - s2)
                        grad_b2 += weight * (-a * (1.0 - s2))
                    else:  # unverified: log(s1 - s2)
                        denom = max(s1 - s2, 1e-9)
                        d_s1_da = (theta - b1) * s1 * (1.0 - s1)
                        d_s2_da = (theta - b2) * s2 * (1.0 - s2)
                        grad_log_a += weight * a * (d_s1_da - d_s2_da) / denom
                        grad_b1 += weight * (-a * s1 * (1.0 - s1)) / denom
                        grad_b2 += weight * (a * s2 * (1.0 - s2)) / denom
            # Average the gradient over items: the posterior weights sum
            # to 1 per item, so the raw sum grows with the item count and
            # a fixed learning rate would overshoot on larger panels.
            # (Caught in prototype: unnormalized steps slammed the
            # thresholds into their clamps and inverted the weights.)
            n_items = len(ratings)
            log_a += _LEARNING_RATE * grad_log_a / n_items
            b1 += _LEARNING_RATE * grad_b1 / n_items
            b2 += _LEARNING_RATE * grad_b2 / n_items
            log_a = max(min(log_a, math.log(8.0)), math.log(0.05))
            a = math.exp(log_a)
            b1 = max(min(b1, 4.0), -4.0)
            b2 = max(min(b2, 4.0), -4.0)
            if b2 < b1 + 0.05:
                b2 = b1 + 0.05
        discriminations[judge_index] = a
        thresholds[judge_index] = (b1, b2)


def _observed_loglik(ratings, discriminations, thresholds):
    """Marginal log-likelihood of the ratings under the fitted model."""
    total = 0.0
    for item in ratings:
        mix = 0.0
        for prior, theta in zip(_GRID_PRIOR, _GRID):
            p = prior
            for judge_index, rating in enumerate(item):
                probs = _category_probs(
                    theta, discriminations[judge_index],
                    *thresholds[judge_index])
                p *= max(probs[SCORES[rating]], 1e-12)
            mix += p
        total += math.log(max(mix, 1e-300))
    return total


def _majority_agreement_init(ratings):
    """Starting discriminations from agreement with the panel majority.

    A judge that usually agrees with the per-item majority verdict is
    probably reliable; one that usually disagrees is probably not.
    The odds of agreement are the starting discrimination, clipped to
    a sane range. This is only an initialization: EM refines it, and
    the flat start runs alongside it (see aggregate_panel), so a
    misleading majority cannot trap the fit on its own.
    """
    majority = majority_verdicts(ratings)
    n_items = len(ratings)
    n_judges = len(ratings[0])
    init = []
    for judge_index in range(n_judges):
        agree = sum(1 for item, verdict in zip(ratings, majority)
                    if item[judge_index] == verdict) / n_items
        agree = max(min(agree, 0.95), 0.05)
        init.append(max(min(agree / (1.0 - agree), 5.0), 0.2))
    return init


def _fit_grm(ratings, max_iter=_MAX_ITER, init_a=None):
    """EM fit of the 3-category graded-response model.

    init_a: optional starting discriminations, one per judge. Defaults
    to 1.0 for every judge (flat start). Returns (discriminations,
    thresholds, thetas, converged, iterations). Raises ValueError on a
    non-finite fit.
    """
    n_items, n_judges = _validate_ratings(ratings)
    if init_a is None:
        discriminations = [1.0] * n_judges
    else:
        discriminations = [max(min(a, 8.0), 0.05) for a in init_a]
    thresholds = [(-0.5, 0.5)] * n_judges
    thetas = [0.0] * n_items
    converged = False
    iterations = 0
    for iterations in range(1, max_iter + 1):
        posteriors = _e_step(ratings, discriminations, thresholds)
        _m_step(ratings, posteriors, discriminations, thresholds)
        new_thetas = [_eap_theta(p) for p in posteriors]
        shift = max(abs(n - o) for n, o in zip(new_thetas, thetas))
        thetas = new_thetas
        if shift < _TOLERANCE:
            converged = True
            break
    if not all(math.isfinite(t) for t in thetas):
        raise ValueError("IRT fit produced a non-finite latent quality")
    if not all(math.isfinite(a) for a in discriminations):
        raise ValueError("IRT fit produced a non-finite discrimination")
    for b1, b2 in thresholds:
        if not (math.isfinite(b1) and math.isfinite(b2)):
            raise ValueError("IRT fit produced a non-finite threshold")
    return discriminations, thresholds, thetas, converged, iterations


def _median(values):
    ordered = sorted(values)
    n = len(ordered)
    if n % 2:
        return ordered[n // 2]
    return (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0


def majority_verdicts(ratings):
    """Per-item majority verdicts, ties resolving to unverified."""
    _validate_ratings(ratings)
    verdicts = []
    for item in ratings:
        verdict, _share = majority_vote(list(item))
        verdicts.append(verdict)
    return verdicts


def ratings_from_trial_records(records):
    """Build a ratings matrix from judge_claim_trials records.

    Each record contributes one item; each panel judge contributes one
    rating: that judge's majority category across its trials (a tie
    resolves to unverified, the same rule as the per-claim verdict).
    Judge order follows the record's per_judge insertion order, which
    is panel order. Returns (ratings, judge_names).
    """
    ratings = []
    names = None
    for record in records:
        per_judge = record.get("per_judge", {})
        judges = list(per_judge.keys())
        if names is None:
            names = judges
        votes = record.get("votes", [])
        n_judges = len(judges)
        if n_judges == 0 or not votes:
            raise ValueError("trial record has no judges or no votes")
        item = []
        for judge_index in range(n_judges):
            judge_votes = votes[judge_index::n_judges]
            verdict, _share = majority_vote(list(judge_votes))
            item.append(verdict)
        ratings.append(item)
    if names is None:
        raise ValueError("no trial records given")
    return ratings, names


def aggregate_panel(ratings, judge_names=None, max_iter=_MAX_ITER):
    """Aggregate a judge panel's ratings by IRT reliability weighting.

    ratings: a list of items; each item is a list of category strings
    (pass/fail/unverified), one per judge, same judges in every item.
    judge_names: optional names in panel order; defaults to judge-0,
    judge-1, ...

    Returns a dict with the per-item verdicts, the majority verdicts
    for comparison, the learned trust weights (normalized
    discriminations), the fitted latent qualities, the dispersion
    statistic and its go/no-go verdict, and the method actually used.
    When the matrix cannot support an IRT fit, method is "majority"
    and the verdicts are the majority verdicts, with a note naming
    the reason: never a silent pass.
    """
    n_items, n_judges = _validate_ratings(ratings)
    if judge_names is None:
        judge_names = ["judge-%d" % i for i in range(n_judges)]
    if len(judge_names) != n_judges:
        raise ValueError("judge_names must name every judge")
    majority = majority_verdicts(ratings)
    disp = dispersion(ratings)
    dispersion_verdict = (
        "weighting can change verdicts"
        if disp >= DISPERSION_CUT
        else "weighting unlikely to change verdicts")
    base = {
        "method": "majority",
        "verdicts": majority,
        "majority_verdicts": majority,
        "agreement_with_majority": 1.0,
        "trust_weights": None,
        "discriminations": None,
        "thetas": None,
        "dispersion": disp,
        "dispersion_verdict": dispersion_verdict,
        "converged": False,
        "iterations": 0,
        "notes": [],
    }
    if n_judges < 2:
        base["notes"].append(
            "IRT unavailable: one judge cannot be reliability-weighted")
        return base
    if n_items < 2:
        base["notes"].append(
            "IRT unavailable: one item cannot identify judge parameters")
        return base
    if len({r for item in ratings for r in item}) == 1:
        base["notes"].append(
            "IRT unavailable: no disagreement anywhere, nothing to learn")
        return base
    # Two deterministic starts, keep the better likelihood. The flat
    # start can lock onto the majority's view and then read the best
    # judge as noise (seen in prototype: the 0.95-reliability judge
    # fitted at discrimination 0.09 on one seed); the
    # majority-agreement start breaks that symmetry toward the
    # reliable judges, and the likelihood decides between them.
    best = None
    for init_a in (None, _majority_agreement_init(ratings)):
        try:
            fitted = _fit_grm(ratings, max_iter=max_iter, init_a=init_a)
        except ValueError:
            continue
        discriminations, thresholds, thetas, converged, iterations = fitted
        loglik = _observed_loglik(ratings, discriminations, thresholds)
        if best is None or loglik > best[0]:
            best = (loglik, discriminations, thresholds, thetas,
                    converged, iterations)
    if best is None:
        base["notes"].append("IRT fit failed, majority fallback")
        return base
    _loglik, discriminations, thresholds, thetas, converged, iterations = best
    total_a = sum(discriminations)
    weights = {name: a / total_a
               for name, a in zip(judge_names, discriminations)}
    median_b1 = _median([b1 for b1, _b2 in thresholds])
    median_b2 = _median([b2 for _b1, b2 in thresholds])
    # Read-out: reliability-weighted vote shares per category; the
    # largest share wins, a tie resolves to unverified. With equal
    # weights this is exactly the shipped majority vote.
    weight_list = [weights[n] for n in judge_names]
    weighted_scores = []
    verdicts = []
    for item in ratings:
        shares = {category: 0.0 for category in CATEGORIES}
        for weight, rating in zip(weight_list, item):
            shares[rating] += weight
        weighted_scores.append(
            sum(w * SCORES[r] for w, r in zip(weight_list, item)))
        top = max(shares.values())
        winners = [c for c, s in shares.items()
                   if abs(s - top) < 1e-9]
        verdicts.append(winners[0] if len(winners) == 1 else "unverified")
    agreement = sum(1 for v, m in zip(verdicts, majority) if v == m)
    agreement = agreement / len(verdicts) if verdicts else 1.0
    return {
        "method": "agora",
        "verdicts": verdicts,
        "majority_verdicts": majority,
        "agreement_with_majority": agreement,
        "trust_weights": weights,
        "discriminations": {name: a for name, a in
                            zip(judge_names, discriminations)},
        "thetas": thetas,
        "median_thresholds": (median_b1, median_b2),
        "weighted_scores": weighted_scores,
        "dispersion": disp,
        "dispersion_verdict": dispersion_verdict,
        "converged": converged,
        "iterations": iterations,
        "notes": [],
    }
