"""Cell-diffs for audit 55 (Open Interpreter) vs audits 46-54.

Established 19-cell unit per task row: verdict + 4 sections
(contract, stress, consistency, data) + pass_rate_k + 13
attacks, each attack entry a FULL tuple (kind, vector,
survived, detected, completed) -- including `completed` (the
audit-53 fold proved a 4-field tuple under-counts SuperAGI /
BabyAGI diffs). 25 rows x 19 cells = 475 cells per audit.

Compares openinterpreter/summary.json against each of audits
46-54 (Swarm, SuperAGI, AutoGPT, BabyAGI, Aider, Agency Swarm,
Phidata, ChatDev, SWE-agent) and prints, per audit: total
differing cells, and the per-cell-type breakdown (verdict,
sections, pass_rate_k, attacks) with the task ids where each
type differs. Computed from the summary.json files on disk;
nothing copied from another audit's numbers.

Alignment is NAME-KEYED: attack cells are keyed by
(kind, vector), not by battery position. (The audit-54 script
used position-keying because some prior summaries record
vector=None for some attack kinds; name-keying those as diffs
would count label-only artifacts where the (survived,
detected, completed) values are identical. This script
therefore keys by (kind, vector) ONLY where the vector is
present on both sides, and falls back to position for
vector=None entries, so no label-only artifact is counted.)
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
]


def _attack_key(attack, index):
    kind = attack.get("kind")
    vector = attack.get("vector")
    if vector is None:
        return ("attack-pos-%d" % index, kind, None)
    return ("attack-%s/%s" % (kind, vector), kind, vector)


def cells(row):
    """The 19 cells of one row as (cell_name, value) pairs."""
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


def main():
    with open(os.path.join(BASE, "openinterpreter", "summary.json")) as h:
        mine = json.load(h)
    my_rows = {r["task"]: r for r in mine["rows"]}
    assert len(my_rows) == 25, len(my_rows)
    for num, slug, name in PRIORS:
        with open(os.path.join(BASE, slug, "summary.json")) as h:
            prior = json.load(h)
        pr_rows = {r["task"]: r for r in prior["rows"]}
        assert len(pr_rows) == 25, (slug, len(pr_rows))
        diffs = {}
        total = 0
        for task in sorted(my_rows):
            # Compare name-keyed: the cell of my row against the
            # same-named cell of the prior row. Union of keys: a
            # cell present on one side only (battery renamed a
            # vector between audits) counts as a diff instead of
            # crashing with KeyError (audit-55 fold fix; the
            # position-keyed cross-check in the fold entry is the
            # comparable number when batteries differ in naming).
            my_cells = dict(cells(my_rows[task]))
            pr_cells = dict(cells(pr_rows[task]))
            for cell_name in sorted(set(my_cells) | set(pr_cells)):
                value = my_cells.get(cell_name)
                pvalue = pr_cells.get(cell_name)
                if value != pvalue:
                    total += 1
                    kind = ("attack" if cell_name.startswith("attack")
                            else cell_name)
                    diffs.setdefault(kind, []).append(
                        (task, cell_name, value, pvalue))
        print("audit %d %s: %d / 475 cells differ" % (num, name, total))
        for kind in ("verdict", "contract", "stress", "consistency",
                     "data", "pass_rate_k", "attack"):
            items = diffs.get(kind, [])
            if not items:
                continue
            print("  %s: %d -- tasks %s" % (
                kind, len(items),
                sorted({t for t, _, _, _ in items})))
            for task, cell_name, value, pvalue in items[:12]:
                print("    %s %s: openinterpreter=%r vs %s=%r" % (
                    task, cell_name, value, slug, pvalue))
            if len(items) > 12:
                print("    ... (%d more)" % (len(items) - 12))


if __name__ == "__main__":
    main()
