"""Tests for the patch-parsimony receipt.

All deterministic, fixed patch records. Unit counts are pinned
from hand-counted AST walks (an assignment is 3 units, the add
function is 9, the guarded version is 18, the summing loop is
12, the sum call is 5), so a counting-rule change fails loudly
instead of drifting silently. Coverage: counting and complexity
on small snippets, the lines fallback, the diff parser
(single-hunk, multi-hunk, new file, deleted file, mismatch
refusal), scope signals, the outcome rules including the
negative-reference sign cases, the campaign math (pass rate,
median ratio, Spearman), and the validation errors that refuse
bad records instead of scoring them.
"""

import pytest

from trustrun.lean_patch import (
    OUTCOME_FAILED,
    OUTCOME_SOLVED,
    OUTCOME_SOLVED_BLOATED,
    OUTCOME_SOLVED_CORNER_CUT,
    OUTCOME_SOLVED_INCOMPLETE,
    OUTCOME_SOLVED_LEAN,
    VERDICT_READY,
    VERDICT_REVIEW,
    build_lean_patch_report,
    complexity,
    count_units,
    format_summary,
    patch_from_diff,
    score_campaign,
    score_patch,
)

ADD_BEFORE = "def add(a, b):\n    return a + b\n"
GUARD_AFTER = (
    "def add(a, b):\n"
    "    if a is None:\n"
    "        raise ValueError(\"a\")\n"
    "    return a + b\n"
)
LOOP_BEFORE = "total = 0\nfor x in items:\n    total = total + x\n"
SUM_AFTER = "total = sum(items)\n"
TEST_FILE = {
    "tests/test_app.py": {
        "before": "",
        "after": "def test_total():\n    assert total_of([1, 2]) == 3\n",
    }
}
DOCS_FILE = {
    "README.md": {"before": "# App\n", "after": "# App\n\nSums items.\n"}
}


def _patch(files, passed=True, reference=None):
    patch = {"id": "t", "files": files, "passed": passed}
    if reference is not None:
        patch["reference"] = reference
    return patch


def _ref(before, after, path="src/app.py"):
    return {"files": {path: {"before": before, "after": after}}}


# --- counting ------------------------------------------------

def test_count_units_assign_is_three():
    assert count_units("x = 1\n") == (3, "ast")


def test_count_units_add_fn_is_nine():
    assert count_units(ADD_BEFORE) == (9, "ast")


def test_count_units_guard_fn_is_eighteen():
    assert count_units(GUARD_AFTER) == (18, "ast")


def test_count_units_loop_is_twelve_and_sum_is_five():
    assert count_units(LOOP_BEFORE) == (12, "ast")
    assert count_units(SUM_AFTER) == (5, "ast")


def test_count_units_empty_is_zero():
    assert count_units("") == (0, "ast")


def test_count_units_broken_python_falls_back_to_lines():
    assert count_units("def broken(:\n") == (1, "lines")
    assert count_units("def broken(:\n\nx = 1\n") == (2, "lines")


def test_count_units_non_python_counts_lines():
    assert count_units("a\nb\n\n", path="notes.txt") == (2, "lines")


def test_complexity_add_is_one_guard_is_two():
    assert complexity(ADD_BEFORE) == (1, "ast")
    assert complexity(GUARD_AFTER) == (2, "ast")


def test_complexity_loop_is_two_sum_is_one():
    assert complexity(LOOP_BEFORE) == (2, "ast")
    assert complexity(SUM_AFTER) == (1, "ast")


# --- diff parser ---------------------------------------------

def test_patch_from_diff_single_hunk():
    diff = (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,3 +1,3 @@\n"
        " total = 0\n"
        "-for x in items:\n"
        "-    total = total + x\n"
        "+total = sum(items)\n"
    )
    result = patch_from_diff(diff, lambda path: LOOP_BEFORE)
    assert result["files"]["src/app.py"]["before"] == LOOP_BEFORE
    # The hunk keeps the "total = 0" line and replaces the loop
    # with the sum call: 12 units become 8, net -4.
    assert result["files"]["src/app.py"]["after"] == (
        "total = 0\ntotal = sum(items)\n"
    )


def test_patch_from_diff_multi_hunk_keeps_lines_between():
    before = "a = 1\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6\ng = 7\n"
    diff = (
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,2 +1,2 @@\n"
        " a = 1\n"
        "-b = 2\n"
        "+b = 20\n"
        "@@ -6,2 +6,2 @@\n"
        " f = 6\n"
        "-g = 7\n"
        "+g = 70\n"
    )
    result = patch_from_diff(diff, lambda path: before)
    after = result["files"]["x.py"]["after"]
    assert after == "a = 1\nb = 20\nc = 3\nd = 4\ne = 5\nf = 6\ng = 70\n"


def test_patch_from_diff_new_file():
    diff = (
        "--- /dev/null\n"
        "+++ b/src/new.py\n"
        "@@ -0,0 +1,2 @@\n"
        "+x = 1\n"
        "+y = 2\n"
    )
    result = patch_from_diff(diff, lambda path: None)
    files = result["files"]["src/new.py"]
    assert files["before"] is None
    assert files["after"] == "x = 1\ny = 2\n"


def test_patch_from_diff_deleted_file():
    diff = (
        "--- a/src/old.py\n"
        "+++ /dev/null\n"
        "@@ -1,2 +0,0 @@\n"
        "-x = 1\n"
        "-y = 2\n"
    )
    result = patch_from_diff(diff, lambda path: "x = 1\ny = 2\n")
    files = result["files"]["src/old.py"]
    assert files["before"] == "x = 1\ny = 2\n"
    assert files["after"] is None


def test_patch_from_diff_context_mismatch_refuses():
    diff = (
        "--- a/x.py\n"
        "+++ b/x.py\n"
        "@@ -1,2 +1,2 @@\n"
        " a = 1\n"
        "-b = 999\n"
        "+b = 20\n"
    )
    with pytest.raises(ValueError):
        patch_from_diff(diff, lambda path: "a = 1\nb = 2\n")


def test_patch_from_diff_missing_plus_plus_refuses():
    with pytest.raises(ValueError):
        patch_from_diff("--- a/x.py\n", lambda path: "")


def test_patch_from_diff_missing_before_source_refuses():
    diff = "--- a/x.py\n+++ b/x.py\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    with pytest.raises(ValueError):
        patch_from_diff(diff, lambda path: None)


# --- per-patch scoring ---------------------------------------

def test_lean_exact_match_with_tests_and_docs():
    patch = _patch(
        {
            "src/app.py": {"before": LOOP_BEFORE, "after": SUM_AFTER},
            **TEST_FILE,
            **DOCS_FILE,
        },
        reference=_ref(LOOP_BEFORE, SUM_AFTER),
    )
    result = score_patch(patch)
    assert result["outcome"] == OUTCOME_SOLVED_LEAN
    assert result["net_units"] == -7
    assert result["ratio"] == 1.0
    assert result["complexity_delta"] == -1
    assert result["completeness"] == pytest.approx(2.0 / 3.0)


def test_test_files_do_not_count_as_bloat():
    patch = _patch(
        {
            "src/app.py": {"before": LOOP_BEFORE, "after": SUM_AFTER},
            **TEST_FILE,
        },
        reference=_ref(LOOP_BEFORE, SUM_AFTER),
    )
    result = score_patch(patch)
    assert result["net_units"] == -7
    assert result["per_file"]["tests/test_app.py"]["counted"] is False


def test_bloated_helper_against_removing_reference():
    bloated = LOOP_BEFORE + "\ndef total_of(items):\n    return sum(items)\n"
    patch = _patch(
        {"src/app.py": {"before": LOOP_BEFORE, "after": bloated}},
        reference=_ref(LOOP_BEFORE, SUM_AFTER),
    )
    result = score_patch(patch)
    assert result["outcome"] == OUTCOME_SOLVED_BLOATED
    assert result["net_units"] == 7
    assert result["ratio"] == -1.0


def test_bloated_guard_against_small_reference():
    ref_after = (
        "def add(a, b):\n    \"\"\"Add two numbers.\"\"\"\n    return a + b\n"
    )
    patch = _patch(
        {"src/app.py": {"before": ADD_BEFORE, "after": GUARD_AFTER}},
        reference=_ref(ADD_BEFORE, ref_after),
    )
    result = score_patch(patch)
    assert result["outcome"] == OUTCOME_SOLVED_BLOATED
    assert result["net_units"] == 9
    assert result["ratio"] == 4.5


def test_docstring_cost_does_not_bloat_a_removing_fix():
    doc_after = "\"\"\"Sum helper.\"\"\"\n" + SUM_AFTER
    patch = _patch(
        {
            "src/app.py": {"before": LOOP_BEFORE, "after": doc_after},
            **TEST_FILE,
        },
        reference=_ref(LOOP_BEFORE, SUM_AFTER),
    )
    result = score_patch(patch)
    assert result["outcome"] == OUTCOME_SOLVED_LEAN
    assert result["net_units"] == -5
    assert result["ratio"] == pytest.approx(-5.0 / -7.0)


def test_corner_cut_solves_with_no_scope_signals():
    patch = _patch(
        {"src/app.py": {"before": LOOP_BEFORE, "after": SUM_AFTER}},
        reference=_ref(LOOP_BEFORE, SUM_AFTER),
    )
    result = score_patch(patch)
    assert result["outcome"] == OUTCOME_SOLVED_CORNER_CUT
    assert result["completeness"] == 0.0


def test_failed_patch_outcome_is_failed():
    patch = _patch(
        {"src/app.py": {"before": LOOP_BEFORE, "after": SUM_AFTER}},
        passed=False,
        reference=_ref(LOOP_BEFORE, SUM_AFTER),
    )
    assert score_patch(patch)["outcome"] == OUTCOME_FAILED


def test_no_reference_solved_and_incomplete():
    files = {
        "src/app.py": {"before": LOOP_BEFORE, "after": SUM_AFTER},
        **TEST_FILE,
        **DOCS_FILE,
    }
    assert score_patch(_patch(files))["outcome"] == OUTCOME_SOLVED
    thin = {"src/app.py": {"before": LOOP_BEFORE, "after": SUM_AFTER}}
    assert score_patch(_patch(thin))["outcome"] == OUTCOME_SOLVED_INCOMPLETE


def test_reference_net_zero_ratio_undefined():
    patch = _patch(
        {
            "src/app.py": {"before": LOOP_BEFORE, "after": SUM_AFTER},
            **TEST_FILE,
            **DOCS_FILE,
        },
        reference=_ref(LOOP_BEFORE, LOOP_BEFORE),
    )
    result = score_patch(patch)
    assert result["reference_net_units"] == 0
    assert result["ratio"] is None
    assert result["outcome"] == OUTCOME_SOLVED


def test_reference_net_zero_agent_adds_is_bloated():
    patch = _patch(
        {"src/app.py": {"before": ADD_BEFORE, "after": GUARD_AFTER}},
        reference=_ref(ADD_BEFORE, ADD_BEFORE),
    )
    result = score_patch(patch)
    assert result["outcome"] == OUTCOME_SOLVED_BLOATED
    assert result["ratio"] is None


def test_agent_removes_more_than_reference_is_lean():
    guard_before = GUARD_AFTER
    ref_after = ADD_BEFORE
    agent_after = "def add(a, b):\n    return 0\n"
    patch = _patch(
        {
            "src/app.py": {"before": guard_before, "after": agent_after},
            **TEST_FILE,
            **DOCS_FILE,
        },
        reference=_ref(guard_before, ref_after),
    )
    result = score_patch(patch)
    assert result["outcome"] == OUTCOME_SOLVED_LEAN
    assert result["net_units"] == -12
    assert result["ratio"] == pytest.approx(-12.0 / -9.0)


def test_error_handling_signal_from_added_try():
    after = (
        "def add(a, b):\n"
        "    try:\n"
        "        return a + b\n"
        "    except TypeError:\n"
        "        return 0\n"
    )
    patch = _patch(
        {
            "src/app.py": {"before": ADD_BEFORE, "after": after},
            **TEST_FILE,
        },
        reference=_ref(ADD_BEFORE, after),
    )
    result = score_patch(patch)
    assert result["scope"]["error_handling"] is True
    assert result["scope"]["tests"] is True
    assert result["net_units"] == 5
    assert result["complexity_delta"] == 1
    assert result["outcome"] == OUTCOME_SOLVED_LEAN


def test_added_test_function_counts_as_tests_signal():
    after = ADD_BEFORE + (
        "\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    patch = _patch(
        {"src/app.py": {"before": ADD_BEFORE, "after": after}},
        reference=_ref(ADD_BEFORE, after),
    )
    result = score_patch(patch)
    assert result["scope"]["tests"] is True
    assert result["outcome"] == OUTCOME_SOLVED_CORNER_CUT


def test_empty_patch_is_incomplete_not_lean():
    result = score_patch(_patch({}))
    assert result["net_units"] == 0
    assert result["outcome"] == OUTCOME_SOLVED_INCOMPLETE


def test_validation_refuses_bad_records():
    with pytest.raises(TypeError):
        score_patch("not a dict")
    with pytest.raises(TypeError):
        score_patch({"id": "x", "passed": True})
    with pytest.raises(TypeError):
        score_patch({"id": "x", "files": {}, "passed": "yes"})
    with pytest.raises(TypeError):
        score_patch(_patch({}), reference="not a dict")
    with pytest.raises(TypeError):
        score_campaign("not a list")


# --- campaign ------------------------------------------------

def test_campaign_ready_when_all_lean():
    patches = [
        _patch(
            {
                "src/app.py": {"before": LOOP_BEFORE, "after": SUM_AFTER},
                **TEST_FILE,
                **DOCS_FILE,
            },
            reference=_ref(LOOP_BEFORE, SUM_AFTER),
        ),
        _patch(
            {
                "src/app.py": {"before": LOOP_BEFORE, "after": SUM_AFTER},
                **TEST_FILE,
                **DOCS_FILE,
            },
            reference=_ref(LOOP_BEFORE, SUM_AFTER),
        ),
    ]
    campaign = score_campaign(patches)
    assert campaign["verdict"] == VERDICT_READY
    assert campaign["pass_rate"] == 1.0
    assert campaign["median_ratio"] == 1.0
    assert campaign["median_complexity_delta"] == -1.0
    assert campaign["outcomes"] == {OUTCOME_SOLVED_LEAN: 2}


def test_campaign_review_when_a_patch_is_bloated():
    bloated = LOOP_BEFORE + "\ndef total_of(items):\n    return sum(items)\n"
    patches = [
        _patch(
            {"src/app.py": {"before": LOOP_BEFORE, "after": bloated}},
            reference=_ref(LOOP_BEFORE, SUM_AFTER),
        ),
    ]
    campaign = score_campaign(patches)
    assert campaign["verdict"] == VERDICT_REVIEW
    assert campaign["spearman_size_solved"] is None


def test_campaign_spearman_positive_when_size_solves():
    patches = [
        _patch(
            {"src/app.py": {"before": "x = 1\n", "after": "x = 1\n"}},
            passed=False,
        ),
        _patch(
            {"src/app.py": {"before": "x = 1\n", "after": "x = 1\ny = 2\n"}},
            passed=False,
        ),
        _patch(
            {"src/app.py": {"before": "x = 1\n", "after": "x = 1\ny = 2\nz = 3\n"}},
            passed=True,
        ),
        _patch(
            {
                "src/app.py": {
                    "before": "x = 1\n",
                    "after": "x = 1\ny = 2\nz = 3\nw = 4\n",
                }
            },
            passed=True,
        ),
    ]
    campaign = score_campaign(patches)
    assert campaign["pass_rate"] == 0.5
    assert campaign["spearman_size_solved"] == pytest.approx(
        0.8944271909999159
    )


def test_campaign_empty_is_review():
    campaign = score_campaign([])
    assert campaign["verdict"] == VERDICT_REVIEW
    assert campaign["pass_rate"] is None


def test_report_and_summary():
    patches = [
        _patch(
            {
                "src/app.py": {"before": LOOP_BEFORE, "after": SUM_AFTER},
                **TEST_FILE,
                **DOCS_FILE,
            },
            reference=_ref(LOOP_BEFORE, SUM_AFTER),
        ),
    ]
    report = build_lean_patch_report("demo-agent", patches)
    assert report["agent"] == "demo-agent"
    assert report["verdict"] == VERDICT_READY
    summary = format_summary(report)
    assert "demo-agent" in summary
    assert "READY" in summary
    assert "solved_lean 1" in summary
    assert format_summary(build_lean_patch_report("x", [])) == (
        "Lean-patch receipt for x: no patches scored."
    )
