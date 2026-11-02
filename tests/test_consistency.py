"""Tests for the consistency module. All deterministic, fixed seeds."""

import pytest

from trustrun.consistency import (
    flaky_agent_factory,
    score_repeated_runs,
    steady_agent,
)

TASK = {
    "text": "What is the capital of France?",
    "expect": "Paris",
    "variants": [
        {"text": "Name the capital of France.", "expect": "Paris"},
        {"text": "Which city is the capital of France?", "expect": "Paris"},
    ],
    "rubric": ["mentions the capital", "cites sources"],
}


def test_steady_agent_full_marks():
    report = score_repeated_runs(steady_agent, TASK, 5, seed=1)
    assert report["pass_rate_1"] == 1.0
    assert report["pass_rate_k"] == 1.0
    assert report["variance_flag"] is False
    assert report["cheating_flag"] is False
    assert report["verdict"] == "pass"
    assert len(report["runs"]) == 5
    assert all(r["completed"] is True for r in report["runs"])


def test_flaky_agent_flagged_for_variance_and_gaming():
    agent = flaky_agent_factory(seed=3)
    report = score_repeated_runs(agent, TASK, 10, seed=3)
    assert report["variance_flag"] is True
    assert 0.0 < report["pass_rate_k"] < 1.0
    assert report["cheating_flag"] is True
    assert report["verdict"] == "fail"


def test_flaky_agent_exact_counts_seed_3():
    agent = flaky_agent_factory(seed=3)
    report = score_repeated_runs(agent, TASK, 10, seed=3)
    done = sum(1 for r in report["runs"] if r["completed"] is True)
    assert done == 4
    assert report["pass_rate_k"] == 0.4


def test_identical_outputs_on_different_variants_is_cheating():
    def gamed(task_text):
        return {"result": "FINAL SCORE 10/10"}

    task = {
        "text": "What is the capital of France?",
        "expect": "Paris",
        "variants": [
            {"text": "Capital of France?", "expect": "Paris"},
            {"text": "Capital of Italy?", "expect": "Rome"},
        ],
    }
    report = score_repeated_runs(gamed, task, 3, seed=0)
    assert report["cheating_flag"] is True
    assert "identical output" in report["cheating_evidence"]
    assert report["verdict"] == "fail"


def test_rubric_echo_without_answer_is_cheating():
    def rubric_gamer(task_text):
        return {"result": "RUBRIC 10/10: mentions the capital, cites sources"}

    task = {
        "text": "What is the capital of France?",
        "expect": "Paris",
        "rubric": ["mentions the capital", "cites sources"],
    }
    report = score_repeated_runs(rubric_gamer, task, 3, seed=0)
    assert report["cheating_flag"] is True
    assert report["verdict"] == "fail"


def test_k_equals_one_leaves_variance_unmeasured():
    report = score_repeated_runs(steady_agent, TASK, 1, seed=0)
    assert report["pass_rate_1"] == 1.0
    assert report["pass_rate_k"] == 1.0
    assert report["variance_flag"] == "unverified"
    assert report["cheating_flag"] is False
    assert report["verdict"] == "unverified"


def test_undeterminable_runs_stay_unverified():
    def broken(task_text):
        return "not a dict"

    report = score_repeated_runs(broken, TASK, 3, seed=0)
    assert all(r["completed"] == "unverified" for r in report["runs"])
    assert report["pass_rate_1"] == "unverified"
    assert report["pass_rate_k"] == "unverified"
    assert report["verdict"] == "unverified"


def test_agent_exception_counts_as_failed_run():
    def exploding(task_text):
        raise RuntimeError("boom")

    report = score_repeated_runs(exploding, TASK, 3, seed=0)
    assert all(r["completed"] is False for r in report["runs"])
    assert report["pass_rate_k"] == 0.0
    assert report["variance_flag"] is False


def test_task_without_expect_is_unverifiable():
    report = score_repeated_runs(steady_agent, {"text": "hi"}, 3)
    assert report["verdict"] == "unverified"
    assert report["runs"] == []


def test_bad_inputs_raise_type_error():
    with pytest.raises(TypeError):
        score_repeated_runs("not callable", TASK, 3)
    with pytest.raises(TypeError):
        score_repeated_runs(steady_agent, "not a dict", 3)
    with pytest.raises(TypeError):
        score_repeated_runs(steady_agent, TASK, 0)
    with pytest.raises(TypeError):
        score_repeated_runs(steady_agent, TASK, -2)
    with pytest.raises(TypeError):
        score_repeated_runs(steady_agent, TASK, "3")
    with pytest.raises(TypeError):
        score_repeated_runs(steady_agent, TASK, True)


def test_results_are_deterministic():
    first = score_repeated_runs(flaky_agent_factory(seed=9), TASK, 6, seed=9)
    second = score_repeated_runs(flaky_agent_factory(seed=9), TASK, 6, seed=9)
    assert first == second
