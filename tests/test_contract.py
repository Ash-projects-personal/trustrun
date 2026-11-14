"""Tests for the contract module: verify_delivery."""

import json
from pathlib import Path

import pytest

from trustrun.contract import verify_delivery
from trustrun.contract.dogfood import (
    CHEAT_CASES,
    _expected_settlement,
    _settlement_judge,
    contract_for_case,
    data_available,
    load_records,
    run_dogfood,
)

needs_pact_data = pytest.mark.skipif(
    not data_available(),
    reason="Pact experiment data not available on this machine")


def test_exact_pass():
    contract = {"task": "t", "claims": [
        {"id": "outcome", "statement": "s", "kind": "exact", "expected": "released"}]}
    report = verify_delivery(contract, {"outcome": "released"})
    assert report["verdict"] == "pass"
    assert report["passed"] == 1
    assert report["claims"][0]["evidence"] != ""


def test_exact_fail():
    contract = {"task": "t", "claims": [
        {"id": "outcome", "statement": "s", "kind": "exact", "expected": "released"}]}
    report = verify_delivery(contract, {"outcome": "refunded"})
    assert report["verdict"] == "fail"
    assert report["failed"] == 1
    assert "refunded" in report["claims"][0]["evidence"]


def test_contains_pass_and_fail():
    contract = {"task": "t", "claims": [
        {"id": "checks", "statement": "s", "kind": "contains", "expected": "/"}]}
    assert verify_delivery(contract, {"checks": "5/5"})["verdict"] == "pass"
    assert verify_delivery(contract, {"checks": "none"})["verdict"] == "fail"


def test_numeric_tolerance():
    contract = {"task": "t", "claims": [
        {"id": "price", "statement": "s", "kind": "numeric",
         "expected": 74.06, "tolerance": 0.01}]}
    assert verify_delivery(contract, {"price": 74.06})["verdict"] == "pass"
    assert verify_delivery(contract, {"price": 74.065})["verdict"] == "pass"
    assert verify_delivery(contract, {"price": 75.00})["verdict"] == "fail"


def test_numeric_non_number_is_unverified():
    contract = {"task": "t", "claims": [
        {"id": "price", "statement": "s", "kind": "numeric", "expected": 74.06}]}
    report = verify_delivery(contract, {"price": "seventy four"})
    assert report["verdict"] == "unverified"
    assert report["unverified"] == 1


def test_missing_field_is_unverified_not_pass():
    contract = {"task": "t", "claims": [
        {"id": "bond_status", "statement": "s", "kind": "exact", "expected": "returned"}]}
    report = verify_delivery(contract, {"outcome": "released"})
    assert report["verdict"] == "unverified"
    assert report["claims"][0]["evidence"] != ""


def test_none_value_is_unverified():
    contract = {"task": "t", "claims": [
        {"id": "outcome", "statement": "s", "kind": "exact", "expected": "released"}]}
    assert verify_delivery(contract, {"outcome": None})["verdict"] == "unverified"


def test_unknown_kind_is_unverified():
    contract = {"task": "t", "claims": [
        {"id": "outcome", "statement": "s", "kind": "magic", "expected": "released"}]}
    assert verify_delivery(contract, {"outcome": "released"})["verdict"] == "unverified"


def test_judge_pass_fail_and_cannot_decide():
    def judge(value, claim, output):
        if value == "yes":
            return True, "said yes"
        if value == "no":
            return False, "said no"
        return None, "unclear"

    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "judge", "judge": judge}]}
    assert verify_delivery(contract, {"a": "yes"})["verdict"] == "pass"
    assert verify_delivery(contract, {"a": "no"})["verdict"] == "fail"
    report = verify_delivery(contract, {"a": "maybe"})
    assert report["verdict"] == "unverified"


def test_judge_without_callable_is_unverified():
    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "judge"}]}
    assert verify_delivery(contract, {"a": "yes"})["verdict"] == "unverified"


def test_overall_verdict_prefers_fail_then_unverified():
    ok = {"task": "t", "claims": [{"id": "a", "statement": "s", "kind": "exact", "expected": "x"}]}
    assert verify_delivery(ok, {"a": "x"})["verdict"] == "pass"

    mixed_fail = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "exact", "expected": "x"},
        {"id": "b", "statement": "s", "kind": "exact", "expected": "y"}]}
    assert verify_delivery(mixed_fail, {"a": "x", "b": "z"})["verdict"] == "fail"

    mixed_unverified = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "exact", "expected": "x"},
        {"id": "b", "statement": "s", "kind": "exact", "expected": "y"}]}
    assert verify_delivery(mixed_unverified, {"a": "x"})["verdict"] == "unverified"

    fail_beats_unverified = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "exact", "expected": "x"},
        {"id": "b", "statement": "s", "kind": "exact", "expected": "y"}]}
    assert verify_delivery(fail_beats_unverified, {"a": "z"})["verdict"] == "fail"


def test_field_override():
    contract = {"task": "t", "claims": [
        {"id": "bond_ok", "statement": "s", "kind": "exact",
         "expected": "returned", "field": "bond_status"}]}
    assert verify_delivery(contract, {"bond_status": "returned"})["verdict"] == "pass"


def test_rejects_non_dict_inputs():
    with pytest.raises(TypeError):
        verify_delivery("not a dict", {})
    with pytest.raises(TypeError):
        verify_delivery({}, "not a dict")


@needs_pact_data
def test_dogfood_two_real_cases():
    results, attacks = load_records()
    honest = results["cases"][0]
    cheat = results["cases"][1]
    assert 1 in CHEAT_CASES and 0 not in CHEAT_CASES
    honest_report = verify_delivery(contract_for_case(honest, "honest"), honest)
    cheat_report = verify_delivery(contract_for_case(cheat, "cheat"), cheat)
    assert honest_report["verdict"] == "pass"
    assert cheat_report["verdict"] == "pass"
    assert honest_report["passed"] == 5
    assert cheat_report["passed"] == 5


def test_settlement_judge_graded_partial():
    # Regression (2026-11-11): Pact's graded settlement re-graded case 2
    # to 1/5 checks with a partial settlement. The old two-branch judge
    # demanded a full refund for any non-full pass and failed the case.
    assert _expected_settlement({"checks": "5/5"}) == (
        "released", "released", "returned")
    assert _expected_settlement({"checks": "0/5"}) == (
        "refunded", "refunded", "slashed")
    assert _expected_settlement({"checks": "1/5"}) == (
        "graded", "partially_released", "partially_slashed")
    partial = {"outcome": "graded",
               "payment_status": "partially_released",
               "bond_status": "partially_slashed"}
    assert _settlement_judge("1/5", None, partial)[0] is True
    assert _settlement_judge("1/5", None, {
        "outcome": "refunded", "payment_status": "refunded",
        "bond_status": "slashed"})[0] is False
    assert _settlement_judge("0/5", None, {
        "outcome": "refunded", "payment_status": "refunded",
        "bond_status": "slashed"})[0] is True
    case = {"case": "synthetic partial cheat", "checks": "1/5",
            "negotiated_price": 100.0, "bond": 20.0,
            "outcome": "graded",
            "payment_status": "partially_released",
            "bond_status": "partially_slashed"}
    assert verify_delivery(
        contract_for_case(case, "cheat"), case)["verdict"] == "pass"


@needs_pact_data
def test_dogfood_full_counts():
    reports, totals = run_dogfood()
    # Counts track the local Pact experiment data file: 28 cases, 13
    # adversarial attacks (A1-A5 incl. A2b/A2c, B1-B6), 1 limit case.
    # Updated 2026-11-02 when two cases were added; updated 2026-11-03
    # when the "Email newsletter issue, cheat writer" case (0/5 checks,
    # refunded, bond slashed) was added; updated 2026-11-04 when the
    # "Product photography set, cheat photographer" case was added;
    # updated 2026-11-05 when the "Book cover design package, cheat
    # designer" case (0/5 checks, refunded, bond slashed) was added;
    # updated 2026-11-06 when the "API integration task, cheat
    # integrator" case (0/5 checks, refunded, bond slashed) was added;
    # updated 2026-11-07 when the "AC repair service, cheat
    # technician" case (0/5 checks, refunded, bond slashed) was added;
    # updated 2026-11-08 when the "Spreadsheet cleanup and report,
    # cheat analyst" case (0/5 checks, refunded, bond slashed) was
    # added; updated 2026-11-09 when the "Landing page copy, cheat
    # copywriter" case (0/5 checks, refunded, bond slashed) was added;
    # updated 2026-11-10 when the "Logo and brand kit, cheat
    # designer" case (0/5 checks, refunded, bond slashed) was added;
    # updated 2026-11-11 when the "Python script task, cheat coder"
    # case (0/5 checks, refunded, bond slashed) was added; updated
    # 2026-11-11 when graded settlement re-graded case 2 ("Social pack,
    # recycled copy cheat") to 1/5 checks with a partial settlement —
    # the contract now derives the expected settlement from the check
    # fraction, so the counts below are unchanged by that re-grade;
    # updated again 2026-11-11 when the Pact build's 20:36 UTC rewrite
    # renamed the partial outcome label from "partially_settled" to
    # "graded" (Pact's own vocabulary, pact/store.py) and the contract
    # followed it — counts still unchanged; updated 2026-11-12 when
    # the Pact data file gained its 29th case, "Market research brief,
    # cheat researcher" (index 28, 0/5 checks, refunded, bond
    # slashed), so CHEAT_CASES gained 28 and the counts below moved
    # by one report and five passing claims.
    # All cheat cases are labeled in CHEAT_CASES, so they are judged
    # against the cheat contract and PASS (correctly caught cheats).
    assert len(reports) == 43
    assert totals["pass"] == 42
    assert totals["fail"] == 1
    assert totals["unverified"] == 0
    assert totals["claims_pass"] == 171
    assert totals["claims_fail"] == 1
    assert totals["claims_unverified"] == 0
    failed = [name for name, r in reports if r["verdict"] == "fail"]
    assert failed == ["Translation, 1,000 words at the $10 Fiverr tier (limit case)"]


@needs_pact_data
def test_cheat_cases_cover_all_cheat_records():
    # Regression: a cheat record missing from CHEAT_CASES is judged
    # against the honest contract and gets a wrong "fail" verdict.
    # This fails loudly when Pact adds a cheat case that dogfood.py
    # has not labeled yet.
    results, _ = load_records()
    cases = results["cases"]
    for i in CHEAT_CASES:
        assert i < len(cases), "CHEAT_CASES index %d beyond data file" % i
    # In the Pact experiment data every cheat deal is refunded with the
    # bond slashed, or — under graded settlement (2026-11-11) — settled
    # as "graded" with the bond partially slashed when it passes some
    # checks; and every honest deal is released with the bond returned:
    # the settlement outcome derives from the recorded data itself, not
    # from case-name heuristics.
    settled_cheat = {i for i, c in enumerate(cases)
                     if (c.get("outcome") == "refunded"
                         and c.get("bond_status") == "slashed")
                     or (c.get("outcome") == "graded"
                         and c.get("bond_status") == "partially_slashed")}
    assert settled_cheat == CHEAT_CASES, (
        "CHEAT_CASES %s does not match settled cheat cases %s in the "
        "Pact data file" % (sorted(CHEAT_CASES), sorted(settled_cheat)))


# agent error distinction: an errored claim fails, but is flagged as an
# error rather than a wrong answer. The taxonomy does not change.


def _answer_contract():
    return {"task": "t", "claims": [
        {"id": "answer", "statement": "s", "kind": "contains",
         "expected": "144", "field": "result"}]}


def test_agent_error_fail_is_flagged():
    report = verify_delivery(
        _answer_contract(), {"result": "AGENT-ERROR: ProviderError: filtered"})
    assert report["verdict"] == "fail"
    assert report["failed"] == 1
    assert report["claims"][0]["agent_error"] is True


def test_wrong_answer_fail_is_not_flagged():
    report = verify_delivery(_answer_contract(), {"result": "999"})
    assert report["verdict"] == "fail"
    assert report["claims"][0]["agent_error"] is False


def test_passing_claim_is_not_flagged():
    report = verify_delivery(_answer_contract(), {"result": "144"})
    assert report["verdict"] == "pass"
    assert report["claims"][0]["agent_error"] is False


def test_missing_value_is_not_flagged():
    report = verify_delivery(_answer_contract(), {"other": "x"})
    assert report["verdict"] == "unverified"
    assert report["claims"][0]["agent_error"] is False


# TRUSTRUN-UnableToVerify: the third verdict state is named, reasoned,
# and never counted as a pass.


def test_empty_expected_contains_is_unverified_not_vacuous_pass():
    # Regression: "" is inside every string, so a contains claim with
    # an empty expected used to pass vacuously. An empty expectation
    # checks nothing, so it is unverified, never a pass.
    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "contains", "expected": ""}]}
    report = verify_delivery(contract, {"a": "anything at all"})
    assert report["verdict"] == "unverified"
    assert report["claims"][0]["reason"] == "no_expected"


def test_none_expected_exact_is_unverified():
    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "exact", "expected": None}]}
    report = verify_delivery(contract, {"a": "x"})
    assert report["verdict"] == "unverified"
    assert report["claims"][0]["reason"] == "no_expected"


def test_unverified_reason_codes():
    missing = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "exact", "expected": "x"}]}
    assert verify_delivery(missing, {})["claims"][0]["reason"] == "missing_value"

    unknown = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "magic", "expected": "x"}]}
    assert verify_delivery(unknown, {"a": "x"})["claims"][0]["reason"] == "unknown_kind"

    def abstain(value, claim, output):
        return None, "cannot tell"

    judge_contract = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "judge", "judge": abstain}]}
    report = verify_delivery(judge_contract, {"a": "maybe"})
    assert report["claims"][0]["reason"] == "judge_abstained"

    numeric = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "numeric", "expected": 1.0}]}
    report = verify_delivery(numeric, {"a": "not a number"})
    assert report["claims"][0]["reason"] == "non_numeric"


def test_checked_reason_on_decided_claims():
    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "exact", "expected": "x"},
        {"id": "b", "statement": "s", "kind": "exact", "expected": "y"}]}
    report = verify_delivery(contract, {"a": "x", "b": "z"})
    assert report["claims"][0]["reason"] == "checked"
    assert report["claims"][1]["reason"] == "checked"


def test_pass_rate_verifiable_excludes_unverified():
    # One pass, one unverified: the verifiable rate is 1.0, the naive
    # passed-over-total rate would be 0.5. The unverifiable share is
    # reported beside it, so the padded rate cannot stand alone.
    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "exact", "expected": "x"},
        {"id": "b", "statement": "s", "kind": "exact", "expected": "y"}]}
    report = verify_delivery(contract, {"a": "x"})
    assert report["pass_rate_verifiable"] == 1.0
    assert report["unverifiable_share"] == 0.5
    assert report["passed"] / len(report["claims"]) == 0.5


def test_pass_rate_none_when_nothing_verifiable():
    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "exact", "expected": "x"}]}
    report = verify_delivery(contract, {})
    assert report["pass_rate_verifiable"] is None
    assert report["unverifiable_share"] == 1.0


def test_rates_on_empty_contract():
    report = verify_delivery({"task": "t", "claims": []}, {})
    assert report["verdict"] == "pass"
    assert report["pass_rate_verifiable"] is None
    assert report["unverifiable_share"] == 0.0


def test_multi_trial_judge_abstain_reason():
    def abstain(value, claim, output):
        return None, "cannot tell"

    contract = {"task": "t", "claims": [
        {"id": "a", "statement": "s", "kind": "judge", "judge": abstain}]}
    report = verify_delivery(contract, {"a": "maybe"}, judge_trials=11)
    assert report["verdict"] == "unverified"
    assert report["claims"][0]["reason"] == "judge_abstained"
