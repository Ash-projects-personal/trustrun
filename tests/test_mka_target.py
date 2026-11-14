"""Tests for the MKA eval target (TRUSTRUN-MKA-Target).

Covers the criterion classifier, the deterministic judges, the runner
on fake agents, determinism, and the vendored task data (10 public
MKA tasks, 835 criteria).
"""

import json
import os

import pytest

from trustrun.mka_target import (
    classify_criterion,
    criterion_claim,
    run_mka_task,
    run_mka_target,
    task_contract,
)

HERE = os.path.dirname(os.path.abspath(__file__))
MKA_TASKS = os.path.join(HERE, "..", "evals", "mka", "tasks.json")

KNOWN_TASK_IDS = {
    "task_143a5623f26c404baaeb63ccd891e196",
    "task_4308eaef4d504328988c1cb5dfd7db77",
    "task_47d262f6d58c4e5293a22623f0d711e5",
    "task_5a0212833c224c85b79960604679eb84",
    "task_9e3bdd2bdccd4164bcc792c914f59925",
    "task_a46a6c3cebd54b82b9ad5e66d1e14e48",
    "task_c9ab91021dc14eab926dfea0a208108a",
    "task_dd94dc222db74864a13fcb7c6c2844a2",
    "task_e49e96e764424db08531c39fb685ed70",
    "task_fea07f327cfd4f4c91af0bf78da197d4",
}


def _load_tasks():
    with open(MKA_TASKS) as handle:
        return json.load(handle)["tasks"]


def _synthetic_task():
    return {
        "task_id": "task_synth",
        "vertical": "Test",
        "domain": "Test",
        "role": "tester",
        "goal": "synthetic",
        "prompt": "Report the area and the study area name.",
        "input_files": "area.geojson",
        "criteria": [
            {
                "id": "criterion 1",
                "description": (
                    "Reports study-area area as 7,464.41 ha."
                    "(Acceptable range : 7,462 - 7,466)"
                ),
                "weight": 2,
                "grading_target": "Word Documents (.docx, .doc, .odt)",
            },
            {
                "id": "criterion 2",
                "description": "States the study area as City of Nottingham (B).",
                "weight": 2,
                "grading_target": "Word Documents (.docx, .doc, .odt)",
            },
            {
                "id": "criterion 3",
                "description": (
                    "Includes a Map of the Study area, showing the building "
                    "footprints, and the study area boundary."
                ),
                "weight": 2,
                "grading_target": "Word Documents (.docx, .doc, .odt)",
            },
            {
                "id": "criterion 4",
                "description": (
                    "States, in Section 0, that DAC_en is the external "
                    "enable signal controlling the RF-DAC clock-generation "
                    "circuitry."
                ),
                "weight": 1,
                "grading_target": "All output (modified files and final message in console)",
            },
        ],
    }


def _judge_claim(claim, deliverable):
    from trustrun.contract import verify_delivery

    contract = {"task": "t", "claims": [claim]}
    report = verify_delivery(contract, {"deliverable": deliverable})
    return report["claims"][0]


# ------------------------------------------------------------- classifier


def test_classify_numeric_comma_range():
    parsed = classify_criterion(
        "Reports study-area area as 7,464.41 ha."
        "(Acceptable range : 7,462 - 7,466)"
    )
    assert parsed["kind"] == "numeric"
    assert parsed["ranges"] == [(7462.0, 7466.0)]


def test_classify_numeric_to_form_and_negative():
    parsed = classify_criterion(
        "Lists the tone near 10.53 GHz with a level of -74.97 dB "
        "(acceptable frequency 10.33 to 10.73 GHz; acceptable level "
        "-76.97 to -74.97 dB)"
    )
    assert parsed["kind"] == "numeric"
    assert parsed["ranges"] == [(10.33, 10.73), (-76.97, -74.97)]


def test_classify_numeric_plus_range():
    parsed = classify_criterion(
        "States, in the Section 3 table, the IRR margin as +44.98 dB "
        "(acceptable range +37.98 to +51.98, with the unit written as dB or dBc)."
    )
    assert parsed["kind"] == "numeric"
    assert parsed["ranges"] == [(37.98, 51.98)]


def test_classify_numeric_unicode_minus_range():
    parsed = classify_criterion(
        "States the change in the gap as \u22121.9 percentage points "
        "(acceptable ranges \u22122.5 to \u22121.3 and \u22121.9 to \u22120.7)"
    )
    assert parsed["kind"] == "numeric"
    assert parsed["ranges"] == [(-2.5, -1.3), (-1.9, -0.7)]


def test_classify_entity_short_value():
    parsed = classify_criterion(
        "States the study area as City of Nottingham (B)."
    )
    assert parsed["kind"] == "entity"
    assert parsed["value"] == "City of Nottingham (B)"
    assert parsed["digits"] == []


def test_classify_entity_with_uprn_token():
    parsed = classify_criterion(
        "Reports Property Name - UPRN ( Queens Court- 200001385371) as Rank 1"
    )
    assert parsed["kind"] == "entity"
    assert parsed["value"] == "Rank 1"
    assert parsed["digits"] == ["200001385371"]


def test_classify_visual_map():
    parsed = classify_criterion(
        "Includes a Map of the Study area, showing the building footprints."
    )
    assert parsed["kind"] == "visual"


def test_classify_visual_plot():
    parsed = classify_criterion("Plots the suitability scores by orientation.")
    assert parsed["kind"] == "visual"


def test_classify_format_zero_asterisk():
    parsed = classify_criterion("Contains zero asterisk characters in the response.")
    assert parsed["kind"] == "format"
    assert parsed["check"] == "zero_asterisk"


def test_classify_format_hyphen_bullets():
    parsed = classify_criterion(
        "Uses a hyphen as the bullet marker on every non-section list item."
    )
    assert parsed["kind"] == "format"
    assert parsed["check"] == "hyphen_bullets"


def test_classify_unparsed_prose_claim():
    parsed = classify_criterion(
        "States, in Section 0, that DAC_en is the external enable signal "
        "controlling the RF-DAC clock-generation circuitry."
    )
    assert parsed["kind"] == "unparsed"


# ------------------------------------------------------------------ judges


def test_numeric_judge_pass_in_range():
    claim = criterion_claim(
        "task_synth",
        {
            "id": "criterion 1",
            "description": (
                "Reports study-area area as 7,464.41 ha."
                "(Acceptable range : 7,462 - 7,466)"
            ),
            "weight": 2,
            "grading_target": "",
        },
    )
    entry = _judge_claim(claim, "The study area covers 7,464.41 ha in total.")
    assert entry["verdict"] == "pass"
    assert entry["reason"] == "checked"


def test_numeric_judge_fail_out_of_range():
    claim = criterion_claim(
        "task_synth",
        {
            "id": "criterion 1",
            "description": (
                "Reports study-area area as 7,464.41 ha."
                "(Acceptable range : 7,462 - 7,466)"
            ),
            "weight": 2,
            "grading_target": "",
        },
    )
    entry = _judge_claim(claim, "The study area covers 9,100 ha in total.")
    assert entry["verdict"] == "fail"


def test_numeric_judge_fail_no_number():
    claim = criterion_claim(
        "task_synth",
        {
            "id": "criterion 1",
            "description": (
                "Reports study-area area as 7,464.41 ha."
                "(Acceptable range : 7,462 - 7,466)"
            ),
            "weight": 2,
            "grading_target": "",
        },
    )
    entry = _judge_claim(claim, "The study area is large.")
    assert entry["verdict"] == "fail"


def test_entity_judge_pass_and_fail():
    claim = criterion_claim(
        "task_synth",
        {
            "id": "criterion 2",
            "description": "States the study area as City of Nottingham (B).",
            "weight": 2,
            "grading_target": "",
        },
    )
    assert _judge_claim(claim, "Study area: City of Nottingham (B).")["verdict"] == "pass"
    assert _judge_claim(claim, "Study area: City of Derby.")["verdict"] == "fail"


def test_entity_judge_missing_uprn_fails():
    claim = criterion_claim(
        "task_synth",
        {
            "id": "criterion 9",
            "description": (
                "Reports Property Name - UPRN ( Queens Court- 200001385371) "
                "as Rank 1"
            ),
            "weight": 2,
            "grading_target": "",
        },
    )
    entry = _judge_claim(claim, "Rank 1: Queens Court.")
    assert entry["verdict"] == "fail"
    entry = _judge_claim(claim, "Rank 1: Queens Court, UPRN 200001385371.")
    assert entry["verdict"] == "pass"


def test_visual_judge_abstains_never_passes():
    claim = criterion_claim(
        "task_synth",
        {
            "id": "criterion 3",
            "description": "Includes a Map of the Study area.",
            "weight": 2,
            "grading_target": "",
        },
    )
    entry = _judge_claim(claim, "Here is a map of the study area.")
    assert entry["verdict"] == "unverified"
    assert entry["reason"] == "judge_abstained"


def test_format_judges():
    asterisk = criterion_claim(
        "task_synth",
        {
            "id": "criterion 5",
            "description": "Contains zero asterisk characters in the response.",
            "weight": 1,
            "grading_target": "",
        },
    )
    assert _judge_claim(asterisk, "plain text")["verdict"] == "pass"
    assert _judge_claim(asterisk, "a * b")["verdict"] == "fail"
    hyphen = criterion_claim(
        "task_synth",
        {
            "id": "criterion 6",
            "description": (
                "Uses a hyphen as the bullet marker on every non-section "
                "list item."
            ),
            "weight": 1,
            "grading_target": "",
        },
    )
    assert _judge_claim(hyphen, "- one\n- two")["verdict"] == "pass"
    assert _judge_claim(hyphen, "- one\n* two")["verdict"] == "fail"


# ------------------------------------------------------------------- runner


def _good_agent(task_text, tools):
    return {
        "result": (
            "Study area: City of Nottingham (B). "
            "The study area covers 7,464.41 ha in total."
        )
    }


def _empty_agent(task_text, tools):
    return {"result": "I could not complete the task."}


def _raising_agent(task_text, tools):
    raise RuntimeError("provider unavailable")


def test_runner_good_agent_scores():
    report = run_mka_task(_good_agent, _synthetic_task(), k=5)
    assert report["criteria"] == 4
    assert report["passed_run1"] == 2
    assert report["failed_run1"] == 0
    assert report["unverified_run1"] == 2
    assert report["pass_rate_verifiable_run1"] == 1.0
    assert report["unverifiable_share_run1"] == 0.5
    assert report["mean_pass_at_1"] == 1.0
    assert report["mean_pass_at_k"] == 1.0
    assert report["verifiable_criteria"] == 2
    assert report["weighted_pass_rate_verifiable_run1"] == 1.0


def test_runner_empty_agent_fails_checkable():
    report = run_mka_task(_empty_agent, _synthetic_task(), k=3)
    assert report["passed_run1"] == 0
    assert report["failed_run1"] == 2
    assert report["unverified_run1"] == 2
    assert report["pass_rate_verifiable_run1"] == 0.0
    assert report["mean_pass_at_1"] == 0.0
    assert report["mean_pass_at_k"] == 0.0


def test_runner_raising_agent_is_agent_error():
    report = run_mka_task(_raising_agent, _synthetic_task(), k=2)
    assert report["runs"][0]["agent_error"] is True
    assert "AGENT-ERROR" in report["runs"][0]["deliverable"]
    assert report["failed_run1"] == 2
    assert report["unverified_run1"] == 2


def test_runner_deterministic_same_seed():
    first = run_mka_task(_good_agent, _synthetic_task(), k=5, seed=0)
    second = run_mka_task(_good_agent, _synthetic_task(), k=5, seed=0)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_runner_k_one():
    report = run_mka_task(_good_agent, _synthetic_task(), k=1)
    assert report["mean_pass_at_k"] == 1.0


def test_runner_rejects_bad_args():
    with pytest.raises(TypeError):
        run_mka_task("not callable", _synthetic_task())
    with pytest.raises(TypeError):
        run_mka_task(_good_agent, _synthetic_task(), k=0)


def test_target_report_aggregates():
    report = run_mka_target(_good_agent, [_synthetic_task()], k=2)
    assert report["task_count"] == 1
    assert report["total_criteria"] == 4
    assert report["verifiable_criteria"] == 2
    assert report["check_level_judgments"] == 8
    assert report["mean_pass_at_k"] == 1.0


# -------------------------------------------------------------- vendored data


def test_vendored_tasks_shape():
    tasks = _load_tasks()
    assert len(tasks) == 10
    assert {t["task_id"] for t in tasks} == KNOWN_TASK_IDS
    total = 0
    for task in tasks:
        assert task["prompt"]
        assert task["criteria"]
        total += len(task["criteria"])
    assert total == 835


def test_vendored_classification_coverage():
    tasks = _load_tasks()
    counts = {"numeric": 0, "entity": 0, "visual": 0, "format": 0, "unparsed": 0}
    for task in tasks:
        for criterion in task["criteria"]:
            counts[classify_criterion(criterion["description"])["kind"]] += 1
    assert counts["numeric"] == 159
    assert counts["entity"] == 165
    assert counts["visual"] == 318
    assert counts["format"] == 2
    assert counts["unparsed"] == 191
    assert sum(counts.values()) == 835


def test_task_contract_claim_count():
    task = _load_tasks()[0]
    contract = task_contract(task)
    assert len(contract["claims"]) == len(task["criteria"])
    assert all(c["kind"] == "judge" for c in contract["claims"])
    assert all(c["field"] == "deliverable" for c in contract["claims"])
