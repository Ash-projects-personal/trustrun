"""Regression tests for the cell-diffs position-keyed comparison.

Audit-64 fold (2026-11-12): `position_keyed_cells` in the real-agent
cell_diffs.py scripts returned the 3-field outcome tuple
(survived, detected, completed) as the cell value, while kind/vector
lived only in the cell NAME. `_diff_position_keyed` compares VALUES
only, so two audits placing different vectors at the same battery
position with identical outcomes counted as a match. The mastra
script printed BabyAGI 69 where the full-tuple count is 73 (the 4
missed cells are t4_multistep and t23_station_add, attacks #11/#12
clarification_injection: mastra records vectors
solicited_reply/piggyback_reply, babyagi records None, outcome
triples identical). Same bug in the other five scripts carrying
`position_keyed_cells` (browser-use, gptengineer, gptresearcher,
magentic_one, storm); openinterpreter and sweagent have no
position-keyed comparison (name-keyed only, where the key already
carries kind/vector) and are unaffected.

The fix: the position-keyed cell value is the FULL tuple
(kind, vector, survived, detected, completed), as the module
docstrings already define each attack cell. These tests pin that
behavior on all six scripts, so a future copy-paste of the method
cannot silently reintroduce the under-count.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evals"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "evals",
                                "real_agents"))

from real_agents.browseruse import cell_diffs as browseruse_diffs  # noqa: E402
from real_agents.gptengineer import cell_diffs as gptengineer_diffs  # noqa: E402
from real_agents.gptresearcher import cell_diffs as gptresearcher_diffs  # noqa: E402
from real_agents.magentic_one import cell_diffs as magentic_one_diffs  # noqa: E402
from real_agents.mastra import cell_diffs as mastra_diffs  # noqa: E402
from real_agents.storm import cell_diffs as storm_diffs  # noqa: E402

_MODULES = (
    browseruse_diffs,
    gptengineer_diffs,
    gptresearcher_diffs,
    magentic_one_diffs,
    mastra_diffs,
    storm_diffs,
)


def _row(vector, survived=True, detected=False, completed=True):
    return {
        "task": "t4_multistep",
        "verdict": "BLOCK",
        "contract": "BLOCK",
        "stress": "BLOCK",
        "consistency": "REVIEW",
        "data": "READY",
        "pass_rate_k": 0.8,
        "attacks": [
            {"kind": "clarification_injection", "vector": vector,
             "survived": survived, "detected": detected,
             "completed": completed},
        ],
    }


def test_position_keyed_value_is_full_tuple():
    """The position-keyed attack value carries kind and vector."""
    for mod in _MODULES:
        cells = dict(mod.position_keyed_cells(_row("solicited_reply")))
        assert cells["attack[0] clarification_injection/solicited_reply"] == (
            "clarification_injection", "solicited_reply", True, False, True), mod


def test_vector_only_difference_counts_as_diff():
    """Two rows differing ONLY in attack vector must count as a diff.

    This is the audit-64 bug: identical outcome triples, different
    vectors (mastra solicited_reply vs babyagi None) at the same
    battery position.
    """
    for mod in _MODULES:
        total, diffs = mod._diff_position_keyed(
            {"t4_multistep": _row("solicited_reply")},
            {"t4_multistep": _row(None)})
        assert total == 1, (mod, total, diffs)
        assert diffs["attack"][0][1] == (
            "attack[0] clarification_injection/solicited_reply"), mod


def test_identical_rows_count_zero():
    for mod in _MODULES:
        total, _ = mod._diff_position_keyed(
            {"t4_multistep": _row("solicited_reply")},
            {"t4_multistep": _row("solicited_reply")})
        assert total == 0, mod


def test_outcome_difference_still_counts():
    for mod in _MODULES:
        total, _ = mod._diff_position_keyed(
            {"t4_multistep": _row("solicited_reply", survived=True)},
            {"t4_multistep": _row("solicited_reply", survived=False)})
        assert total == 1, mod


def _battery_row(extra_visibility=False):
    """A 13-attack row; optionally a 14-attack row with
    tool_failure_visibility inserted at battery position 2."""
    attacks = [
        {"kind": "perturbation", "vector": "typo",
         "survived": True, "detected": False, "completed": True},
        {"kind": "tool_failure", "vector": "search_down",
         "survived": True, "detected": True, "completed": True},
    ]
    if extra_visibility:
        attacks.append({"kind": "tool_failure_visibility",
                        "vector": "search_down",
                        "survived": True, "detected": True,
                        "completed": True})
    attacks += [
        {"kind": "injection", "vector": "plaintext",
         "survived": True, "detected": False, "completed": True},
    ]
    return {
        "task": "t1_test",
        "verdict": "BLOCK",
        "contract": "READY",
        "stress": "BLOCK",
        "consistency": "REVIEW",
        "data": "READY",
        "pass_rate_k": 0.8,
        "attacks": attacks,
    }


def test_tool_failure_visibility_trim_keeps_batteries_comparable():
    """Round-97 fix: a 14-attack row and the same 13-attack row must
    count ZERO diffs on both alignments once the dropped attack is
    trimmed -- otherwise the position-keyed alignment shifts every
    attack after position 1 and the count is a misalignment
    artifact (gptengineer printed 252/475 vs Swarm before the trim;
    the comparable unit is 0/475, per the audit-64 fold)."""
    for mod in (gptengineer_diffs, mastra_diffs):
        row14 = _battery_row(extra_visibility=True)
        row13 = _battery_row(extra_visibility=False)
        trimmed = mod._trimmed(row14)
        assert len(trimmed["attacks"]) == 3, mod  # fixture: 4 - 1 dropped
        assert all(a["kind"] != "tool_failure_visibility"
                   for a in trimmed["attacks"]), mod
        rows14 = {"t1_test": trimmed}
        rows13 = {"t1_test": row13}
        total, _ = mod._diff_position_keyed(rows14, rows13)
        assert total == 0, (mod, total)
        total, _ = mod._diff_name_keyed(rows14, rows13)
        assert total == 0, (mod, total)
        # Without the trim the same pair misaligns: the extra
        # attack shifts positions, so the raw count must be > 0.
        total, _ = mod._diff_position_keyed(
            {"t1_test": row14}, {"t1_test": row13})
        assert total > 0, (mod, total)
