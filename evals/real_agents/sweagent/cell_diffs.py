"""Cell-diffs for audit 54 (SWE-agent) vs audits 46-53.

Established 19-cell unit per task row: verdict + 4 sections
(contract, stress, consistency, data) + pass_rate_k + 13
attacks, each attack entry a FULL tuple (kind, vector,
survived, detected, completed) -- including `completed` (the
audit-53 fold proved a 4-field tuple under-counts SuperAGI /
BabyAGI diffs). 25 rows x 19 cells = 475 cells per audit.

Compares sweagent/summary.json against each of audits 46-53
(Swarm, SuperAGI, AutoGPT, BabyAGI, Aider, Agency Swarm,
Phidata, ChatDev) and prints, per audit: total differing
cells, and the per-cell-type breakdown (verdict, sections,
pass_rate_k, attacks) with the task ids where each type
differs. Computed from the summary.json files on disk; nothing
copied from another audit's numbers.
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
]


def cells(row):
    """The 19 cells of one row as (cell_name, value) pairs.

    Attack cells are keyed by battery POSITION (attack[i]), not
    by (kind, vector) label: prior summaries record vector=None
    for some attack kinds (e.g. BabyAGI's clarification_injection
    on t4/t23), and name-keying those as diffs would count 4
    label-only artifacts where the (survived, detected,
    completed) values are identical. The battery order is the
    same across audits, so position is the honest key.
    """
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
            (a.get("survived"), a.get("detected"),
             a.get("completed"))))
    return out


def main():
    with open(os.path.join(BASE, "sweagent", "summary.json")) as h:
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
            # Compare positionally: the i-th cell of my row against
            # the i-th cell of the prior row (see cells()).
            my_cells = cells(my_rows[task])
            pr_cells = cells(pr_rows[task])
            assert len(my_cells) == len(pr_cells) == 19
            for (cell_name, value), (_, pvalue) in zip(
                    my_cells, pr_cells):
                if value != pvalue:
                    total += 1
                    kind = cell_name.split("[")[0].split(" ")[0]
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
                print("    %s %s: sweagent=%r vs %s=%r" % (
                    task, cell_name, value, slug, pvalue))
            if len(items) > 12:
                print("    ... (%d more)" % (len(items) - 12))


if __name__ == "__main__":
    main()
