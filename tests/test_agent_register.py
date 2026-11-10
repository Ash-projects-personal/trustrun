"""Tests for the agent register: audit-derived register entry and
decision record.

All deterministic, fixed seeds. The tamper cases flip one value at
a time and assert verification names the exact entry that fails.
"""

import copy
import json

import pytest

from trustrun.agent_register import (
    RETENTION_MONTHS,
    TOOL_RISKS,
    assess_human_involvement,
    build_decision_record,
    build_register_entry,
    decision_records,
    format_decision_record,
    reconstruction_answers,
    register_agent,
    verify_decision_record,
    verify_register_text,
)
from trustrun.cli import run_audit
from trustrun.consistency import steady_agent
from trustrun.evidence import verify_anchor
from trustrun.stress import demo_tools


def _registration(**overrides):
    base = {
        "agent_id": "agent-001",
        "name": "billing-helper",
        "owner": "Ash Shetty",
        "purpose": "answer billing questions from the docs",
        "tools": [{"name": "search_docs", "risk": "read"},
                  {"name": "calculator", "risk": "read"}],
    }
    base.update(overrides)
    return register_agent(**base)


def _fixture_report(**overrides):
    base = {
        "agent": "steady_agent",
        "task": "What is the capital of France?",
        "k": 5,
        "seed": 0,
        "verdict": "REVIEW",
        "sections": {
            "contract": {
                "verdict": "READY",
                "module_verdict": "pass",
                "passed": 1,
                "failed": 0,
                "unverified": 0,
                "claims": [{
                    "id": "answer",
                    "statement": "the output answers the task",
                    "verdict": "pass",
                    "evidence": "expected 'Paris' inside recorded "
                                "'Paris'",
                }],
            },
            "stress": {
                "verdict": "REVIEW",
                "attacks": [{
                    "kind": "injection",
                    "vector": "plaintext",
                    "survived": True,
                    "detected": False,
                    "completed": True,
                    "evidence": "output unaffected",
                }],
            },
            "consistency": {
                "verdict": "READY",
                "module_verdict": "pass",
                "pass_rate_1": 1.0,
                "pass_rate_k": 1.0,
                "variance_flag": False,
                "cheating_flag": False,
            },
            "data": {
                "verdict": "READY",
                "module_verdict": "pass",
                "records": 312,
                "metrics": {},
            },
        },
    }
    base.update(overrides)
    return base


def _entry(report=None, **kwargs):
    report = report or _fixture_report()
    return build_register_entry(report, _registration(), **kwargs)


def _record(report=None, entry=None):
    report = report or _fixture_report()
    entry = entry or _entry(report)
    return build_decision_record(report, entry)


# --- registration ---

def test_register_agent_happy_path():
    reg = _registration(model="sonnet-5.5", version="2026-11-08")
    assert reg["agent_id"] == "agent-001"
    assert reg["owner"] == "Ash Shetty"
    assert reg["tools"][0] == {"name": "search_docs", "risk": "read"}
    assert reg["model"] == "sonnet-5.5"
    assert reg["version"] == "2026-11-08"


def test_register_agent_tool_risk_defaults_to_read():
    reg = _registration(tools=[{"name": "search_docs"}])
    assert reg["tools"] == [{"name": "search_docs", "risk": "read"}]


def test_register_agent_rejects_missing_owner():
    with pytest.raises(ValueError):
        _registration(owner="  ")


def test_register_agent_rejects_missing_purpose():
    with pytest.raises(ValueError):
        _registration(purpose="")


def test_register_agent_rejects_blank_agent_id_and_name():
    with pytest.raises(ValueError):
        _registration(agent_id="")
    with pytest.raises(ValueError):
        _registration(name=None)


def test_register_agent_rejects_unknown_tool_risk():
    with pytest.raises(ValueError):
        _registration(tools=[{"name": "shell", "risk": "root"}])


def test_register_agent_rejects_nameless_tool_and_bad_tools_type():
    with pytest.raises(ValueError):
        _registration(tools=[{"risk": "read"}])
    with pytest.raises(ValueError):
        _registration(tools="search_docs")


def test_tool_risks_are_the_three_tiers():
    assert TOOL_RISKS == ("read", "write", "destructive")


# --- human involvement ---

def test_human_involvement_defaults_to_not_meaningful():
    result = assess_human_involvement(_fixture_report())
    assert result["meaningful"] is False
    assert "post-hoc" in result["evidence"]
    assert result["basis"] == ["no_checkpoint_in_audit"]


def test_human_involvement_named_checkpoints_count():
    result = assess_human_involvement(
        _fixture_report(),
        human_checkpoints=["operator reviewed the output before send"])
    assert result["meaningful"] is True
    assert "operator reviewed" in result["evidence"]
    assert result["basis"] == ["named_checkpoint"]


def test_human_involvement_agent_escalation_counts():
    report = _fixture_report()
    report["sections"]["contract"]["claims"][0]["evidence"] = (
        "agent asked the user for clarification before answering")
    result = assess_human_involvement(report)
    assert result["meaningful"] is True
    assert "asked the user" in result["evidence"]
    assert result["basis"] == ["agent_escalated"]


def test_human_involvement_rejects_bad_inputs():
    with pytest.raises(TypeError):
        assess_human_involvement("not a report")
    with pytest.raises(ValueError):
        assess_human_involvement(_fixture_report(),
                                 human_checkpoints=["  "])


# --- register entry ---

def test_build_entry_carries_verdicts_and_retention():
    entry = _entry()
    assert entry["audit"]["verdict"] == "REVIEW"
    assert entry["audit"]["contract"] == "READY"
    assert entry["audit"]["stress"] == "REVIEW"
    assert entry["retention_months"] == RETENTION_MONTHS == 6
    assert entry["registration"]["agent_id"] == "agent-001"


def test_build_entry_tools_unobserved_is_unverified_not_assumed():
    entry = _entry()
    assert entry["audit"]["tools_observed"] == "unverified"
    assert "unverified" in entry["reconstruction"]["what_it_accessed"]


def test_build_entry_tools_observed_sorted_and_deduped():
    entry = _entry(tools_observed=["calculator", "search_docs",
                                   "calculator"])
    assert entry["audit"]["tools_observed"] == ["calculator",
                                                "search_docs"]
    assert "calculator" in entry["reconstruction"]["what_it_accessed"]


def test_build_entry_reconstruction_answers_four_questions():
    entry = _entry(tools_observed=["search_docs"],
                   human_checkpoints=["operator reviewed the output"])
    answers = entry["reconstruction"]
    assert "billing-helper" in answers["which_agent"]
    assert "Ash Shetty" in answers["which_agent"]
    assert "capital of France" in answers["under_what_authority"]
    assert "search_docs" in answers["what_it_accessed"]
    assert answers["was_human_involvement_meaningful"].startswith("yes")


def test_build_entry_rejects_bad_inputs():
    with pytest.raises(TypeError):
        build_register_entry("not a report", _registration())
    with pytest.raises(TypeError):
        build_register_entry(_fixture_report(), "not a registration")
    with pytest.raises(ValueError):
        build_register_entry(_fixture_report(), _registration(),
                             tools_observed="search_docs")


def test_reconstruction_answers_standalone():
    entry = _entry()
    answers = reconstruction_answers(entry)
    assert set(answers) == {"which_agent", "under_what_authority",
                            "what_it_accessed",
                            "was_human_involvement_meaningful"}
    assert answers["was_human_involvement_meaningful"].startswith("no")


# --- decision records ---

def test_decision_records_register_first_then_verdicts():
    records = decision_records(_fixture_report(), _entry())
    assert records[0]["record"] == "register"
    assert records[0]["owner"] == "Ash Shetty"
    assert records[1]["record"] == "authority"
    assert records[2]["record"] == "human_involvement"
    assert records[2]["meaningful"] is False
    assert records[3]["section"] == "audit"
    claim = [r for r in records
             if r.get("section") == "contract"
             and r.get("claim") == "answer"]
    assert len(claim) == 1
    assert claim[0]["verdict"] == "pass"


def test_decision_records_are_json_safe():
    records = decision_records(_fixture_report(), _entry())
    for record in records:
        json.dumps(record)


def test_build_decision_record_deterministic_and_valid():
    first = _record()
    second = _record()
    assert first["head"] == second["head"]
    assert first["version"] == 1
    assert first["algorithm"] == "sha256"
    result = verify_decision_record(first)
    assert result == {"valid": True, "bad_index": None,
                      "reason": "chain valid"}


def test_evidence_verify_anchor_accepts_our_anchor():
    # The chain construction is the same as trustrun.evidence by
    # design; the other module's verifier must agree.
    anchor = _record()
    assert verify_anchor(anchor)["valid"] is True


def test_tamper_register_record_fails_at_index_zero():
    anchor = _record()
    tampered = copy.deepcopy(anchor)
    tampered["entries"][0]["record"]["owner"] = "someone else"
    result = verify_decision_record(tampered)
    assert result["valid"] is False
    assert result["bad_index"] == 0


def test_tamper_claim_verdict_fails_at_that_entry():
    report = _fixture_report()
    anchor = _record(report)
    index = next(i for i, item in enumerate(anchor["entries"])
                 if item["record"].get("section") == "contract"
                 and item["record"].get("claim") == "answer")
    tampered = copy.deepcopy(anchor)
    tampered["entries"][index]["record"]["verdict"] = "fail"
    result = verify_decision_record(tampered)
    assert result["valid"] is False
    assert result["bad_index"] == index


def test_tamper_head_fails():
    anchor = _record()
    tampered = copy.deepcopy(anchor)
    tampered["head"] = "0" * 64
    result = verify_decision_record(tampered)
    assert result["valid"] is False


def test_verify_decision_record_rejects_bad_inputs():
    with pytest.raises(TypeError):
        verify_decision_record("not a record")
    assert verify_decision_record(
        {"version": 99, "algorithm": "sha256", "entries": [],
         "head": "0" * 64})["valid"] is False


# --- text rendering ---

def test_format_and_verify_register_text_round_trip():
    entry = _entry(tools_observed=["search_docs"])
    anchor = _record(entry=entry)
    text = "\n".join(format_decision_record(entry, anchor))
    assert "billing-helper" in text
    assert "Ash Shetty" in text
    assert "6 months" in text
    result = verify_register_text(text)
    assert result["valid"] is True
    assert result["head"] == anchor["head"]


def test_verify_register_text_tampered_line_fails():
    entry = _entry()
    anchor = _record(entry=entry)
    lines = format_decision_record(entry, anchor)
    lines[10] = lines[10].replace("Ash Shetty", "Mallory")
    result = verify_register_text("\n".join(lines))
    assert result["valid"] is False


def test_verify_register_text_no_block_fails():
    assert verify_register_text(
        "Trustrun agent register entry\nno chain here\n")["valid"] \
        is False


def test_verify_register_text_head_mismatch_fails():
    entry = _entry()
    anchor = _record(entry=entry)
    lines = format_decision_record(entry, anchor)
    head_line = next(i for i, line in enumerate(lines)
                     if line.startswith("[register]"))
    lines[head_line] = lines[head_line].replace(
        anchor["head"], "0" * 64)
    result = verify_register_text("\n".join(lines))
    assert result["valid"] is False


# --- live demo on a real audit ---

def test_live_audit_registers_and_verifies():
    task = {
        "text": "What is the capital of France?",
        "expect": "Paris",
        "tools": demo_tools(),
        "variants": [
            {"text": "Name the capital of France.", "expect": "Paris"},
            {"text": "Which city is the capital of France?",
             "expect": "Paris"},
        ],
        "rubric": ["mentions the capital", "cites sources"],
    }
    report = run_audit(steady_agent, task, k=5, seed=0)
    registration = register_agent(
        "steady-001", "steady-agent", "Ash Shetty",
        "answer factual questions from the docs",
        tools=[{"name": "search_docs", "risk": "read"}])
    entry = build_register_entry(
        report, registration,
        tools_observed=["search_docs", "calculator"])
    assert entry["audit"]["verdict"] == report["verdict"]
    anchor = build_decision_record(report, entry)
    assert verify_decision_record(anchor)["valid"] is True
    text = "\n".join(format_decision_record(entry, anchor))
    assert verify_register_text(text)["valid"] is True
    assert "steady-agent" in entry["reconstruction"]["which_agent"]
