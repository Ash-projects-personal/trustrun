"""Tests for the contract module: verify_delivery."""

import json
from pathlib import Path

import pytest

from trustrun.contract import verify_delivery
from trustrun.contract.dogfood import (
    CHEAT_CASES,
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


@needs_pact_data
def test_dogfood_full_counts():
    reports, totals = run_dogfood()
    # Counts track the local Pact experiment data file: 19 cases, 7
    # seller attacks, 6 api attacks, 1 limit case. Updated 2026-11-02
    # when two cases were added to that file.
    assert len(reports) == 33
    assert totals["pass"] == 32
    assert totals["fail"] == 1
    assert totals["unverified"] == 0
    assert totals["claims_pass"] == 121
    assert totals["claims_fail"] == 1
    assert totals["claims_unverified"] == 0
    failed = [name for name, r in reports if r["verdict"] == "fail"]
    assert len(failed) == 1 and "Translation" in failed[0]


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
