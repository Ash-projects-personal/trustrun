"""Cell-diffs for audit 85 (copilot-cli), slice t5-t8 only, vs audits 70-73
(the 0-diff cluster: Cline, Roo Code, OpenCode, Continue), audit 82
(ForgeCode), audit 83 (Sweep), and audit 84 (Kimi Code).

Method copied VERBATIM from evals/real_agents/kimi_code/cell_diffs.py
(audit 84), which copied it VERBATIM from evals/real_agents/cline/
cell_diffs.py (audit 70): established 19-cell unit per task row --
verdict + 4 sections (contract, stress, consistency, data) +
pass_rate_k + 13 attacks, each attack entry a FULL tuple (kind,
vector, survived, detected, completed). The battery grew 13 -> 14
attacks when TRUSTRUN-ToolFailureSwallow shipped (2026-11-12),
adding tool_failure_visibility as attack #3, and 14 -> 18 attacks
with the four newer classes (adaptive_injection, task_tamper,
ci_harness_inject, prompt_adware). Audits 70-73 ran on the 14-attack
battery, so the four newer classes are DROPPED from the Copilot CLI
side before a comparison against them -- otherwise cells present on
one side only would count as diffs artifactually.
tool_failure_visibility is dropped from both sides in every
comparison (the cline convention). ForgeCode (audit 82), Sweep
(audit 83), and Kimi Code (audit 84) ran on the same 18-attack
battery as Copilot CLI, so those comparisons keep all four newer
classes.

Two alignments (same as audit 62):
- NAME-KEYED (audit-55 method): attack cells keyed by (kind,
  vector), compared on the UNION of cell keys -- a cell present on
  one side only counts as a diff instead of crashing with KeyError.
  Vector=None entries fall back to position, so no label-only
  artifact is counted.
- POSITION-KEYED (audit-54 method): attack cells keyed by battery
  position (attack[i]); rows with fewer attacks than the other side
  count the missing positions as diffs (a crash row carries
  attacks=[]).

Slice scope: only the 4 graded slice tasks (t5-t8). Per-row unit
after dropping tool_failure_visibility is 6 + 17 = 23 cells vs
ForgeCode/Sweep/Kimi Code (92 cells over 4 rows) and 6 + 13 = 19
cells vs the 0-diff cluster (76 cells over 4 rows).

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
    evals/reports/real_agents/copilot-cli/cell_diffs_t5_t8.py > \\
    evals/reports/real_agents/copilot-cli/cell_diffs_t5_t8.txt
"""

import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIORS = [
    (70, "cline", "Cline"),
    (71, "roo", "Roo Code"),
    (72, "opencode", "OpenCode"),
    (73, "continue", "Continue"),
    (82, "forgecode", "ForgeCode"),
    (83, "sweep", "Sweep"),
    (84, "kimi-code", "Kimi Code"),
]
SLICE_TASKS = ["t5_simple_math", "t6_lowconf", "t7_toolmath", "t8_imperative"]

# The 14th attack (TRUSTRUN-ToolFailureSwallow, 2026-11-12) is
# dropped from the diff unit so audits on the 13-attack battery
# stay comparable at 475 cells. See the module docstring.
_DROPPED_KIND = "tool_failure_visibility"
# The four newer attack classes (post audit-73 battery growth)
# exist only on the ForgeCode/Sweep/Kimi-Code/Copilot-CLI side; they
# are dropped from the Copilot CLI side before a comparison against
# a 14-attack prior.
_NEWER_KINDS = {"adaptive_injection", "task_tamper",
                "ci_harness_inject", "prompt_adware"}


def _trimmed(row, drop_newer=False):
    """A copy of the row without the dropped 14th attack (and,
    against a 14-attack prior, without the four newer classes)."""
    trimmed = dict(row)
    trimmed["attacks"] = [
        a for a in row.get("attacks", [])
        if a.get("kind") != _DROPPED_KIND
        and not (drop_newer and a.get("kind") in _NEWER_KINDS)
    ]
    return trimmed


def _attack_key(attack, index):
    kind = attack.get("kind")
    vector = attack.get("vector")
    if vector is None:
        return ("attack-pos-%d" % index, kind, None)
    return ("attack-%s/%s" % (kind, vector), kind, vector)


def name_keyed_cells(row):
    """The cells of one row as (cell_name, value) pairs,
    attack cells keyed by (kind, vector)."""
    out = [
        ("verdict", row["verdict"]),
        ("contract", row["contract"]),
        ("stress", row["stress"]),
        ("consistency", row["consistency"]),
        ("data", row["data"]),
        ("pass_rate_k", row["pass_rate_k"]),
    ]
    for i, a in enumerate(row["attacks"]):
        key, _, _ = _attack_key(a, i)
        out.append((key, (a.get("survived"), a.get("detected"),
                          a.get("completed"))))
    return out


def position_keyed_cells(row):
    """The cells of one row as (cell_name, value) pairs,
    attack cells keyed by battery position."""
    out = [
        ("verdict", row["verdict"]),
        ("contract", row["contract"]),
        ("stress", row["stress"]),
        ("consistency", row["consistency"]),
        ("data", row["data"]),
        ("pass_rate_k", row["pass_rate_k"]),
    ]
    for i, a in enumerate(row["attacks"]):
        out.append(("attack[%d] %s/%s" % (
            i, a.get("kind"), a.get("vector")),
            # FULL tuple (kind, vector, survived, detected,
            # completed): _diff_position_keyed compares VALUES only,
            # so kind/vector must live in the value, not just the
            # cell name. Audit-64 fold fix (2026-11-12): the 3-field
            # value under-counted wherever two audits place
            # different vectors at the same battery position with
            # identical outcomes (BabyAGI 69 vs correct 73).
            (a.get("kind"), a.get("vector"), a.get("survived"),
             a.get("detected"), a.get("completed"))))
    return out


def _diff_name_keyed(my_rows, pr_rows):
    diffs = {}
    total = 0
    for task in sorted(my_rows):
        my_cells = dict(name_keyed_cells(my_rows[task]))
        pr_cells = dict(name_keyed_cells(pr_rows[task]))
        for cell_name in sorted(set(my_cells) | set(pr_cells)):
            value = my_cells.get(cell_name)
            pvalue = pr_cells.get(cell_name)
            if value != pvalue:
                total += 1
                kind = ("attack" if cell_name.startswith("attack")
                        else cell_name)
                diffs.setdefault(kind, []).append(
                    (task, cell_name, value, pvalue))
    return total, diffs


def _diff_position_keyed(my_rows, pr_rows):
    diffs = {}
    total = 0
    for task in sorted(my_rows):
        my_cells = position_keyed_cells(my_rows[task])
        pr_cells = position_keyed_cells(pr_rows[task])
        # Fixed 6 cells first, then attacks by position. A side
        # with fewer attacks counts its missing positions as
        # diffs (a crash row carries attacks=[]).
        for idx in range(max(len(my_cells), len(pr_cells))):
            if idx < len(my_cells):
                cell_name, value = my_cells[idx]
            else:
                cell_name, value = pr_cells[idx][0], None
            if idx < len(pr_cells):
                _, pvalue = pr_cells[idx]
            else:
                pvalue = None
            if value != pvalue:
                total += 1
                kind = ("attack" if cell_name.startswith("attack")
                        else cell_name)
                diffs.setdefault(kind, []).append(
                    (task, cell_name, value, pvalue))
    return total, diffs


def main():
    with open(os.path.join(
            BASE, "copilot-cli",
            "summary-slice-t1_factual-t8_imperative.json")) as h:
        mine = json.load(h)
    my_rows_all = {r["task"]: r for r in mine["rows"]
                   if r["task"] in SLICE_TASKS}
    assert sorted(my_rows_all) == sorted(SLICE_TASKS), sorted(my_rows_all)
    for num, slug, name in PRIORS:
        with open(os.path.join(BASE, slug, "summary.json")) as h:
            prior = json.load(h)
        pr_rows_all = {r["task"]: r for r in prior["rows"]}
        drop_newer = len(next(iter(pr_rows_all.values()))["attacks"]) == 14
        my_rows = {t: _trimmed(my_rows_all[t], drop_newer)
                   for t in SLICE_TASKS}
        pr_rows = {t: _trimmed(pr_rows_all[t], False)
                   for t in SLICE_TASKS}
        unit = 6 + len(next(iter(my_rows.values()))["attacks"])
        total_cells = unit * len(SLICE_TASKS)
        n_total, n_diffs = _diff_name_keyed(my_rows, pr_rows)
        p_total, p_diffs = _diff_position_keyed(my_rows, pr_rows)
        print("audit 85 copilot-cli (slice t5-t8) vs audit %d %s (%s): "
              "%d / %d cells differ (name-keyed union); %d / %d "
              "(position-keyed)"
              % (num, name, slug, n_total, total_cells,
                 p_total, total_cells))
        for kind in ("verdict", "contract", "stress", "consistency",
                     "data", "pass_rate_k", "attack"):
            items = n_diffs.get(kind, [])
            if not items:
                continue
            print("  %s: %d -- tasks %s" % (
                kind, len(items),
                sorted({t for t, _, _, _ in items})))
            for task, cell_name, value, pvalue in items[:12]:
                print("    %s %s: copilot-cli=%r vs %s=%r" % (
                    task, cell_name, value, slug, pvalue))
            if len(items) > 12:
                print("    ... (%d more)" % (len(items) - 12))


if __name__ == "__main__":
    main()
