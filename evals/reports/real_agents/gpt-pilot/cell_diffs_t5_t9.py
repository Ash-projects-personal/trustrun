"""Full-tuple cell diffs for audit 88 (gpt-pilot), slice t5-t9.

Same fixed full-tuple method as cell_diffs_t1_t4.py: a cell is either
a per-task section 6-tuple (verdict, contract, stress, consistency,
data, pass_rate_k) or an attack cell keyed (task, kind, vector,
occurrence) with the full outcome tuple (survived, detected,
completed). A cell present in one audit and absent in the other
counts as a diff (reported as missing).

Comparison set (per the slice brief): audit 85 (Copilot CLI),
86 (CodeBuddy), 87 (Claude Code CLI). Each comparison audit's full
summary.json is used; only its t5-t9 rows are compared.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
    evals/reports/real_agents/gpt-pilot/cell_diffs_t5_t9.py
Writes cell_diffs_t5_t9.txt next to this script.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
REPORTS = os.path.join(ROOT, "evals", "reports", "real_agents")

TASKS = ["t5_simple_math", "t6_lowconf", "t7_toolmath",
         "t8_imperative", "t9_olympics"]

COMPARE = [
    ("85", "copilot-cli"),
    ("86", "codebuddy"),
    ("87", "claude-code-cli"),
]

SECTION_KEYS = ("verdict", "contract", "stress", "consistency",
                "data", "pass_rate_k")


def _load_rows(path):
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload["rows"] if isinstance(payload, dict) else payload
    return [r for r in rows if r.get("task") in TASKS]


def _cells(rows):
    """Return {cell_key: tuple} for one audit's t5-t9 rows.

    Attack cells are keyed (task, kind, vector, occurrence): the
    battery runs two misleading_principal cells per task (and two
    vector-less clarification_injection cells on some tasks), which
    share a (kind, vector) key, so the occurrence index keeps all
    19 attack cells per task distinct. Order is the battery's
    deterministic attack order, identical across audits.
    """
    cells = {}
    for row in rows:
        task = row["task"]
        cells[(task, "sections")] = tuple(row.get(k) for k in SECTION_KEYS)
        seen = {}
        for attack in row.get("attacks") or []:
            base = (task, attack.get("kind"),
                    attack.get("vector") or attack.get("encoding"))
            occ = seen.get(base, 0)
            seen[base] = occ + 1
            cells[base + (occ,)] = (attack.get("survived"),
                                    attack.get("detected"),
                                    attack.get("completed"))
    return cells


def main():
    ours = _cells(_load_rows(os.path.join(HERE, "rows_partial.json")))
    lines = []
    lines.append("GPT-Pilot audit 88 slice t5-t9 — full-tuple cell diffs")
    lines.append("ours: %d cells (%d tasks)" % (len(ours), len(TASKS)))
    lines.append("")
    for number, dirname in COMPARE:
        path = os.path.join(REPORTS, dirname, "summary.json")
        if not os.path.exists(path):
            lines.append("audit %s (%s): NO summary.json — skipped"
                         % (number, dirname))
            continue
        theirs = _cells(_load_rows(path))
        keys = sorted(set(ours) | set(theirs), key=str)
        diffs = []
        for key in keys:
            ours_v = ours.get(key, "<missing>")
            theirs_v = theirs.get(key, "<missing>")
            if ours_v != theirs_v:
                diffs.append((key, ours_v, theirs_v))
        lines.append("vs audit %s (%s): %d/%d diffs"
                     % (number, dirname, len(diffs), len(keys)))
        for key, ours_v, theirs_v in diffs:
            lines.append("  %s: ours %r vs %s %r"
                         % (key, ours_v, dirname, theirs_v))
        lines.append("")
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(HERE, "cell_diffs_t5_t9.txt"), "w",
              encoding="utf-8") as handle:
        handle.write(text + "\n")


if __name__ == "__main__":
    main()
