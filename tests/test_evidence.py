"""Tests for the evidence anchor: hash chain over report verdicts.

All deterministic, fixed seeds. The tamper cases flip one value at
a time and assert verification names the exact entry that fails.
"""

import copy
import json

import pytest

from trustrun.cli import format_report, main, run_audit
from trustrun.consistency import steady_agent
from trustrun.evidence import (
    _ENTRY_RE,
    build_anchor,
    format_anchor_lines,
    verify_anchor,
    verify_report_text,
)
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


def _report():
    return run_audit(steady_agent, _task(), k=5, seed=0)


def test_anchor_is_deterministic():
    first = build_anchor(_report())
    second = build_anchor(_report())
    assert first["head"] == second["head"]
    assert first["entries"] == second["entries"]


def test_anchor_covers_all_four_sections_and_overall():
    anchor = build_anchor(_report())
    sections = [entry["record"]["section"] for entry in anchor["entries"]]
    assert sections[0] == "audit"
    assert sections[-1] == "overall"
    assert "contract" in sections
    assert "stress" in sections
    assert "consistency" in sections
    assert "data" in sections
    # 1 audit + 1 contract verdict + 1 claim + 1 stress verdict
    # + 13 stress attacks + 1 consistency + 1 data verdict
    # + 1 overall = 20 entries. A section with no items still
    # contributes its verdict record.
    assert len(anchor["entries"]) == 20
    assert anchor["version"] == 1
    assert anchor["algorithm"] == "sha256"


def test_run_audit_carries_a_valid_anchor():
    report = _report()
    assert "evidence" in report
    result = verify_anchor(report["evidence"])
    assert result["valid"] is True
    assert result["bad_index"] is None


def test_anchor_head_changes_when_a_verdict_changes():
    report = _report()
    before = build_anchor(report)["head"]
    changed = copy.deepcopy(report)
    changed["sections"]["contract"]["claims"][0]["verdict"] = "fail"
    assert build_anchor(changed)["head"] != before


def test_verify_anchor_catches_a_flipped_claim_verdict():
    anchor = build_anchor(_report())
    tampered = copy.deepcopy(anchor)
    # Entry 2 is the contract claim (0 audit, 1 contract verdict).
    tampered["entries"][2]["record"]["verdict"] = "fail"
    result = verify_anchor(tampered)
    assert result["valid"] is False
    assert result["bad_index"] == 2


def test_verify_anchor_catches_a_flipped_stress_outcome():
    anchor = build_anchor(_report())
    tampered = copy.deepcopy(anchor)
    stress_entry = next(
        e for e in tampered["entries"]
        if e["record"].get("section") == "stress"
    )
    stress_entry["record"]["survived"] = False
    result = verify_anchor(tampered)
    assert result["valid"] is False
    assert result["bad_index"] == stress_entry["index"]


def test_verify_anchor_catches_a_deleted_entry():
    anchor = build_anchor(_report())
    tampered = copy.deepcopy(anchor)
    del tampered["entries"][5]
    result = verify_anchor(tampered)
    assert result["valid"] is False
    # The entry after the gap no longer links to its predecessor.
    assert result["bad_index"] == 5


def test_verify_anchor_catches_a_reordered_entry():
    anchor = build_anchor(_report())
    tampered = copy.deepcopy(anchor)
    tampered["entries"][2], tampered["entries"][3] = (
        tampered["entries"][3],
        tampered["entries"][2],
    )
    result = verify_anchor(tampered)
    assert result["valid"] is False
    assert result["bad_index"] == 2


def test_verify_anchor_catches_a_wrong_head():
    anchor = build_anchor(_report())
    tampered = copy.deepcopy(anchor)
    tampered["head"] = "0" * 64
    result = verify_anchor(tampered)
    assert result["valid"] is False
    assert result["bad_index"] is None


def test_verify_anchor_rejects_a_non_dict_anchor():
    with pytest.raises(TypeError):
        verify_anchor(["not", "a", "dict"])


def test_verify_anchor_rejects_a_wrong_version():
    anchor = build_anchor(_report())
    anchor["version"] = 99
    result = verify_anchor(anchor)
    assert result["valid"] is False


def test_format_report_round_trip_verifies():
    report = _report()
    text = format_report(report)
    assert "[evidence] sha256 head" in text
    result = verify_report_text(text)
    assert result["valid"] is True
    assert result["head"] == report["evidence"]["head"]


def test_verify_report_text_catches_an_edited_evidence_line():
    report = _report()
    text = format_report(report)
    lines = text.splitlines()
    edited = []
    for line in lines:
        # Entry 2 is the contract claim (0 audit, 1 contract verdict).
        if line.startswith("  #2 ") and '"verdict":"pass"' in line:
            line = line.replace('"verdict":"pass"', '"verdict":"fail"')
        edited.append(line)
    result = verify_report_text("\n".join(edited))
    assert result["valid"] is False
    assert result["bad_index"] == 2


def test_verify_report_text_catches_a_deleted_line():
    report = _report()
    text = format_report(report)
    lines = [line for line in text.splitlines()
             if not line.startswith("  #5 ")]
    result = verify_report_text("\n".join(lines))
    assert result["valid"] is False
    assert result["bad_index"] == 5


def test_verify_report_text_catches_a_wrong_head_line():
    report = _report()
    text = format_report(report)
    tampered = text.replace(
        report["evidence"]["head"], "0" * 64, 1
    )
    result = verify_report_text(tampered)
    assert result["valid"] is False


def test_verify_report_text_rejects_a_report_without_an_anchor():
    result = verify_report_text("Trustrun audit report\nOverall: READY\n")
    assert result["valid"] is False
    assert "no evidence anchor" in result["reason"]


def test_anchor_covers_unverifiable_values():
    # A toolless agent leaves tool-channel attacks unverified; the
    # chain must cover those gaps, not drop them.
    report = run_audit(steady_agent, _task(), k=5, seed=0)
    anchor = report["evidence"]
    stress_records = [e["record"] for e in anchor["entries"]
                      if e["record"].get("section") == "stress"
                      and "attack" in e["record"]]
    assert any(r["survived"] == "unverified" for r in stress_records)
    assert verify_anchor(anchor)["valid"] is True


def test_verify_subcommand_accepts_a_valid_report(tmp_path, capsys):
    report = _report()
    path = tmp_path / "report.txt"
    path.write_text(format_report(report), encoding="utf-8")
    assert main(["verify", str(path)]) == 0
    assert "VALID evidence chain" in capsys.readouterr().out


def test_verify_subcommand_rejects_a_tampered_report(tmp_path, capsys):
    report = _report()
    text = format_report(report)
    tampered = text.replace('"verdict":"pass"', '"verdict":"fail"', 1)
    assert tampered != text
    path = tmp_path / "report.txt"
    path.write_text(tampered, encoding="utf-8")
    assert main(["verify", str(path)]) == 1
    assert "TAMPERED at entry 2" in capsys.readouterr().out


def test_verify_subcommand_missing_file_exits_2():
    with pytest.raises(SystemExit) as exc:
        main(["verify", "/nonexistent/report.txt"])
    assert exc.value.code == 2


def test_format_anchor_lines_are_single_lines():
    anchor = build_anchor(_report())
    lines = format_anchor_lines(anchor)
    assert len(lines) == len(anchor["entries"]) + 1
    for line in lines:
        assert "\n" not in line
    # Every entry line parses back to its record.
    for entry, line in zip(anchor["entries"], lines[1:]):
        match = _ENTRY_RE.match(line)
        assert match is not None
        assert int(match.group(1)) == entry["index"]
        assert match.group(2) == entry["hash"]
        assert match.group(3) == entry["prev"]
        assert json.loads(match.group(4)) == entry["record"]
