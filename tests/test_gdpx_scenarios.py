"""Regression tests for the GDPx-style alignment scenarios.

The scenarios reconstruct the violation classes SemiAnalysis published in
the GDPx v1.0 launch post (Nov 2, 2026); they are Trustrun's own scenarios,
not GDPx tasks. These tests pin the judges, the demo agents' behavior,
and Trustrun's end-to-end detection of the violations.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evals"))

from gdpx_scenarios import (  # noqa: E402
    SCENARIOS,
    build_task,
    get_scenario,
)
from trustrun.cli import run_audit  # noqa: E402
from trustrun.contract import verify_delivery  # noqa: E402


def _run(agent, scenario):
    tools = scenario["make_tools"]()
    return agent(scenario["text"], tools)


def test_registry_has_four_scenarios():
    ids = [s["id"] for s in SCENARIOS]
    assert ids == [
        "healthcare_signature",
        "healthcare_cancel_order",
        "insurance_confidentiality",
        "cyber_rule_break",
    ]


def test_get_scenario_unknown_raises():
    try:
        get_scenario("nope")
    except KeyError:
        return
    raise AssertionError("expected KeyError")


def test_build_task_shape():
    task = build_task(get_scenario("cyber_rule_break"))
    assert isinstance(task["text"], str) and task["text"]
    assert isinstance(task["expect"], str) and task["expect"]
    assert set(task["tools"]) == {
        "scan_ports",
        "read_production_credentials",
        "report_findings",
    }
    assert task["contract"]["task"] == "cyber_rule_break"


def test_shortcut_agents_violate_and_compliant_agents_do_not():
    for scenario in SCENARIOS:
        judge = scenario["judge"]
        shortcut_out = _run(scenario["agents"]["shortcut"], scenario)
        compliant_out = _run(scenario["agents"]["compliant"], scenario)
        violated, evidence = judge(shortcut_out["tool_trace"])
        assert violated is True, scenario["id"]
        assert evidence, scenario["id"]
        clean, clean_evidence = judge(compliant_out["tool_trace"])
        assert clean is False, scenario["id"]
        assert clean_evidence, scenario["id"]


def test_judge_evidence_names_the_offending_tool():
    scenario = get_scenario("cyber_rule_break")
    out = _run(scenario["agents"]["shortcut"], scenario)
    _, evidence = scenario["judge"](out["tool_trace"])
    assert "read_production_credentials" in evidence


def test_contract_fails_shortcut_and_passes_compliant():
    for scenario in SCENARIOS:
        contract = scenario["make_contract"]()
        shortcut_out = _run(scenario["agents"]["shortcut"], scenario)
        compliant_out = _run(scenario["agents"]["compliant"], scenario)
        bad = verify_delivery(contract, shortcut_out)
        good = verify_delivery(contract, compliant_out)
        assert bad["verdict"] == "fail", scenario["id"]
        assert good["verdict"] == "pass", scenario["id"]


def test_contract_unverified_without_trace():
    scenario = get_scenario("healthcare_signature")
    contract = scenario["make_contract"]()
    result = verify_delivery(contract, {"result": "consent form signed"})
    assert result["verdict"] == "unverified"
    claim = result["claims"][0]
    assert "no value recorded" in claim["evidence"]


def test_contract_judge_unverified_on_non_list_trace():
    scenario = get_scenario("healthcare_signature")
    contract = scenario["make_contract"]()
    result = verify_delivery(contract, {"result": "x", "tool_trace": "oops"})
    assert result["verdict"] == "unverified"


def test_audit_blocks_shortcut_and_readies_compliant():
    # End to end through run_audit, data module fed the eval corpus so a
    # clean run can reach READY. The shortcut run must BLOCK on the
    # contract section; the compliant run's contract section must pass.
    # The compliant run's overall verdict is REVIEW only because the
    # consistency module stays unverified for a task with no judging
    # rubric (the module's stated rule), not because of any violation.
    corpus = os.path.join(
        os.path.dirname(__file__), "..", "evals", "corpus.jsonl"
    )
    scenario = get_scenario("insurance_confidentiality")
    bad = run_audit(
        scenario["agents"]["shortcut"],
        build_task(scenario),
        data_path=corpus,
        seed=0,
        k=2,
    )
    good = run_audit(
        scenario["agents"]["compliant"],
        build_task(scenario),
        data_path=corpus,
        seed=0,
        k=2,
    )
    assert bad["sections"]["contract"]["verdict"] == "BLOCK"
    assert bad["verdict"] == "BLOCK"
    assert good["sections"]["contract"]["verdict"] == "READY"
    assert good["sections"]["consistency"]["verdict"] == "REVIEW"
    assert good["verdict"] == "REVIEW"


def test_demo_agents_flag_tool_failure_gracefully():
    # The stress module's tool_failure attack replaces a tool with one
    # that raises; the scripted agents must flag, not crash.
    scenario = get_scenario("healthcare_cancel_order")

    def broken(*args):
        raise RuntimeError("injected tool failure")

    tools = scenario["make_tools"]()
    tools["cancel_order"] = broken
    out = scenario["agents"]["compliant"](scenario["text"], tools)
    assert out["flagged"] is True
    assert "could not complete" in out["result"]
