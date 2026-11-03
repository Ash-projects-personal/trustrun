"""Tests for the CLI audit flow. All deterministic, fixed seeds."""

import json

import pytest

from trustrun.cli import (
    _data_section,
    _overall_verdict,
    build_parser,
    format_report,
    run_audit,
)
from trustrun.consistency import flaky_agent_factory, steady_agent
from trustrun.stress import demo_tools


def _task(**overrides):
    base = {
        "text": "What is the capital of France?",
        "expect": "Paris",
        "tools": demo_tools(),
        "variants": [
            {"text": "Name the capital of France.", "expect": "Paris"},
            {"text": "Which city is the capital of France?", "expect": "Paris"},
        ],
        "rubric": ["mentions the capital", "cites sources"],
    }
    base.update(overrides)
    return base


def test_overall_verdict_precedence():
    assert _overall_verdict(["READY", "READY", "READY", "READY"]) == "READY"
    assert _overall_verdict(["READY", "REVIEW", "READY", "READY"]) == "REVIEW"
    assert _overall_verdict(["REVIEW", "REVIEW", "REVIEW", "REVIEW"]) == "REVIEW"
    assert _overall_verdict(["READY", "BLOCK", "READY", "READY"]) == "BLOCK"
    assert _overall_verdict(["BLOCK", "REVIEW", "READY", "REVIEW"]) == "BLOCK"
    assert _overall_verdict(["REVIEW", "BLOCK", "REVIEW", "BLOCK"]) == "BLOCK"


def test_steady_agent_sections_have_evidence():
    report = run_audit(steady_agent, _task(), k=5, seed=0)
    assert set(report["sections"]) == {"contract", "stress", "consistency", "data"}
    contract = report["sections"]["contract"]
    assert contract["verdict"] == "READY"
    assert contract["passed"] == 1
    assert contract["claims"][0]["verdict"] == "pass"
    assert contract["claims"][0]["evidence"]
    consistency = report["sections"]["consistency"]
    assert consistency["verdict"] == "READY"
    assert consistency["pass_rate_1"] == 1.0
    assert consistency["pass_rate_k"] == 1.0
    assert consistency["variance_flag"] is False
    assert consistency["cheating_flag"] is False
    assert consistency["variance_evidence"]
    stress = report["sections"]["stress"]
    # perturbation, tool failure, 3 injections, 2 monitor tampering
    assert len(stress["attacks"]) == 7
    assert all(a["evidence"] for a in stress["attacks"])
    # steady_agent takes no tools, so tool channel attacks are unmeasured
    assert report["tools_capable"] is False
    tool_attacks = [a for a in stress["attacks"] if a["kind"] != "perturbation"]
    assert all(a["survived"] == "unverified" for a in tool_attacks)
    assert stress["attacks"][0]["survived"] is True


def test_no_data_flag_gives_review_data_section():
    report = run_audit(steady_agent, _task(), k=5, seed=0)
    data = report["sections"]["data"]
    assert data["verdict"] == "REVIEW"
    assert data["module_verdict"] == "unverified"
    assert data["records"] is None
    assert "no dataset given" in data["note"]
    # data REVIEW keeps the whole report out of READY
    assert report["verdict"] == "REVIEW"


def test_data_section_standalone_without_path():
    section = _data_section(None)
    assert section["verdict"] == "REVIEW"
    assert section["module_verdict"] == "unverified"


def test_data_section_with_jsonl(tmp_path):
    path = tmp_path / "records.jsonl"
    rows = [{"text": "record number %d about Paris" % i} for i in range(20)]
    rows.append({"text": rows[0]["text"]})
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    report = run_audit(steady_agent, _task(), data_path=str(path), k=3, seed=0)
    data = report["sections"]["data"]
    assert data["records"] == 21
    assert data["skipped"] == 0
    assert set(data["metrics"]) == {
        "exact_duplicates",
        "near_duplicates",
        "template_clusters",
    }
    # one exact duplicate in 21 rows is over the 0.1 percent review line
    assert data["metrics"]["exact_duplicates"]["verdict"] == "review"


def test_data_loader_dolly_shape_fallback(tmp_path):
    path = tmp_path / "dolly.jsonl"
    rows = [
        {"instruction": "instruct %d" % i, "input": "input %d" % i, "output": "out %d" % i}
        for i in range(12)
    ]
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
        handle.write("not json\n")
        handle.write(json.dumps({"nope": 1}) + "\n")
    report = run_audit(steady_agent, _task(), data_path=str(path), k=3, seed=0)
    data = report["sections"]["data"]
    assert data["records"] == 12
    assert data["skipped"] == 2


def test_flaky_agent_is_blocked():
    report = run_audit(flaky_agent_factory(3), _task(), k=10, seed=3)
    consistency = report["sections"]["consistency"]
    assert consistency["cheating_flag"] is True
    assert consistency["verdict"] == "BLOCK"
    assert report["verdict"] == "BLOCK"


def test_zero_pass_rate_is_block_not_ready():
    def always_wrong(task_text):
        return {"result": "I do not know."}

    report = run_audit(always_wrong, _task(), k=5, seed=0)
    consistency = report["sections"]["consistency"]
    assert consistency["module_verdict"] == "pass"
    assert consistency["pass_rate_k"] == 0.0
    assert consistency["verdict"] == "BLOCK"
    assert "0 of 5 runs" in consistency["note"]
    assert report["verdict"] == "BLOCK"


def test_audit_is_deterministic():
    first = run_audit(steady_agent, _task(), k=5, seed=0)
    second = run_audit(steady_agent, _task(), k=5, seed=0)
    assert first == second
    flaky_first = run_audit(flaky_agent_factory(3), _task(), k=10, seed=3)
    flaky_second = run_audit(flaky_agent_factory(3), _task(), k=10, seed=3)
    assert flaky_first == flaky_second


def test_type_errors():
    with pytest.raises(TypeError):
        run_audit("not a callable", _task())
    with pytest.raises(TypeError):
        run_audit(steady_agent, "not a dict")
    with pytest.raises(TypeError):
        run_audit(steady_agent, _task(), k=0)


def test_tools_capable_agent_gets_full_stress_battery():
    from trustrun.stress import careful_agent

    report = run_audit(careful_agent, _task(), k=3, seed=0)
    assert report["tools_capable"] is True
    attacks = report["sections"]["stress"]["attacks"]
    by_kind = {}
    for attack in attacks:
        by_kind.setdefault(attack["kind"], []).append(attack)
    assert len(by_kind["perturbation"]) == 1
    assert len(by_kind["tool_failure"]) == 1
    assert len(by_kind["injection"]) == 3
    # careful_agent flags plaintext injection and survives the tool failure
    plaintext = [a for a in by_kind["injection"] if a.get("encoding") == "plaintext"][0]
    assert plaintext["survived"] is True
    assert plaintext["detected"] is True


def test_format_report_shows_all_sections(capsys):
    report = run_audit(steady_agent, _task(), k=5, seed=0)
    text = format_report(report)
    assert "Trustrun audit report" in text
    for section in ("contract", "stress", "consistency", "data"):
        assert "[%s]" % section in text
    assert "Overall: %s" % report["verdict"] in text


def test_parser_accepts_audit_args(tmp_path):
    task_path = tmp_path / "task.json"
    task_path.write_text(json.dumps({"text": "t", "expect": "e"}), encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(
        [
            "audit",
            "trustrun.consistency:steady_agent",
            str(task_path),
            "--data",
            "rows.jsonl",
            "--k",
            "7",
            "--seed",
            "2",
        ]
    )
    assert args.command == "audit"
    assert args.agent == "trustrun.consistency:steady_agent"
    assert args.k == 7
    assert args.seed == 2
    assert args.data == "rows.jsonl"


def test_report_notes_agent_error_not_wrong_answer():
    def erroring_agent(text):
        return {"result": "AGENT-ERROR: ProviderError: content filtered"}

    report = run_audit(
        erroring_agent, {"text": "What is 12 times 12?", "expect": "144"}, k=1
    )
    text = format_report(report)
    assert "agent errored, not a wrong answer" in text
    # the taxonomy is unchanged: an errored contract still blocks
    assert report["verdict"] == "BLOCK"
    assert report["sections"]["contract"]["verdict"] == "BLOCK"


def test_report_omits_note_for_plain_wrong_answer():
    def wrong_agent(text):
        return {"result": "999"}

    report = run_audit(
        wrong_agent, {"text": "What is 12 times 12?", "expect": "144"}, k=1
    )
    text = format_report(report)
    assert "agent errored, not a wrong answer" not in text
    assert report["verdict"] == "BLOCK"
