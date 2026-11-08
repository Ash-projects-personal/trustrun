"""Tests for the contract JudgeRedesign: multi-trial judging, kappa,
binary coverage, panels, and tool-access judges."""

import pytest

from trustrun.contract import verify_delivery
from trustrun.contract.judge import (
    MIN_TRIALS,
    binary_coverage,
    fleiss_kappa,
    judge_claim_trials,
    majority_vote,
)


def _flip_on_trials(flip_trials):
    """A judge that returns False on the given trial indices, True else."""
    def judge(value, claim, output, context):
        if context["trial"] in flip_trials:
            return False, "flipped on trial %d" % context["trial"]
        return True, "correct on trial %d" % context["trial"]
    return judge


def _judge_contract(n_judge_claims=2, n_rule_claims=1):
    claims = []
    for i in range(n_judge_claims):
        claims.append({"id": "j%d" % i, "statement": "judged %d" % i,
                       "kind": "judge", "judge": _flip_on_trials(set())})
    for i in range(n_rule_claims):
        claims.append({"id": "r%d" % i, "statement": "rule %d" % i,
                       "kind": "exact", "expected": "yes"})
    return {"task": "t", "claims": claims}


def _output_for(contract):
    output = {}
    for claim in contract["claims"]:
        if claim["kind"] == "judge":
            output[claim["id"]] = "yes"
        else:
            output[claim["id"]] = "yes"
    return output


# --- Fleiss' kappa ---

def test_fleiss_kappa_hand_computed():
    # A: 2 pass 1 fail; B: 1 pass 2 fail; 3 raters. kappa = -1/3.
    ratings = [["pass", "pass", "fail"], ["fail", "fail", "pass"]]
    assert fleiss_kappa(ratings) == pytest.approx(-1 / 3, abs=1e-9)


def test_fleiss_kappa_perfect_agreement_is_one():
    ratings = [["pass", "pass", "pass"], ["fail", "fail", "fail"]]
    assert fleiss_kappa(ratings) == pytest.approx(1.0, abs=1e-9)


def test_fleiss_kappa_single_category_is_none():
    ratings = [["pass", "pass"], ["pass", "pass"]]
    assert fleiss_kappa(ratings) is None


def test_fleiss_kappa_single_subject_is_none():
    # One subject makes kappa an artifact (-1/(n-1)); never report it.
    ratings = [["pass", "pass", "fail"]]
    assert fleiss_kappa(ratings) is None


def test_fleiss_kappa_rejects_unequal_raters():
    with pytest.raises(ValueError):
        fleiss_kappa([["pass", "pass"], ["pass"]])


def test_fleiss_kappa_rejects_bad_category():
    with pytest.raises(ValueError):
        fleiss_kappa([["pass", "maybe"], ["pass", "fail"]])


# --- Majority vote ---

def test_majority_vote_picks_majority():
    verdict, share = majority_vote(["pass"] * 7 + ["fail"] * 4)
    assert verdict == "pass"
    assert share == pytest.approx(7 / 11, abs=1e-9)


def test_majority_vote_tie_is_unverified():
    verdict, share = majority_vote(["pass", "fail"])
    assert verdict == "unverified"
    assert share == pytest.approx(0.5, abs=1e-9)


def test_majority_vote_empty_is_unverified():
    verdict, share = majority_vote([])
    assert verdict == "unverified"
    assert share == 0.0


# --- Binary coverage ---

def test_binary_coverage_counts_atoms():
    contract = _judge_contract(n_judge_claims=1, n_rule_claims=2)
    assert binary_coverage(contract) == pytest.approx(2 / 3, abs=1e-9)


def test_binary_coverage_empty_contract_is_one():
    assert binary_coverage({"task": "t", "claims": []}) == 1.0


def test_min_trials_is_eleven():
    assert MIN_TRIALS == 11


# --- Default behavior is unchanged ---

def test_default_single_trial_has_no_reliability_keys():
    contract = _judge_contract()
    report = verify_delivery(contract, _output_for(contract))
    assert "judge_reliability" not in report
    assert all("trials" not in c for c in report["claims"])
    assert report["verdict"] == "pass"


def test_judge_trials_below_one_is_rejected():
    with pytest.raises(ValueError):
        verify_delivery(_judge_contract(), {}, judge_trials=0)


# --- Multi-trial path ---

def test_multi_trial_noisy_judge_recovers_verdict_and_reports_kappa():
    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "a", "kind": "judge",
         "judge": _flip_on_trials({2, 5})},
        {"id": "b", "statement": "b", "kind": "judge",
         "judge": _flip_on_trials({3})},
        {"id": "c", "statement": "c", "kind": "exact", "expected": "yes"},
    ]}
    report = verify_delivery(contract, {"a": "yes", "b": "yes", "c": "yes"},
                             judge_trials=11, seed=0)
    assert report["verdict"] == "pass"
    by_id = {c["id"]: c for c in report["claims"]}
    assert by_id["a"]["flip_rate"] == pytest.approx(2 / 11, abs=1e-9)
    assert by_id["b"]["flip_rate"] == pytest.approx(1 / 11, abs=1e-9)
    assert by_id["a"]["majority_share"] == pytest.approx(9 / 11, abs=1e-9)
    # 9 pass/2 fail vs 10 pass/1 fail across 11 raters: kappa = -0.0807.
    assert by_id["a"]["kappa"] == pytest.approx(-0.0807, abs=1e-3)
    assert by_id["b"]["kappa"] == by_id["a"]["kappa"]
    # Rule-kind claim stays deterministic.
    assert by_id["c"]["trials"] == 1
    assert by_id["c"]["flip_rate"] == 0.0
    assert by_id["c"]["deterministic"] is True
    rel = report["judge_reliability"]
    assert rel["trials"] == 11
    assert rel["min_trials"] == 11
    assert rel["binary_coverage"] == pytest.approx(1 / 3, abs=1e-9)
    assert rel["judge_claims"] == 2
    assert rel["mean_flip_rate"] == pytest.approx(1.5 / 11, abs=1e-9)
    assert rel["kappa"] == pytest.approx(-0.0807, abs=1e-3)
    assert rel["positions_randomized"] is True


def test_position_biased_judge_shows_instability():
    def biased(value, claim, output, context):
        if context["position"] == 0:
            return True, "position 0 says pass"
        return False, "position 1 says fail"

    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "a", "kind": "judge", "judge": biased},
        {"id": "b", "statement": "b", "kind": "judge", "judge": biased},
    ]}
    report = verify_delivery(contract, {"a": "yes", "b": "yes"},
                             judge_trials=11, seed=0)
    by_id = {c["id"]: c for c in report["claims"]}
    # The judge flips with the position draw, so the verdict is unstable
    # and the report says so instead of hiding it behind one trial.
    # (With seed 0 the first claim draws 8 pass positions and 3 fail,
    # so the flip rate is 3/11; the point is it is not a clean 0.0.)
    assert by_id["a"]["flip_rate"] > 0.0
    assert by_id["a"]["majority_share"] < 1.0
    assert report["judge_reliability"]["mean_flip_rate"] > 0.0


def test_single_judge_claim_kappa_is_none():
    contract = _judge_contract(n_judge_claims=1, n_rule_claims=0)
    report = verify_delivery(contract, _output_for(contract),
                             judge_trials=11, seed=0)
    assert report["claims"][0]["kappa"] is None
    assert report["judge_reliability"]["kappa"] is None


def test_judge_without_callable_is_unverified_and_excluded():
    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "a", "kind": "judge"},
        {"id": "b", "statement": "b", "kind": "judge",
         "judge": _flip_on_trials({1})},
    ]}
    report = verify_delivery(contract, {"a": "yes", "b": "yes"},
                             judge_trials=11, seed=0)
    by_id = {c["id"]: c for c in report["claims"]}
    assert by_id["a"]["verdict"] == "unverified"
    assert by_id["a"]["n_votes"] == 0
    # The unjudged claim does not drag the mean flip rate to zero.
    assert report["judge_reliability"]["mean_flip_rate"] == pytest.approx(
        1 / 11, abs=1e-9)
    assert report["judge_reliability"]["judge_claims"] == 1


def test_legacy_three_arg_judge_works_in_multi_trial():
    def legacy(value, claim, output):
        return value == "yes", "legacy verdict"

    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "a", "kind": "judge", "judge": legacy},
        {"id": "b", "statement": "b", "kind": "judge", "judge": legacy},
    ]}
    report = verify_delivery(contract, {"a": "yes", "b": "yes"},
                             judge_trials=11, seed=0)
    assert report["verdict"] == "pass"
    assert report["claims"][0]["flip_rate"] == 0.0


def test_raising_judge_is_unverified_per_trial_not_a_crash():
    def flaky(value, claim, output, context):
        if context["trial"] == 0:
            raise RuntimeError("boom")
        return True, "fine after trial 0"

    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "a", "kind": "judge", "judge": flaky},
        {"id": "b", "statement": "b", "kind": "judge", "judge": flaky},
    ]}
    report = verify_delivery(contract, {"a": "yes", "b": "yes"},
                             judge_trials=11, seed=0)
    assert report["claims"][0]["verdict"] == "pass"
    assert report["claims"][0]["flip_rate"] == pytest.approx(1 / 11, abs=1e-9)


# --- Panels and tool access ---

def test_panel_disagreement_is_measured_not_hidden():
    def always_pass(value, claim, output):
        return True, "passer"

    def always_fail(value, claim, output):
        return False, "failer"

    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "a", "kind": "judge"},
        {"id": "b", "statement": "b", "kind": "judge"},
    ]}
    report = verify_delivery(contract, {"a": "yes", "b": "yes"},
                             judge_trials=11,
                             judges=[always_pass, always_fail], seed=0)
    by_id = {c["id"]: c for c in report["claims"]}
    # 11 pass + 11 fail votes tie, so the verdict is unverified.
    assert by_id["a"]["verdict"] == "unverified"
    assert by_id["a"]["flip_rate"] == pytest.approx(0.5, abs=1e-9)
    assert by_id["a"]["family_agreement"] == 0.0
    assert set(by_id["a"]["per_judge"]) == {"always_pass", "always_fail"}
    assert by_id["a"]["per_judge"]["always_pass"]["pass"] == 11
    assert by_id["a"]["per_judge"]["always_fail"]["fail"] == 11
    assert report["judge_reliability"]["family_agreement"] == 0.0


def test_tool_access_judge_uses_the_tool_not_the_text():
    calls = []

    def recompute():
        calls.append(1)
        return 42

    def tool_judge(value, claim, output, context):
        tools = context["tools"]
        if tools["recompute"]() == 42:
            return True, "tool recomputed 42"
        return False, "tool disagrees"

    claim = {"id": "a", "statement": "a", "kind": "judge", "judge": tool_judge}
    record = judge_claim_trials(claim, "not 42", {}, trials=11,
                                tools={"recompute": recompute}, seed=0)
    assert record["verdict"] == "pass"
    assert record["flip_rate"] == 0.0
    assert len(calls) == 11


def test_judge_claim_trials_rejects_bad_trial_count():
    claim = {"id": "a", "statement": "a", "kind": "judge",
             "judge": _flip_on_trials(set())}
    with pytest.raises(ValueError):
        judge_claim_trials(claim, "yes", {}, trials=0)
