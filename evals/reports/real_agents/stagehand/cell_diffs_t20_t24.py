"""Full-tuple cell diffs for Stagehand audit 90, slice t20-t24.

Same fixed full-tuple method as gpt-pilot/cell_diffs_t20_t24.py,
with one normalization the t5-t9 Stagehand report already needed:
attack cells are keyed (task, kind, occurrence) in deterministic
battery order, NOT by vector. The three audits record vectors
inconsistently (87/88 store vector=None for clarification_injection
on every task and for monitor/evaluator/misleading on t14, where
those cells are all unverified; Stagehand stores the vector when
the attack result carries one), so a vector key manufactures
"<missing>" pairs for the same cell. Battery order is identical
across all three audits (verified: the 19-kind sequence matches),
so occurrence-within-kind aligns the same cell.

A cell is either a per-task section 6-tuple (verdict, contract,
stress, consistency, data, pass_rate_k) or an attack cell with the
full outcome tuple (survived, detected, completed). A cell present
in one audit and absent in the other counts as a diff (reported
as missing).

Comparison set (per the slice brief): audit 87 (Claude Code CLI
2.1.327) and audit 88 (GPT-Pilot 0.2.13). Each comparison audit's
full summary (summary.json) is used; only its t20-t24 rows are
compared. (87 has no t20-t24 cumulative slice; 88's t20-t24
cumulative slice was verified identical to its summary.json.)

Stagehand runs 20 attacks (terminal_gap included); 87/88 ran 19,
so the attack comparison set is 95 cells (19x5); terminal_gap is
extra here and not compared. Section diffs are reported
separately (5 cells).

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
    evals/reports/real_agents/stagehand/cell_diffs_t20_t24.py
Writes cell_diffs_t20_t24.txt next to this script.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.normpath(os.path.join(HERE, ".."))

TASKS = ["t20_wine", "t21_percent_word", "t22_hard_math",
         "t23_station_add", "t24_underspecified"]

COMPARE = [
    ("87", "claude-code-cli"),
    ("88", "gpt-pilot"),
]

SECTION_KEYS = ("verdict", "contract", "stress", "consistency",
                "data", "pass_rate_k")


def _load_rows(path):
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload["rows"] if isinstance(payload, dict) else payload
    return [r for r in rows if r.get("task") in TASKS]


def _cells(rows):
    """Return ({section_key: tuple}, {attack_key: (tuple, vector)}).

    Attack keys are (task, kind, occurrence-in-kind) in battery
    order; the recorded vector (or None) rides along for display.
    """
    sections = {}
    attacks = {}
    for row in rows:
        task = row["task"]
        sections[(task, "sections")] = tuple(
            row.get(k) for k in SECTION_KEYS)
        seen = {}
        for attack in row.get("attacks") or []:
            if attack.get("kind") == "terminal_gap":
                continue  # 87/88 ran 19 attacks; not compared
            kind = attack.get("kind")
            occ = seen.get(kind, 0)
            seen[kind] = occ + 1
            attacks[(task, kind, occ)] = (
                (attack.get("survived"), attack.get("detected"),
                 attack.get("completed")),
                attack.get("vector") or attack.get("encoding"),
            )
    return sections, attacks


def main():
    ours_s, ours_a = _cells(_load_rows(
        os.path.join(HERE, "summary-slice-t20_wine-t24_underspecified.json")))
    lines = []
    lines.append("Stagehand audit 90 slice t20-t24 — full-tuple cell diffs")
    lines.append("ours: %d section cells + %d attack cells (%d tasks)"
                 % (len(ours_s), len(ours_a), len(TASKS)))
    lines.append("attack cells keyed (task, kind, occurrence) in battery "
                 "order; vectors shown for display only")
    lines.append("")
    for number, dirname in COMPARE:
        path = os.path.join(
            REPORTS, dirname, "summary.json")
        if not os.path.exists(path):
            lines.append("vs audit %s (%s): MISSING %s"
                         % (number, dirname, path))
            lines.append("")
            continue
        theirs_s, theirs_a = _cells(_load_rows(path))
        sdiffs = []
        for key in sorted(set(ours_s) | set(theirs_s), key=str):
            if ours_s.get(key) != theirs_s.get(key):
                sdiffs.append("  %r: ours %r vs %s %r"
                              % (key, ours_s.get(key), dirname,
                                 theirs_s.get(key)))
        adiffs = []
        for key in sorted(set(ours_a) | set(theirs_a), key=str):
            ours_v = ours_a.get(key, ("<missing>", None))
            theirs_v = theirs_a.get(key, ("<missing>", None))
            if ours_v[0] != theirs_v[0]:
                adiffs.append(
                    "  %r [vector ours=%r theirs=%r]: ours %r vs %s %r"
                    % (key, ours_v[1], theirs_v[1], ours_v[0],
                       dirname, theirs_v[0]))
        lines.append("vs audit %s (%s): sections %d/%d diffs, attacks "
                     "%d/%d diffs"
                     % (number, dirname, len(sdiffs), len(ours_s),
                        len(adiffs), len(ours_a)))
        lines.extend(sdiffs)
        lines.extend(adiffs)
        lines.append("")
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(HERE, "cell_diffs_t20_t24.txt"),
              "w", encoding="utf-8") as handle:
        handle.write(text + "\n")


if __name__ == "__main__":
    main()
