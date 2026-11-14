"""Cell-diffs for audit 62 (browser-use) vs audits 46-61.

Established 19-cell unit per task row: verdict + 4 sections
(contract, stress, consistency, data) + pass_rate_k + 13
attacks, each attack entry a FULL tuple (kind, vector,
survived, detected, completed) -- including `completed` (the
audit-53 fold proved a 4-field tuple under-counts SuperAGI /
BabyAGI diffs). 25 rows x 19 cells = 475 cells per audit.

Compares browser-use/summary.json against each of audits 46-61
(Swarm, SuperAGI, AutoGPT, BabyAGI, Aider, Agency Swarm,
Phidata, ChatDev, SWE-agent, Open Interpreter, GPT-Researcher,
STORM, Qwen-Agent, Magentic-One, FastAgent, Cheshire Cat)
and prints, per audit: the differing-cell total under BOTH
alignments, and the per-cell-type breakdown (verdict, sections,
pass_rate_k, attacks) with the task ids where each type
differs. Computed from the summary.json files on disk; nothing
copied from another audit's numbers.

Two alignments (the brief requires both, so the parent can
cross-check):
- NAME-KEYED (audit-55 method): attack cells are keyed by
  (kind, vector), compared on the UNION of cell keys -- a cell
  present on one side only (a battery renamed a vector between
  audits) counts as a diff instead of crashing with KeyError
  (audit-55 fold fix). Vector=None entries fall back to
  position, so no label-only artifact is counted.
- POSITION-KEYED (audit-54 method): attack cells are keyed by
  battery position (attack[i]); the battery order is the same
  across audits, so position is the honest key when vectors are
  missing or renamed. Rows with fewer attacks than the other
  side count the missing positions as diffs (no assert crash --
  a crash row carries attacks=[]).
"""

import json
import os

BASE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))),
    "reports", "real_agents")
PRIORS = [
    (46, "swarm", "Swarm"),
    (47, "superagi", "SuperAGI"),
    (48, "autogpt", "AutoGPT"),
    (49, "babyagi", "BabyAGI"),
    (50, "aider", "Aider"),
    (51, "agency_swarm", "Agency Swarm"),
    (52, "phidata", "Phidata"),
    (53, "chatdev", "ChatDev"),
    (54, "sweagent", "SWE-agent"),
    (55, "openinterpreter", "Open Interpreter"),
    (56, "gptresearcher", "GPT-Researcher"),
    (57, "storm", "STORM"),
    (58, "qwen_agent", "Qwen-Agent"),
    (59, "magentic_one", "Magentic-One"),
    (60, "fastagent", "FastAgent"),
    (61, "cheshirecat", "Cheshire Cat"),
]


def _attack_key(attack, index):
    kind = attack.get("kind")
    vector = attack.get("vector")
    if vector is None:
        return ("attack-pos-%d" % index, kind, None)
    return ("attack-%s/%s" % (kind, vector), kind, vector)


def name_keyed_cells(row):
    """The 19 cells of one row as (cell_name, value) pairs,
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
    """The 19 cells of one row as (cell_name, value) pairs,
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
    with open(os.path.join(BASE, "browser-use", "summary.json")) as h:
        mine = json.load(h)
    my_rows = {r["task"]: r for r in mine["rows"]}
    assert len(my_rows) == 25, len(my_rows)
    for num, slug, name in PRIORS:
        with open(os.path.join(BASE, slug, "summary.json")) as h:
            prior = json.load(h)
        pr_rows = {r["task"]: r for r in prior["rows"]}
        assert len(pr_rows) == 25, (slug, len(pr_rows))
        n_total, n_diffs = _diff_name_keyed(my_rows, pr_rows)
        p_total, p_diffs = _diff_position_keyed(my_rows, pr_rows)
        print("audit 62 browser-use vs audit %d %s (%s): %d / 475 cells "
              "differ (name-keyed union); %d / 475 (position-keyed)"
              % (num, name, slug, n_total, p_total))
        for kind in ("verdict", "contract", "stress", "consistency",
                     "data", "pass_rate_k", "attack"):
            items = n_diffs.get(kind, [])
            if not items:
                continue
            print("  %s: %d -- tasks %s" % (
                kind, len(items),
                sorted({t for t, _, _, _ in items})))
            for task, cell_name, value, pvalue in items[:12]:
                print("    %s %s: browser-use=%r vs %s=%r" % (
                    task, cell_name, value, slug, pvalue))
            if len(items) > 12:
                print("    ... (%d more)" % (len(items) - 12))


if __name__ == "__main__":
    main()
