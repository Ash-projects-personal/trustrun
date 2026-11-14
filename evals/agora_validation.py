"""Labeled validation sets for judge-panel aggregation (TRUSTRUN-AGORA-Aggregate).

Simulated judge pools with KNOWN reliability and KNOWN ground truth,
so majority-vote aggregation and AGORA's IRT reliability-weighted
aggregation can be compared honestly on labeled items. Nothing here is
a real model: the judges are simulated voters whose per-item correctness
probability is their reliability. The experiment follows the queue's
plan: run the contract judge panel with majority vs AGORA aggregation
on labeled validation sets; metrics are agreement with ground truth,
per pool and per set size, plus the dispersion statistic's predictive
value for AGORA's gain.

Pools (reliability = probability the judge's rating equals the truth;
when wrong it picks uniformly among the other two categories):
- uneven: [0.95, 0.9, 0.6, 0.5, 0.15] — two strong judges, two weak,
  one inverted. The regime AGORA is built for (Ahn, arXiv:2611.05556:
  pools of uneven reliability, small validation sets).
- even: [0.85] * 5 — equally reliable judges. Control: weighting
  should not help and should not hurt much.
- three: [0.95, 0.6, 0.5] — a three-judge panel, one strong.

Ground truth is binary (pass/fail); no item's truth is "unverified",
so an "unverified" verdict always counts as a miss. That is the hard
reading: AGORA's abstentions are scored as wrong, not excused.

Every cell is seeded, so the numbers reproduce exactly.
"""

import random

from trustrun.contract.agora import aggregate_panel

POOLS = {
    "uneven": [0.95, 0.9, 0.6, 0.5, 0.15],
    "even": [0.85, 0.85, 0.85, 0.85, 0.85],
    "three": [0.95, 0.6, 0.5],
}

SIZES = (20, 50, 100)
SEEDS = (0, 1, 2, 3, 4)

_CATEGORIES = ("pass", "fail", "unverified")


def simulate_pool(reliabilities, n_items, seed):
    """Simulate one pool's ratings and the ground truth.

    Returns (truths, ratings): truths are pass/fail only; ratings are
    one row per item, one category per judge.
    """
    rng = random.Random(seed)
    truths = ["pass" if rng.random() < 0.5 else "fail"
              for _ in range(n_items)]
    ratings = []
    for truth in truths:
        row = []
        for reliability in reliabilities:
            if rng.random() < reliability:
                row.append(truth)
            else:
                row.append(rng.choice(
                    [c for c in _CATEGORIES if c != truth]))
        ratings.append(row)
    return truths, ratings


def _agreement(verdicts, truths):
    return sum(1 for v, t in zip(verdicts, truths) if v == t) / len(truths)


def compare_cell(pool_name, n_items, seed, max_iter=60):
    """Compare majority vs AGORA on one labeled cell.

    Returns the measured numbers for the cell: both agreements, the
    gain, the dispersion statistic, and the fit's method/convergence.
    """
    reliabilities = POOLS[pool_name]
    truths, ratings = simulate_pool(reliabilities, n_items, seed)
    names = ["judge-%d" % i for i in range(len(reliabilities))]
    result = aggregate_panel(ratings, judge_names=names,
                             max_iter=max_iter)
    majority = _agreement(result["majority_verdicts"], truths)
    agora = _agreement(result["verdicts"], truths)
    return {
        "pool": pool_name,
        "n_items": n_items,
        "seed": seed,
        "reliabilities": list(reliabilities),
        "majority_agreement": majority,
        "agora_agreement": agora,
        "gain": agora - majority,
        "dispersion": result["dispersion"],
        "dispersion_verdict": result["dispersion_verdict"],
        "method": result["method"],
        "converged": result["converged"],
        "iterations": result["iterations"],
        "trust_weights": result["trust_weights"],
        "n_items_labeled": n_items,
    }


def _rank(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mean_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = mean_rank
        i = j + 1
    return ranks


def spearman(xs, ys):
    """Spearman rank correlation (stdlib; ties get mean ranks)."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    rx = _rank(xs)
    ry = _rank(ys)
    n = len(xs)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    num = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry))
    den_x = sum((a - mean_x) ** 2 for a in rx)
    den_y = sum((b - mean_y) ** 2 for b in ry)
    if den_x == 0.0 or den_y == 0.0:
        return None
    return num / (den_x * den_y) ** 0.5


def run_comparison(max_iter=60):
    """Run every pool x size x seed cell and summarize.

    Returns the summary dict: per-cell results plus mean gain per
    pool/size, the dispersion-gain Spearman correlation across cells,
    and the labeled-row counts (one audit-level row per cell; two
    check-level judgments per item: majority vs truth, AGORA vs
    truth).
    """
    cells = []
    for pool_name in POOLS:
        for n_items in SIZES:
            for seed in SEEDS:
                cells.append(compare_cell(pool_name, n_items, seed,
                                          max_iter=max_iter))
    by_pool_size = {}
    for cell in cells:
        key = (cell["pool"], cell["n_items"])
        by_pool_size.setdefault(key, []).append(cell)
    aggregates = {}
    for (pool_name, n_items), group in sorted(by_pool_size.items()):
        aggregates["%s/n=%d" % (pool_name, n_items)] = {
            "cells": len(group),
            "mean_majority_agreement": (
                sum(c["majority_agreement"] for c in group) / len(group)),
            "mean_agora_agreement": (
                sum(c["agora_agreement"] for c in group) / len(group)),
            "mean_gain": sum(c["gain"] for c in group) / len(group),
            "mean_dispersion": (
                sum(c["dispersion"] for c in group) / len(group)),
        }
    total_items = sum(c["n_items_labeled"] for c in cells)
    return {
        "cells": cells,
        "aggregates": aggregates,
        "dispersion_gain_spearman": spearman(
            [c["dispersion"] for c in cells],
            [c["gain"] for c in cells]),
        "audit_level_rows": len(cells),
        "check_level_judgments": total_items * 2,
        "method": (
            "Ahn, AGORA, arXiv:2611.05556; Trustrun graded-response "
            "fit (trustrun/contract/agora.py); simulated pools with "
            "known reliability and binary ground truth"),
    }
