"""Cell-diffs for audit 91 (Skyvern), slice t5-t9 only, vs audit 87
(Claude Code CLI) and audit 88 (GPT-Pilot).

Method: same as cell_diffs_t1_t4.py (the audit-90 Stagehand
full-tuple method). One cell per stress attack per task row: the
FULL tuple (kind, vector, survived, detected, completed) plus
visibility_class when present, keyed by (kind, vector) and compared
on the UNION of cell keys (a cell present on one side only counts as
a diff). The 6 fixed cells (verdict + contract/stress/consistency/
data + pass_rate_k) are checked separately and reported as a count,
not folded into the attack-cell denominator.

Battery alignment: audits 87/88 ran 19 attacks; this audit runs 20
(terminal_gap is the 20th, new since 87/88). terminal_gap is
DROPPED from the Skyvern side before comparison, so the denominator
is 19 attacks x 5 tasks = 95 cells for both priors. A crash row
carries attacks=[] and counts its missing positions as diffs.

Prior rows: audits 87/88 have no t5-t9-only slice file; their
cumulative summary-slice-t1_factual-t9_olympics.json is read and
filtered to the slice tasks.

Usage: ~/workspace/hackathons/trustrun/trustrun-venvs/skyvern-venv/bin/python3 \\
    evals/reports/real_agents/skyvern/cell_diffs_t5_t9.py > \\
    evals/reports/real_agents/skyvern/cell_diffs_t5_t9.txt
"""

import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
PRIORS = [
    (87, "claude-code-cli", "Claude Code CLI"),
    (88, "gpt-pilot", "GPT-Pilot"),
]
SLICE_TASKS = ["t5_simple_math", "t6_lowconf", "t7_toolmath",
               "t8_imperative", "t9_olympics"]
_DROPPED_KINDS = {"terminal_gap"}


def _attack_tuple(attack):
    out = (attack.get("kind"), attack.get("vector"),
           attack.get("survived"), attack.get("detected"),
           attack.get("completed"))
    if attack.get("visibility_class"):
        out = out + (attack.get("visibility_class"),)
    return out


def _attack_cells(row):
    """{(kind, vector): full tuple} for one row, terminal_gap dropped."""
    cells = {}
    for a in row.get("attacks", []):
        if a.get("kind") in _DROPPED_KINDS:
            continue
        cells[(a.get("kind"), a.get("vector"))] = _attack_tuple(a)
    return cells


def _fixed_cells(row):
    return {
        "verdict": row.get("verdict"),
        "contract": row.get("contract"),
        "stress": row.get("stress"),
        "consistency": row.get("consistency"),
        "data": row.get("data"),
        "pass_rate_k": row.get("pass_rate_k"),
    }


def _diff_cells(my_rows, pr_rows):
    diffs = {}
    total = 0
    for task in sorted(my_rows):
        my_cells = _attack_cells(my_rows[task])
        pr_cells = _attack_cells(pr_rows[task])
        for key in sorted(set(my_cells) | set(pr_cells),
                          key=lambda k: (str(k[0]), str(k[1]))):
            value = my_cells.get(key)
            pvalue = pr_cells.get(key)
            if value != pvalue:
                total += 1
                diffs.setdefault(key[0], []).append(
                    (task, key, value, pvalue))
    return total, diffs


def main():
    with open(os.path.join(
            BASE, "summary-slice-t5_simple_math-t9_olympics.json")) as h:
        mine = json.load(h)
    my_rows_all = {r["task"]: r for r in mine["rows"]}
    assert sorted(my_rows_all) == sorted(SLICE_TASKS), sorted(my_rows_all)
    for num, slug, name in PRIORS:
        with open(os.path.join(
                BASE, "..", slug,
                "summary-slice-t1_factual-t9_olympics.json")) as h:
            prior = json.load(h)
        pr_rows_all = {r["task"]: r for r in prior["rows"]
                       if r["task"] in SLICE_TASKS}
        assert sorted(pr_rows_all) == sorted(SLICE_TASKS), sorted(pr_rows_all)
        my_rows = {t: my_rows_all[t] for t in SLICE_TASKS}
        pr_rows = {t: pr_rows_all[t] for t in SLICE_TASKS}
        total_cells = 19 * len(SLICE_TASKS)
        n_total, n_diffs = _diff_cells(my_rows, pr_rows)
        print("audit 91 skyvern (slice t5-t9) vs audit %d %s (%s): "
              "%d / %d attack cells differ (full-tuple, name-keyed "
              "union; terminal_gap dropped, 87/88 ran 19 attacks)"
              % (num, name, slug, n_total, total_cells))
        for kind in sorted(n_diffs):
            items = n_diffs[kind]
            print("  %s: %d -- tasks %s" % (
                kind, len(items),
                sorted({t for t, _, _, _ in items})))
            for task, key, value, pvalue in items[:12]:
                print("    %s %s: skyvern=%r vs %s=%r" % (
                    task, key, value, slug, pvalue))
            if len(items) > 12:
                print("    ... (%d more)" % (len(items) - 12))
        fixed_diffs = 0
        for task in SLICE_TASKS:
            my_fixed = _fixed_cells(my_rows[task])
            pr_fixed = _fixed_cells(pr_rows[task])
            for cell in sorted(set(my_fixed) | set(pr_fixed)):
                if my_fixed.get(cell) != pr_fixed.get(cell):
                    fixed_diffs += 1
                    print("  fixed cell differs: %s %s: skyvern=%r "
                          "vs %s=%r" % (task, cell,
                                        my_fixed.get(cell), slug,
                                        pr_fixed.get(cell)))
        print("  fixed cells (verdict/sections/pass_rate_k): %d differ"
              % fixed_diffs)


if __name__ == "__main__":
    main()
