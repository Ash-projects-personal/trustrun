"""Tests for the ContractTarget calibration harness."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trustrun.contract.calibration import calibrate_judge  # noqa: E402


def _strict_judge(value, claim, output):
    expect = output.get("expect", "")
    if isinstance(value, str) and expect and expect in value:
        return True, "contains"
    return False, "missing"


def _pairs():
    return [
        {
            "id": "p1",
            "claim": {"id": "a", "statement": "answers", "kind": "judge"},
            "value": "the capital is Paris",
            "output": {"expect": "Paris"},
            "expected": "pass",
        },
        {
            "id": "p2",
            "claim": {"id": "a", "statement": "answers", "kind": "judge"},
            "value": "the capital is London",
            "output": {"expect": "Paris"},
            "expected": "fail",
        },
        {
            "id": "p3",
            "claim": {"id": "a", "statement": "answers", "kind": "judge"},
            "value": "4",
            "output": {"expect": "4"},
            "expected": "pass",
        },
        {
            "id": "p4",
            "claim": {"id": "a", "statement": "answers", "kind": "judge"},
            "value": "5",
            "output": {"expect": "4"},
            "expected": "fail",
        },
    ]


def test_deterministic_panel_agrees_with_labels():
    report = calibrate_judge(_pairs(), trials=11, judges=[_strict_judge], seed=0)
    assert report["n"] == 4
    assert report["agreement"] == 1.0
    assert report["agreement_decided"] == 1.0
    assert report["mean_flip_rate"] == 0.0
    # All votes agree within each pair and both categories are present.
    assert report["kappa"] == 1.0
    assert all(r["agree"] for r in report["pairs"])


def test_empty_pairs():
    report = calibrate_judge([], trials=11, judges=[_strict_judge])
    assert report["n"] == 0
    assert report["agreement"] is None
    assert report["agreement_decided"] is None
    assert report["kappa"] is None
    assert report["pairs"] == []


def test_single_pair_kappa_is_none():
    report = calibrate_judge(_pairs()[:1], trials=11, judges=[_strict_judge])
    assert report["n"] == 1
    assert report["agreement"] == 1.0
    assert report["kappa"] is None


def test_inverted_panel_agrees_with_nothing():
    def _wrong_judge(value, claim, output):
        decision, evidence = _strict_judge(value, claim, output)
        return (not decision), "inverted"

    report = calibrate_judge(_pairs(), trials=11, judges=[_wrong_judge], seed=0)
    assert report["agreement"] == 0.0


def test_noisy_panel_still_recovers_ground_truth():
    import random

    rng = random.Random(7)

    def _noisy_judge(value, claim, output):
        decision, evidence = _strict_judge(value, claim, output)
        if rng.random() < 0.10:
            return (not decision), "noisy flip"
        return decision, evidence

    report = calibrate_judge(
        _pairs(), trials=11, judges=[_strict_judge, _noisy_judge], seed=0
    )
    assert report["agreement"] == 1.0
    assert report["mean_flip_rate"] > 0.0
    assert report["kappa"] is not None and report["kappa"] > 0.5


def test_bad_expected_raises():
    pairs = _pairs()
    pairs[0]["expected"] = "maybe"
    try:
        calibrate_judge(pairs, trials=11, judges=[_strict_judge])
    except ValueError:
        return
    raise AssertionError("expected ValueError for a bad expected verdict")


def test_bad_pairs_type_raises():
    try:
        calibrate_judge("not a list")
    except TypeError:
        return
    raise AssertionError("expected TypeError for a non-list pairs argument")
