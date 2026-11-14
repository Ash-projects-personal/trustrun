"""Tests for the AGORA IRT judge-panel aggregation (TRUSTRUN-AGORA-Aggregate)."""

import pytest

from trustrun.contract import verify_delivery
from trustrun.contract.agora import (
    aggregate_panel,
    dispersion,
    majority_verdicts,
    ratings_from_trial_records,
)
from trustrun.contract.judge import judge_claim_trials


def test_dispersion_zero_when_all_agree():
    ratings = [["pass", "pass", "pass"], ["fail", "fail", "fail"]]
    assert dispersion(ratings) == 0.0


def test_dispersion_one_when_every_pair_disagrees():
    ratings = [["pass", "fail"], ["pass", "fail"]]
    assert dispersion(ratings) == 1.0


def test_dispersion_partial_disagreement():
    # Pairs: (pass, pass) agree, (pass, fail) disagree twice: 2/3.
    ratings = [["pass", "pass", "fail"]]
    assert dispersion(ratings) == pytest.approx(2.0 / 3.0)


def test_dispersion_single_judge_is_zero():
    assert dispersion([["pass"], ["fail"]]) == 0.0


def test_majority_verdicts_tie_is_unverified():
    assert majority_verdicts([["pass", "fail"]]) == ["unverified"]
    assert majority_verdicts([["pass", "pass", "fail"]]) == ["pass"]


def test_aggregate_rejects_bad_ratings():
    with pytest.raises(ValueError):
        aggregate_panel([])
    with pytest.raises(ValueError):
        aggregate_panel([["pass"], ["pass", "fail"]])
    with pytest.raises(ValueError):
        aggregate_panel([["pass", "maybe"]])
    with pytest.raises(ValueError):
        aggregate_panel([["pass", "fail"]], judge_names=["only-one"])


def test_aggregate_single_judge_falls_back_to_majority():
    result = aggregate_panel([["pass"], ["fail"], ["pass"]])
    assert result["method"] == "majority"
    assert result["verdicts"] == ["pass", "fail", "pass"]
    assert result["trust_weights"] is None
    assert any("one judge" in note for note in result["notes"])


def test_aggregate_single_item_falls_back_to_majority():
    result = aggregate_panel([["pass", "fail", "pass"]])
    assert result["method"] == "majority"
    assert result["verdicts"] == ["pass"]
    assert any("one item" in note for note in result["notes"])


def test_aggregate_no_disagreement_falls_back_to_majority():
    result = aggregate_panel([["pass", "pass"], ["pass", "pass"]])
    assert result["method"] == "majority"
    assert result["verdicts"] == ["pass", "pass"]
    assert any("no disagreement" in note for note in result["notes"])


def test_aggregate_weights_sum_to_one():
    ratings = [
        ["pass", "pass", "fail", "fail", "pass"],
        ["fail", "fail", "pass", "pass", "fail"],
        ["pass", "fail", "pass", "fail", "pass"],
        ["fail", "pass", "fail", "pass", "fail"],
        ["pass", "pass", "pass", "fail", "fail"],
        ["fail", "fail", "fail", "pass", "pass"],
    ]
    result = aggregate_panel(ratings)
    assert result["method"] == "agora"
    assert sum(result["trust_weights"].values()) == pytest.approx(1.0)
    assert len(result["verdicts"]) == len(ratings)
    assert all(v in ("pass", "fail", "unverified")
               for v in result["verdicts"])


def test_aggregate_is_deterministic():
    ratings = [
        ["pass", "pass", "fail", "fail", "pass"],
        ["fail", "fail", "pass", "pass", "fail"],
        ["pass", "fail", "pass", "fail", "pass"],
        ["fail", "pass", "fail", "pass", "fail"],
        ["pass", "pass", "pass", "fail", "fail"],
        ["fail", "fail", "fail", "pass", "pass"],
    ]
    first = aggregate_panel(ratings)
    second = aggregate_panel(ratings)
    assert first["verdicts"] == second["verdicts"]
    assert first["trust_weights"] == second["trust_weights"]
    assert first["thetas"] == second["thetas"]


def _simulate(reliabilities, n_items, seed):
    import random
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
                    [c for c in ("pass", "fail", "unverified")
                     if c != truth]))
        ratings.append(row)
    return truths, ratings


def _agreement(verdicts, truths):
    return sum(1 for v, t in zip(verdicts, truths) if v == t) / len(truths)


def test_uneven_pool_agora_beats_majority():
    # The paper's regime: uneven reliability, small validation set.
    # Measured 2026-11-10 (3-seed mean, n=50): majority 0.767,
    # AGORA 0.933. The test uses 2 seeds and the cheaper fit; the
    # margin is large enough to hold.
    majority_scores = []
    agora_scores = []
    for seed in (0, 1):
        truths, ratings = _simulate(
            [0.95, 0.9, 0.6, 0.5, 0.15], 50, seed)
        result = aggregate_panel(ratings, max_iter=30)
        assert result["method"] == "agora"
        majority_scores.append(
            _agreement(result["majority_verdicts"], truths))
        agora_scores.append(_agreement(result["verdicts"], truths))
    mean_majority = sum(majority_scores) / len(majority_scores)
    mean_agora = sum(agora_scores) / len(agora_scores)
    assert mean_agora > mean_majority + 0.05


def test_even_pool_agora_does_not_harm_much():
    # Control: equally reliable judges. Weighting should not help and
    # should not cost much. Measured 2026-11-10 (3-seed mean, n=50):
    # majority 0.987, AGORA 0.960.
    majority_scores = []
    agora_scores = []
    for seed in (0, 1):
        truths, ratings = _simulate([0.85] * 5, 50, seed)
        result = aggregate_panel(ratings, max_iter=30)
        assert result["method"] == "agora"
        majority_scores.append(
            _agreement(result["majority_verdicts"], truths))
        agora_scores.append(_agreement(result["verdicts"], truths))
    mean_majority = sum(majority_scores) / len(majority_scores)
    mean_agora = sum(agora_scores) / len(agora_scores)
    assert mean_agora >= mean_majority - 0.05


def test_ratings_from_trial_records():
    # Two claims, two judges, three trials each. Votes are round-major
    # (round 0: A, B; round 1: A, B; round 2: A, B). Judge A always
    # passes claim 1 and fails claim 2; judge B splits 2-1 each way.
    records = [
        {"votes": ["pass", "pass", "pass", "fail", "pass", "pass"],
         "per_judge": {"judge_a": {"pass": 3, "fail": 0, "unverified": 0},
                       "judge_b": {"pass": 2, "fail": 1, "unverified": 0}}},
        {"votes": ["fail", "fail", "fail", "pass", "fail", "fail"],
         "per_judge": {"judge_a": {"pass": 0, "fail": 3, "unverified": 0},
                       "judge_b": {"pass": 1, "fail": 2, "unverified": 0}}},
    ]
    ratings, names = ratings_from_trial_records(records)
    assert names == ["judge_a", "judge_b"]
    assert ratings == [["pass", "pass"], ["fail", "fail"]]


def test_ratings_from_real_trial_records():
    def always_pass(value, claim, output):
        return True, "yes"

    def always_fail(value, claim, output):
        return False, "no"

    claim = {"id": "c1", "statement": "s", "kind": "judge"}
    record = judge_claim_trials(
        claim, "x", {}, trials=3,
        judges=[always_pass, always_fail], seed=0)
    ratings, names = ratings_from_trial_records([record])
    assert names == ["always_pass", "always_fail"]
    assert ratings == [["pass", "fail"]]


def _panel_contract():
    def always_pass(value, claim, output):
        return True, "yes"

    def always_fail(value, claim, output):
        return False, "no"

    def mixed(value, claim, output):
        return (True, "yes") if claim["id"] in ("c1", "c2") else (False, "no")

    return {
        "task": "t",
        "claims": [
            {"id": "c1", "statement": "s", "kind": "judge",
             "judge": always_pass},
            {"id": "c2", "statement": "s", "kind": "judge",
             "judge": always_pass},
            {"id": "c3", "statement": "s", "kind": "judge",
             "judge": always_pass},
        ],
    }, [always_pass, always_fail, mixed]


def test_verify_delivery_agora_section():
    contract, panel = _panel_contract()
    report = verify_delivery(contract, {"c1": "x", "c2": "x", "c3": "x"},
                             judge_trials=11, judges=panel,
                             aggregate="agora", seed=0)
    assert "agora" in report["judge_reliability"]
    section = report["judge_reliability"]["agora"]
    assert section["claim_ids"] == ["c1", "c2", "c3"]
    assert set(section["verdicts"]) == {"c1", "c2", "c3"}
    assert section["trust_weights"] is not None
    assert sum(section["trust_weights"].values()) == pytest.approx(1.0)
    # Per-claim verdicts stay majority: AGORA is reported alongside,
    # never silently substituted.
    assert [c["verdict"] for c in report["claims"]] == [
        section["majority_verdicts"][cid] for cid in ("c1", "c2", "c3")]


def test_verify_delivery_default_has_no_agora_section():
    contract, panel = _panel_contract()
    report = verify_delivery(contract, {"c1": "x", "c2": "x", "c3": "x"},
                             judge_trials=11, judges=panel, seed=0)
    assert "agora" not in report["judge_reliability"]


def test_verify_delivery_bad_aggregate_value():
    contract, _panel = _panel_contract()
    with pytest.raises(ValueError):
        verify_delivery(contract, {"c1": "x"}, aggregate="bogus")


def test_verify_delivery_agora_falls_back_with_one_claim():
    def always_pass(value, claim, output):
        return True, "yes"

    def always_fail(value, claim, output):
        return False, "no"

    contract = {"task": "t", "claims": [
        {"id": "c1", "statement": "s", "kind": "judge",
         "judge": always_pass}]}
    report = verify_delivery(contract, {"c1": "x"}, judge_trials=11,
                             judges=[always_pass, always_fail],
                             aggregate="agora", seed=0)
    section = report["judge_reliability"]["agora"]
    assert section["method"] == "majority"
    # Two judges split 11-11: a tie resolves to unverified, the same
    # rule as the per-claim verdict.
    assert section["verdicts"] == {"c1": "unverified"}
    assert report["claims"][0]["verdict"] == "unverified"
    assert any("one item" in note for note in section["notes"])
