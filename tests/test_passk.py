"""Tests for the tau-bench style pass_at_k estimator."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trustrun.consistency import pass_at_k  # noqa: E402


def test_all_pass():
    assert pass_at_k([True, True, True, True, True], 1) == 1.0
    assert pass_at_k([True, True, True, True, True], 5) == 1.0


def test_none_pass():
    assert pass_at_k([False, False, False, False, False], 1) == 0.0
    assert pass_at_k([False, False, False, False, False], 4) == 0.0


def test_one_of_five_pass_at_1_is_a_fifth():
    assert abs(pass_at_k([True, False, False, False, False], 1) - 0.2) < 1e-9


def test_one_of_five_pass_at_5_is_one():
    assert pass_at_k([True, False, False, False, False], 5) == 1.0


def test_two_of_five_pass_at_2():
    # 1 - C(3, 2) / C(5, 2) = 1 - 3/10 = 0.7
    assert pass_at_k([True, True, False, False, False], 2) == 0.7


def test_unverified_runs_excluded():
    assert pass_at_k([True, "unverified", False, False, False], 1) == 0.25


def test_fewer_judged_than_k_is_unverified():
    assert pass_at_k([True, False], 5) == "unverified"
    assert pass_at_k([], 1) == "unverified"


def test_bad_k_raises():
    for bad in (0, -1, True, "4", 2.5):
        try:
            pass_at_k([True], bad)
        except TypeError:
            continue
        raise AssertionError("expected TypeError for k=%r" % (bad,))


def test_bad_outcomes_type_raises():
    try:
        pass_at_k("not a list", 1)
    except TypeError:
        return
    raise AssertionError("expected TypeError for a non-list outcomes argument")
