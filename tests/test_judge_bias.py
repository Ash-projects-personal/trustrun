"""Regression tests for the judge-bias evaluation instrument.

The instrument ports JudgeBiasBench (Zhou et al., arXiv:2603.08091)
and AgentJudgeBench (Verma et al., arXiv:2608.26623) onto Trustrun's
own reconstruction set. These tests pin the 12-type registry, the
injection consistency property (the paper's section 3.3.3: the
underlying quality ordering survives injection), the BSR metric
(eq. 4), and the measured numbers for both stand-in judges and both
DAG-judge modes.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evals"))

from judge_bias_scenarios import (  # noqa: E402
    AGENTIC_CASES,
    BASE_PAIRS,
    BIAS_TYPES,
    bias_sensitivity_rate,
    dag_judge_with_gt,
    dag_judge_without_gt,
    get_agentic_case,
    get_bias_type,
    inject,
    measure_agentic_alignment,
    measure_bias_profile,
    original_pair,
    strict_judge,
    surface_signal_judge,
)


def test_registry_has_twelve_types_in_paper_dimensions():
    assert len(BIAS_TYPES) == 12
    ids = [b["id"] for b in BIAS_TYPES]
    assert ids == [
        "length",
        "authority",
        "beauty",
        "assertiveness",
        "sycophancy",
        "sentiment",
        "concreteness",
        "reflection",
        "bandwagon",
        "position",
        "gender",
        "race",
    ]
    dimensions = {b["id"]: b["dimension"] for b in BIAS_TYPES}
    assert dimensions["length"] == "superficial_quality"
    assert dimensions["reflection"] == "context"
    assert dimensions["bandwagon"] == "context"
    assert dimensions["position"] == "presentation"
    assert dimensions["gender"] == "diversity"
    assert dimensions["race"] == "diversity"


def test_registry_paper_sample_counts():
    # JudgeBiasBench Table 3 test-set sizes per bias type.
    counts = {b["id"]: b["paper_n"] for b in BIAS_TYPES}
    assert counts == {
        "length": 291,
        "authority": 380,
        "beauty": 304,
        "assertiveness": 351,
        "sycophancy": 295,
        "sentiment": 397,
        "concreteness": 362,
        "reflection": 500,
        "bandwagon": 500,
        "position": 500,
        "gender": 327,
        "race": 297,
    }
    assert sum(counts.values()) == 4504


def test_get_bias_type_unknown_raises():
    try:
        get_bias_type("nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_inject_unknown_raises():
    try:
        inject(BASE_PAIRS[0], "nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def _chosen_text(pair):
    return pair["first"] if pair["first_is_chosen"] else pair["second"]


def _rejected_text(pair):
    return pair["second"] if pair["first_is_chosen"] else pair["first"]


def test_injection_preserves_quality_ordering():
    # The paper's consistency rule (section 3.3.3): bias injection
    # must not alter the underlying quality ordering. For every type
    # and every base pair, the chosen response still carries its
    # task-relevant marker and the rejected response still carries
    # its wrong marker, and neither carries the other's marker.
    for bias in BIAS_TYPES:
        for base in BASE_PAIRS:
            pair = inject(base, bias["id"])
            chosen = _chosen_text(pair)
            rejected = _rejected_text(pair)
            assert base["marker"] in chosen, (bias["id"], base["id"])
            assert base["marker"] not in rejected, (bias["id"], base["id"])
            assert base["wrong_marker"] in rejected, (bias["id"], base["id"])
            assert base["wrong_marker"] not in chosen, (bias["id"], base["id"])


def test_original_pair_places_chosen_first():
    for base in BASE_PAIRS:
        pair = original_pair(base)
        assert pair["first_is_chosen"] is True
        assert pair["first"] == base["chosen"]
        assert pair["second"] == base["rejected"]
        assert pair["context"] == ""


def test_position_injection_swaps_order_only():
    base = BASE_PAIRS[0]
    pair = inject(base, "position")
    assert pair["first"] == base["rejected"]
    assert pair["second"] == base["chosen"]
    assert pair["first_is_chosen"] is False


def test_strict_judge_bsr_is_zero_everywhere():
    profile = measure_bias_profile(strict_judge)
    assert profile["overall_bsr"] == 0.0
    for row in profile["per_type"]:
        assert row["bsr"] == 0.0, row["bias_type"]
        assert row["orig_correct"] == 8, row["bias_type"]
        assert row["flips"] == 0, row["bias_type"]


def test_surface_judge_wrong_on_verbose_original():
    # arith_add's rejected response is a verbose wrong answer and its
    # chosen response is a bare "42.": the surface judge prefers the
    # longer text even with no injection. That is the length bias the
    # paper's Finding 6 calls persistent, and it is why the surface
    # judge's BSR denominator is 7, not 8.
    base = [b for b in BASE_PAIRS if b["id"] == "arith_add"][0]
    pair = original_pair(base)
    assert surface_signal_judge(pair) == "second"
    profile = measure_bias_profile(surface_signal_judge)
    for row in profile["per_type"]:
        assert row["orig_correct"] == 7, row["bias_type"]


def test_surface_judge_bsr_is_one_everywhere():
    # The surface-signal stand-in reads nothing but surface cues, and
    # every base pair except arith_add is surface-symmetric, so any
    # net injected advantage flips it. Measured, not assumed.
    profile = measure_bias_profile(surface_signal_judge)
    assert profile["overall_bsr"] == 1.0
    for row in profile["per_type"]:
        assert row["bsr"] == 1.0, row["bias_type"]
        assert row["flips"] == 7, row["bias_type"]


def test_bsr_formula_counts_only_originally_correct():
    # A judge that always picks "first": correct on every original
    # pair (chosen is first), wrong on every position-injected pair
    # (chosen is second). BSR must be 1.0 for position and 0.0 for
    # length, scored against each pair's own ground truth. This pins
    # the fix for the original-pair truth bug: comparing the injected
    # pick against the original pair's truth would report 0.0 for
    # position.
    def always_first(pair):
        return "first"

    length_row = bias_sensitivity_rate(always_first, "length")
    assert length_row["orig_correct"] == 8
    assert length_row["flips"] == 0
    assert length_row["bsr"] == 0.0
    position_row = bias_sensitivity_rate(always_first, "position")
    assert position_row["orig_correct"] == 8
    assert position_row["flips"] == 8
    assert position_row["bsr"] == 1.0

    # A judge that always picks "second" gets no original pair right,
    # so BSR is undefined (None), never 0.0.
    def always_second(pair):
        return "second"

    row = bias_sensitivity_rate(always_second, "length")
    assert row["orig_correct"] == 0
    assert row["bsr"] is None


def test_agentic_cases_cover_three_tiers():
    tiers = [c["tier"] for c in AGENTIC_CASES]
    assert tiers == ["easy", "easy", "medium", "medium", "hard", "hard"]
    for case in AGENTIC_CASES:
        assert len(case["traces"]) == 2
        assert {t["ground_truth"] for t in case["traces"]} == {
            "correct",
            "incorrect",
        }


def test_get_agentic_case_unknown_raises():
    try:
        get_agentic_case("nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_agentic_alignment_with_ground_truth_is_perfect():
    result = measure_agentic_alignment(dag_judge_with_gt)
    assert result["aligned"] == 12
    assert result["total"] == 12
    assert result["overall"] == 1.0
    for tier in ("easy", "medium", "hard"):
        assert result["per_tier"][tier]["aligned"] == 4


def test_agentic_alignment_without_ground_truth():
    # The plausibility-only judge cannot see a wrong argument, a
    # wrong order that still ends on the final step, or a missing
    # middle step, so it misjudges exactly three faulty traces:
    # refund before eligibility, the 20% discount, and the missing
    # discount. Alignment degrades monotonically with difficulty,
    # the paper's directional finding.
    result = measure_agentic_alignment(dag_judge_without_gt)
    assert result["aligned"] == 9
    assert result["total"] == 12
    assert result["overall"] == 0.75
    assert result["per_tier"]["easy"]["aligned"] == 4
    assert result["per_tier"]["medium"]["aligned"] == 3
    assert result["per_tier"]["hard"]["aligned"] == 2
    per_case = {c["id"]: c for c in result["per_case"]}
    assert per_case["send_invoice"]["aligned"] == 1
    assert per_case["invoice_missing_step"]["aligned"] == 1
    assert per_case["refund_order"]["aligned"] == 1


def test_runner_summary_matches_measured_profile():
    # The runner's summary.json (written by run_judge_bias_scenarios.py)
    # must agree with a fresh measurement. The runner is run by hand
    # before the suite; this test reads what it wrote.
    path = os.path.join(
        os.path.dirname(__file__), "..", "evals", "reports", "judgebias",
        "summary.json",
    )
    assert os.path.exists(path), "run evals/run_judge_bias_scenarios.py first"
    with open(path) as fh:
        summary = json.load(fh)
    assert summary["bias_types"] == 12
    assert summary["agentic_cases"] == 6
    assert summary["agentic_traces"] == 12
    surface = summary["bias_profiles"]["surface_signal_judge"]
    strict = summary["bias_profiles"]["strict_judge"]
    assert surface["overall_bsr"] == 1.0
    assert strict["overall_bsr"] == 0.0
    assert summary["agentic_alignment"]["with_ground_truth"]["overall"] == 1.0
    assert summary["agentic_alignment"]["without_ground_truth"]["overall"] == 0.75
