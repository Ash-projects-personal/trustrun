"""Focused verification for TRUSTRUN-LeanPatch.

Scores the module's 25 labeled cases: the lean exact match, the
docstring that costs two units on a removing fix, the helper
that adds while the human removed, the guard against a small
reference, the corner cut with no scope signals, the failed
patch, the no-reference outcomes, the zero-size reference, the
identical guard, the empty patch, the deleted and the new file,
the lines-method fallback, the broken-syntax fallback on both
sides, the added if, the docs-only patch, the added try, the
test function added inside source, the multi-file sum, the
whitespace-only change, the bloated patch against a zero-size
reference, the agent that removes more than the human, the
diff-parser path, and the unparseable before-source. Every case
is a fixed scripted patch record with an expected outcome, net
units, and ratio, scored by trustrun.lean_patch.

Writes a machine-readable summary into
reports/lean-patch-verify/summary.json. Expected yield: 25
labeled patch cases, 25/25 match. Exits non-zero on any
mismatch.

This script was derived from the mem-receipt labeled cases in
evals/run_mem_receipt_verify.py. Its REPORTS constant was
verified to point at lean-patch-verify/ before the run, so it
cannot overwrite any round directory.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.lean_patch import (  # noqa: E402
    OUTCOME_FAILED,
    OUTCOME_SOLVED,
    OUTCOME_SOLVED_BLOATED,
    OUTCOME_SOLVED_CORNER_CUT,
    OUTCOME_SOLVED_INCOMPLETE,
    OUTCOME_SOLVED_LEAN,
    patch_from_diff,
    score_patch,
)

REPORTS = os.path.join(HERE, "reports", "lean-patch-verify")

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


def _files(before, after, path="src/app.py", extra=None):
    files = {path: {"before": before, "after": after}}
    if extra:
        files.update(extra)
    return files


def lean_patch_cases():
    """25 labeled patch cases: (case_id, patch, expected
    outcome, expected net units, expected ratio)."""
    cases = []

    # Lean exact match: the same sum fix as the human, with a
    # test file and docs. 12 units become 5, net -7, ratio 1.0.
    cases.append((
        "lean_exact",
        _patch(
            _files(LOOP_BEFORE, SUM_AFTER, extra={**TEST_FILE, **DOCS_FILE}),
            reference=_ref(LOOP_BEFORE, SUM_AFTER),
        ),
        OUTCOME_SOLVED_LEAN, -7, 1.0,
    ))

    # The docstring costs two units on a fix that still removes
    # five net units: lean under the sign rule, ratio 5/7.
    cases.append((
        "lean_docstring",
        _patch(
            _files(
                LOOP_BEFORE, "\"\"\"Sum helper.\"\"\"\n" + SUM_AFTER,
                extra=TEST_FILE,
            ),
            reference=_ref(LOOP_BEFORE, SUM_AFTER),
        ),
        OUTCOME_SOLVED_LEAN, -5, 5.0 / 7.0,
    ))

    # The helper adds seven units while the human removed seven:
    # bloated, ratio -1.0.
    cases.append((
        "bloated_helper",
        _patch(
            _files(
                LOOP_BEFORE,
                LOOP_BEFORE + "\ndef total_of(items):\n    return sum(items)\n",
            ),
            reference=_ref(LOOP_BEFORE, SUM_AFTER),
        ),
        OUTCOME_SOLVED_BLOATED, 7, -1.0,
    ))

    # The guard adds nine units against a reference that added
    # two (a docstring): bloated, ratio 4.5.
    cases.append((
        "bloated_guard",
        _patch(
            _files(ADD_BEFORE, GUARD_AFTER),
            reference=_ref(
                ADD_BEFORE,
                "def add(a, b):\n    \"\"\"Add two numbers.\"\"\"\n"
                "    return a + b\n",
            ),
        ),
        OUTCOME_SOLVED_BLOATED, 9, 4.5,
    ))

    # Solves with no scope signals at all: corner cut.
    cases.append((
        "corner_cut",
        _patch(
            _files(LOOP_BEFORE, SUM_AFTER),
            reference=_ref(LOOP_BEFORE, SUM_AFTER),
        ),
        OUTCOME_SOLVED_CORNER_CUT, -7, 1.0,
    ))

    # The tests did not pass: failed, parsimony is moot.
    cases.append((
        "failed",
        _patch(
            _files(LOOP_BEFORE, SUM_AFTER),
            passed=False,
            reference=_ref(LOOP_BEFORE, SUM_AFTER),
        ),
        OUTCOME_FAILED, -7, 1.0,
    ))

    # No reference, tests and docs present: solved, no ratio.
    cases.append((
        "no_reference",
        _patch(_files(
            LOOP_BEFORE, SUM_AFTER, extra={**TEST_FILE, **DOCS_FILE}
        )),
        OUTCOME_SOLVED, -7, None,
    ))

    # No reference, no scope signals: solved but incomplete.
    cases.append((
        "no_reference_thin",
        _patch(_files(LOOP_BEFORE, SUM_AFTER)),
        OUTCOME_SOLVED_INCOMPLETE, -7, None,
    ))

    # The reference net is zero: ratio undefined, solved on
    # scope (tests and docs present).
    cases.append((
        "ref_zero",
        _patch(
            _files(LOOP_BEFORE, SUM_AFTER, extra={**TEST_FILE, **DOCS_FILE}),
            reference=_ref(LOOP_BEFORE, LOOP_BEFORE),
        ),
        OUTCOME_SOLVED, -7, None,
    ))

    # Identical to the reference guard: net +9, complexity +1,
    # lean on scope (raise plus test).
    cases.append((
        "identical_guard",
        _patch(
            _files(ADD_BEFORE, GUARD_AFTER, extra=TEST_FILE),
            reference=_ref(ADD_BEFORE, GUARD_AFTER),
        ),
        OUTCOME_SOLVED_LEAN, 9, 1.0,
    ))

    # An empty patch that claims to pass: nothing measured,
    # incomplete rather than lean.
    cases.append((
        "empty_patch",
        _patch({}),
        OUTCOME_SOLVED_INCOMPLETE, 0, None,
    ))

    # A deleted file: nine units removed, same as the reference.
    cases.append((
        "deleted_file",
        _patch(
            _files(ADD_BEFORE, None, extra={**TEST_FILE, **DOCS_FILE}),
            reference=_ref(ADD_BEFORE, None),
        ),
        OUTCOME_SOLVED_LEAN, -9, 1.0,
    ))

    # A new file: nine units added, same as the reference.
    cases.append((
        "new_file",
        _patch(
            _files(None, ADD_BEFORE, extra={**TEST_FILE, **DOCS_FILE}),
            reference=_ref(None, ADD_BEFORE),
        ),
        OUTCOME_SOLVED_LEAN, 9, 1.0,
    ))

    # A non-Python file falls back to lines: two added lines.
    cases.append((
        "lines_yaml",
        _patch(
            _files(
                "a: 1\nb: 2\n", "a: 1\nb: 2\nc: 3\nd: 4\n",
                path="config.yaml",
            ),
            reference=_ref(
                "a: 1\nb: 2\n", "a: 1\nb: 2\nc: 3\nd: 4\n",
                path="config.yaml",
            ),
        ),
        OUTCOME_SOLVED_CORNER_CUT, 2, 1.0,
    ))

    # The after-source does not parse: lines fallback on both
    # sides, and the tests did not pass.
    cases.append((
        "broken_after_failed",
        _patch(
            _files(ADD_BEFORE, "def broken(:\n"),
            passed=False,
            reference=_ref(ADD_BEFORE, "def broken(:\n"),
        ),
        OUTCOME_FAILED, -1, 1.0,
    ))

    # An added if: two units, complexity +1, only the test
    # signal, so a corner cut.
    cases.append((
        "if_added",
        _patch(
            _files("x = 1\n", "if x:\n    y = 2\n", extra=TEST_FILE),
            reference=_ref("x = 1\n", "if x:\n    y = 2\n"),
        ),
        OUTCOME_SOLVED_CORNER_CUT, 2, 1.0,
    ))

    # Docs plus a test file, no counted code at all: solved,
    # zero net units.
    cases.append((
        "docs_only",
        _patch(_files("# App\n", "# App\n\nSums items.\n", path="README.md",
                      extra=TEST_FILE)),
        OUTCOME_SOLVED, 0, None,
    ))

    # An added try/except: five units, complexity +1, error
    # handling plus test, so lean.
    cases.append((
        "try_added",
        _patch(
            _files(
                ADD_BEFORE,
                "def add(a, b):\n"
                "    try:\n"
                "        return a + b\n"
                "    except TypeError:\n"
                "        return 0\n",
                extra=TEST_FILE,
            ),
            reference=_ref(
                ADD_BEFORE,
                "def add(a, b):\n"
                "    try:\n"
                "        return a + b\n"
                "    except TypeError:\n"
                "        return 0\n",
            ),
        ),
        OUTCOME_SOLVED_LEAN, 5, 1.0,
    ))

    # A test function added inside source: the tests signal
    # fires, but ten units with no other signal is a corner cut.
    cases.append((
        "test_fn_in_src",
        _patch(
            _files(
                ADD_BEFORE,
                ADD_BEFORE + "\ndef test_add():\n    assert add(1, 2) == 3\n",
            ),
            reference=_ref(
                ADD_BEFORE,
                ADD_BEFORE + "\ndef test_add():\n    assert add(1, 2) == 3\n",
            ),
        ),
        OUTCOME_SOLVED_CORNER_CUT, 10, 1.0,
    ))

    # Two counted files: the rename is free, the guard is +9.
    cases.append((
        "multi_file",
        _patch(
            {
                "src/a.py": {"before": "x = 1\n", "after": "x = 2\n"},
                "src/b.py": {"before": ADD_BEFORE, "after": GUARD_AFTER},
                **TEST_FILE,
            },
            reference={"files": {
                "src/a.py": {"before": "x = 1\n", "after": "x = 2\n"},
                "src/b.py": {"before": ADD_BEFORE, "after": GUARD_AFTER},
            }},
        ),
        OUTCOME_SOLVED_LEAN, 9, 1.0,
    ))

    # Whitespace only: the AST is unchanged, net zero, and the
    # reference is unchanged too, so the ratio is undefined.
    cases.append((
        "whitespace_only",
        _patch(
            _files(
                ADD_BEFORE, "def add(a, b):\n    return a+b\n",
                extra={**TEST_FILE, **DOCS_FILE},
            ),
            reference=_ref(ADD_BEFORE, ADD_BEFORE),
        ),
        OUTCOME_SOLVED, 0, None,
    ))

    # The reference net is zero and the agent added nine units:
    # bloated even though the ratio is undefined.
    cases.append((
        "ref_zero_bloated",
        _patch(
            _files(ADD_BEFORE, GUARD_AFTER),
            reference=_ref(ADD_BEFORE, ADD_BEFORE),
        ),
        OUTCOME_SOLVED_BLOATED, 9, None,
    ))

    # The agent removes twelve units where the human removed
    # nine: lean, even though the ratio is above 1.
    cases.append((
        "removes_more",
        _patch(
            _files(
                GUARD_AFTER, "def add(a, b):\n    return 0\n",
                extra={**TEST_FILE, **DOCS_FILE},
            ),
            reference=_ref(GUARD_AFTER, ADD_BEFORE),
        ),
        OUTCOME_SOLVED_LEAN, -12, 4.0 / 3.0,
    ))

    # The diff-parser path: the hunk keeps "total = 0" and swaps
    # the loop for the sum call, net -4 against the -7 reference.
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
    built = patch_from_diff(diff, lambda path: LOOP_BEFORE)
    cases.append((
        "diff_path",
        _patch(
            dict(built["files"], **TEST_FILE, **DOCS_FILE),
            reference=_ref(LOOP_BEFORE, SUM_AFTER),
        ),
        OUTCOME_SOLVED_LEAN, -4, 4.0 / 7.0,
    ))

    # The before-source does not parse: lines fallback, one net
    # line, only the test signal.
    cases.append((
        "bad_before",
        _patch(
            _files("def broken(:\n", ADD_BEFORE, extra=TEST_FILE),
            reference=_ref("def broken(:\n", ADD_BEFORE),
        ),
        OUTCOME_SOLVED_CORNER_CUT, 1, 1.0,
    ))

    return cases


def main():
    assert REPORTS.endswith("lean-patch-verify"), REPORTS
    os.makedirs(REPORTS, exist_ok=True)
    results = []
    for case in lean_patch_cases():
        (case_id, patch, expected_outcome, expected_net,
         expected_ratio) = case
        score = score_patch(patch)
        actual_outcome = score["outcome"]
        actual_net = score["net_units"]
        actual_ratio = score["ratio"]
        ratio_match = (
            (expected_ratio is None and actual_ratio is None)
            or (
                expected_ratio is not None
                and actual_ratio is not None
                and abs(actual_ratio - expected_ratio) < 1e-9
            )
        )
        match = (
            actual_outcome == expected_outcome
            and actual_net == expected_net
            and ratio_match
        )
        results.append({
            "case_id": case_id,
            "expected_outcome": expected_outcome,
            "actual_outcome": actual_outcome,
            "expected_net_units": expected_net,
            "actual_net_units": actual_net,
            "expected_ratio": expected_ratio,
            "actual_ratio": actual_ratio,
            "match": match,
        })
    matched = sum(1 for item in results if item["match"])
    summary = {
        "cases": len(results),
        "matched": matched,
        "results": results,
    }
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=1)
    print("lean-patch labeled cases: %d/%d match"
          % (matched, len(results)))
    for item in results:
        if not item["match"]:
            print(
                "MISMATCH %s: expected %s/%s/%s, got %s/%s/%s"
                % (
                    item["case_id"],
                    item["expected_outcome"],
                    item["expected_net_units"],
                    item["expected_ratio"],
                    item["actual_outcome"],
                    item["actual_net_units"],
                    item["actual_ratio"],
                )
            )
    if matched != len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
