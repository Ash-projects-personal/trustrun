"""Focused verification for TRUSTRUN-ThinkSpend.

Scores the module's 25 labeled cases: hidden share (basic,
zero reasoning, zero total, the dev.to GLM 5.3 Flash and
DeepSeek V4.1 Flash default medians), call and hidden cost
(basic, priced, zero), call-site scores (the waste site, the
low-effort clean site, the hard site that keeps effort, the
below-floor site, the below-bar site, no-correct cost per
correct, mixed-site and mixed-difficulty rejections), and
campaign verdicts (the 10-run REVIEW fixture, PASS with no
waste, BLOCK when waste dominates, tuning wins with a
low-effort baseline, tuning unproven without one, empty
campaign, zero-token campaign, and the one-line summary).
Every case is a fixed recorded call trace with a hand-computed
score, scored by trustrun.think_spend. The campaign block
checks the aggregate numbers by hand: 10 runs, total cost
$0.0188, hidden cost $0.0162, hidden share 0.8617, cost per
correct task $0.00188, waste share 0.3830 on the summarize
site, tuning unproven, verdict REVIEW.

Writes a machine-readable summary into
reports/think-spend-verify/summary.json. Expected yield: 25
labeled cases, 25/25 match, campaign block matches.
Exits non-zero on any mismatch.

The cases are fixed call traces with hand-computed scores,
including the dev.to Oct 11 2026 per-model medians as inputs;
they are not production traces.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.think_spend import (  # noqa: E402
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_REVIEW,
    call_cost,
    format_summary,
    hidden_cost,
    hidden_share,
    score_call_site,
    score_campaign,
)

REPORTS = os.path.join(HERE, "reports", "think-spend-verify")


def _call(site="summarize", visible=200, reasoning=1800, correct=True,
          difficulty="simple", effort="high", price=1.0):
    return {
        "call_site": site,
        "visible_tokens": visible,
        "reasoning_tokens": reasoning,
        "correct": correct,
        "difficulty": difficulty,
        "effort": effort,
        "price_per_million_output": price,
    }


def _site_calls(count, **kwargs):
    return [_call(**kwargs) for _ in range(count)]


def _main_fixture():
    calls = []
    calls += _site_calls(4, site="summarize")
    calls += _site_calls(4, site="extract", reasoning=0, effort="low")
    calls += _site_calls(
        2, site="plan", visible=500, reasoning=4500, difficulty="hard"
    )
    return calls


MAIN = _main_fixture()

TUNING_FIXTURE = _main_fixture() + _site_calls(
    2, site="summarize", reasoning=100, effort="low"
)

BLOCK_FIXTURE = _site_calls(4, site="summarize") + [
    _call(site="extract", reasoning=0, effort="low")
]

PASS_FIXTURE = _site_calls(4, site="extract", reasoning=0, effort="low") + (
    _site_calls(2, site="plan", visible=500, reasoning=4500,
                difficulty="hard")
)

# (case_id, kind, payload, expected)
CASES = [
    ("share-basic", "share", _call(), 0.9),
    ("share-zero-reasoning", "share", _call(reasoning=0), 0.0),
    ("share-zero-total", "share", _call(visible=0, reasoning=0), None),
    ("share-devto-glm", "share", _call(visible=227, reasoning=2256),
     0.9086),
    ("share-devto-deepseek", "share", _call(visible=232, reasoning=1293),
     0.8479),
    ("cost-basic", "cost", _call(), 0.002),
    ("cost-priced", "cost",
     _call(visible=1000, reasoning=4000, price=2.0), 0.01),
    ("cost-zero", "cost", _call(visible=0, reasoning=0), 0.0),
    ("hidden-cost-basic", "hidden_cost", _call(), 0.0018),
    ("site-waste", "site", _site_calls(4, site="summarize"),
     {"accuracy": 1.0, "mean_hidden_share": 0.9,
      "total_cost": 0.008, "hidden_cost": 0.0072,
      "cost_per_correct": 0.002,
      "recommendation": "downgrade_to_low"}),
    ("site-low-effort-clean", "site",
     _site_calls(4, site="extract", reasoning=0, effort="low"),
     {"accuracy": 1.0, "mean_hidden_share": 0.0,
      "total_cost": 0.0008, "hidden_cost": 0.0,
      "cost_per_correct": 0.0002, "recommendation": "keep"}),
    ("site-hard-keeps", "site",
     _site_calls(2, site="plan", visible=500, reasoning=4500,
                 difficulty="hard"),
     {"accuracy": 1.0, "mean_hidden_share": 0.9,
      "total_cost": 0.01, "hidden_cost": 0.009,
      "cost_per_correct": 0.005, "recommendation": "keep"}),
    ("site-below-floor", "site",
     [_call(correct=True), _call(correct=True),
      _call(correct=False), _call(correct=False)],
     {"accuracy": 0.5, "mean_hidden_share": 0.9,
      "recommendation": "keep"}),
    ("site-below-bar", "site",
     _site_calls(4, site="summarize", visible=1800, reasoning=200),
     {"accuracy": 1.0, "mean_hidden_share": 0.1,
      "recommendation": "keep"}),
    ("site-no-correct", "site",
     _site_calls(2, site="summarize", correct=False),
     {"accuracy": 0.0, "mean_hidden_share": 0.9,
      "cost_per_correct": None, "recommendation": "keep"}),
    ("site-rejects-mixed-site", "site_error",
     [_call(site="a"), _call(site="b")], "ValueError"),
    ("site-rejects-mixed-difficulty", "site_error",
     [_call(difficulty="simple"), _call(difficulty="hard")],
     "ValueError"),
    ("site-rejects-negative-tokens", "site_error",
     [_call(reasoning=-1)], "ValueError"),
    ("campaign-review", "campaign", MAIN,
     {"verdict": VERDICT_REVIEW, "calls": 10, "accuracy": 1.0,
      "total_cost": 0.0188, "hidden_cost": 0.0162,
      "hidden_cost_share": 0.8617, "cost_per_correct": 0.0019,
      "waste_sites": ["summarize"], "waste_hidden_cost": 0.0072,
      "waste_share": 0.383, "tuning_wins": False,
      "tuning_saving_share": None}),
    ("campaign-pass", "campaign", PASS_FIXTURE,
     {"verdict": VERDICT_PASS, "waste_share": 0.0,
      "waste_sites": []}),
    ("campaign-block", "campaign", BLOCK_FIXTURE,
     {"verdict": VERDICT_BLOCK, "waste_share": 0.878}),
    ("campaign-tuning-wins", "campaign", TUNING_FIXTURE,
     {"verdict": VERDICT_REVIEW, "total_cost": 0.0194,
      "waste_share": 0.3814, "tuning_wins": True,
      "tuning_saving": 0.0068, "tuning_saving_share": 0.7234,
      "tuning_accuracy_delta": 0.0}),
    ("campaign-empty", "campaign", [],
     {"verdict": VERDICT_REVIEW, "waste_share": None, "calls": 0}),
    ("campaign-zero-tokens", "campaign",
     [_call(visible=0, reasoning=0), _call(visible=0, reasoning=0)],
     {"verdict": VERDICT_REVIEW, "total_cost": 0.0,
      "waste_share": None}),
    ("format-summary", "summary", MAIN,
     "ThinkSpend: 10 calls, 3 sites, cost $0.0188, hidden share "
     "0.8617, waste share 0.3830, tuning unproven, verdict REVIEW"),
]

EXPECTED_CAMPAIGN = {
    "sites": 3,
    "calls": 10,
    "verdict": VERDICT_REVIEW,
    "accuracy": 1.0,
    "total_cost": 0.0188,
    "hidden_cost": 0.0162,
    "hidden_cost_share": 0.8617,
    "cost_per_correct": 0.0019,
    "waste_sites": ["summarize"],
    "waste_hidden_cost": 0.0072,
    "waste_share": 0.383,
    "tuning_wins": False,
    "tuning_saving_share": None,
}


def _round(value):
    return None if value is None else round(value, 4)


def _check(kind, payload, expected):
    if kind == "share":
        got = _round(hidden_share(payload))
        return got == expected, got
    if kind == "cost":
        got = _round(call_cost(payload))
        return got == expected, got
    if kind == "hidden_cost":
        got = _round(hidden_cost(payload))
        return got == expected, got
    if kind == "site":
        site = score_call_site(payload)
        got = {
            "accuracy": _round(site["accuracy"]),
            "mean_hidden_share": _round(site["mean_hidden_share"]),
            "recommendation": site["recommendation"]["recommendation"],
        }
        if "total_cost" in expected:
            got["total_cost"] = _round(site["total_cost"])
        if "hidden_cost" in expected:
            got["hidden_cost"] = _round(site["hidden_cost"])
        if "cost_per_correct" in expected:
            got["cost_per_correct"] = _round(site["cost_per_correct"])
        return got == expected, got
    if kind == "site_error":
        try:
            score_call_site(payload)
        except ValueError:
            return expected == "ValueError", "ValueError"
        return False, "no error"
    if kind == "campaign":
        campaign = score_campaign(payload)
        got = {"verdict": campaign["verdict"]}
        if "calls" in expected:
            got["calls"] = campaign["calls"]
        if "accuracy" in expected:
            got["accuracy"] = _round(campaign["accuracy"])
        if "total_cost" in expected:
            got["total_cost"] = _round(campaign["total_cost"])
        if "hidden_cost" in expected:
            got["hidden_cost"] = _round(campaign["hidden_cost"])
        if "hidden_cost_share" in expected:
            got["hidden_cost_share"] = _round(
                campaign["hidden_cost_share"]
            )
        if "cost_per_correct" in expected:
            got["cost_per_correct"] = _round(campaign["cost_per_correct"])
        if "waste_sites" in expected:
            got["waste_sites"] = campaign["waste_sites"]
        if "waste_hidden_cost" in expected:
            got["waste_hidden_cost"] = _round(
                campaign["waste_hidden_cost"]
            )
        if "waste_share" in expected:
            got["waste_share"] = _round(campaign["waste_share"])
        if "tuning_wins" in expected:
            got["tuning_wins"] = campaign["tuning"]["tuning_wins"]
        if "tuning_saving" in expected:
            got["tuning_saving"] = _round(campaign["tuning"]["saving"])
        if "tuning_saving_share" in expected:
            got["tuning_saving_share"] = _round(
                campaign["tuning"]["saving_share"]
            )
        if "tuning_accuracy_delta" in expected:
            got["tuning_accuracy_delta"] = _round(
                campaign["tuning"]["accuracy_delta"]
            )
        return got == expected, got
    if kind == "summary":
        campaign = score_campaign(payload)
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

    campaign = score_campaign(MAIN)
    campaign_block = {
        "sites": len(campaign["sites"]),
        "calls": campaign["calls"],
        "verdict": campaign["verdict"],
        "accuracy": _round(campaign["accuracy"]),
        "total_cost": _round(campaign["total_cost"]),
        "hidden_cost": _round(campaign["hidden_cost"]),
        "hidden_cost_share": _round(campaign["hidden_cost_share"]),
        "cost_per_correct": _round(campaign["cost_per_correct"]),
        "waste_sites": campaign["waste_sites"],
        "waste_hidden_cost": _round(campaign["waste_hidden_cost"]),
        "waste_share": _round(campaign["waste_share"]),
        "tuning_wins": campaign["tuning"]["tuning_wins"],
        "tuning_saving_share": _round(
            campaign["tuning"]["saving_share"]
        ),
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

    print("ThinkSpend verify: %d/%d cases matched"
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
