"""Focused verification for TRUSTRUN-CauseReceipt.

Scores the module's 25 labeled cases: the unsolved issue, the
difficulty boundary, the mixed-repeat bad run, the single-true
repeat, the bad run that beats a high difficulty, the ability
gap, the ability boundary, the unknown with no signals, the
unknown with a small gap, the passed run, the bad run with no
difficulty recorded, the difficulty with no repeats recorded,
the unknown with no ability fields, the cheap retry recovery,
the switch recovery, the escalate with no recovery, the
trajectory flag that wastes budget, the router beating
always-switch, the router beating always-retry, the unknown
that escalates, the ability gap below the difficulty bar, the
ability case with all-false repeats, the difficulty with empty
repeats, the retry with no token cost recorded, and the high
difficulty with no flag recorded. Every case is a fixed scripted
run record with an expected cause and decision, scored by
trustrun.cause_receipt. The campaign block checks the aggregate
numbers by hand: 24 failed runs, 7 issue_difficulty / 7 bad_run /
6 model_ability / 4 unknown; router recovers 13 at 13,200 tokens
spent and 0 wasted; always-retry recovers 7 at 21,650 spent and
16,150 wasted; always-switch recovers 6 at 21,650 spent and
13,950 wasted; trajectory-flag attempts 7, recovers 1 at 6,600
spent and 5,700 wasted; verdict REVIEW on the 4 unattributed.

Writes a machine-readable summary into
reports/cause-receipt-verify/summary.json. Expected yield: 25
labeled run cases, 25/25 match, campaign block matches.
Exits non-zero on any mismatch.

This script was derived from the lean-patch labeled cases in
evals/run_lean_patch_verify.py. Its REPORTS constant was
verified to point at cause-receipt-verify/ before the run, so it
cannot overwrite any round directory.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.cause_receipt import (  # noqa: E402
    CAUSE_BAD_RUN,
    CAUSE_ISSUE_DIFFICULTY,
    CAUSE_MODEL_ABILITY,
    CAUSE_NOT_A_FAILURE,
    CAUSE_UNKNOWN,
    DECISION_ESCALATE,
    DECISION_NONE,
    DECISION_RETRY,
    DECISION_SWITCH,
    attribute_failure,
    score_campaign,
)

REPORTS = os.path.join(HERE, "reports", "cause-receipt-verify")

EXPECTED_CAMPAIGN = {
    "runs": 25,
    "failed": 24,
    "attributions": {
        CAUSE_ISSUE_DIFFICULTY: 7,
        CAUSE_BAD_RUN: 7,
        CAUSE_MODEL_ABILITY: 6,
        CAUSE_UNKNOWN: 4,
    },
    "unknown": 4,
    "attribution_accuracy": 1.0,
    "router": {"attempts": 13, "recovered": 13,
               "tokens_spent": 13200, "tokens_wasted": 0},
    "always_retry": {"attempts": 24, "recovered": 7,
                     "tokens_spent": 21650, "tokens_wasted": 16150},
    "always_switch": {"attempts": 24, "recovered": 6,
                      "tokens_spent": 21650, "tokens_wasted": 13950},
    "trajectory_flag": {"attempts": 7, "recovered": 1,
                        "tokens_spent": 6600, "tokens_wasted": 5700},
    "verdict": "REVIEW",
}


def _run(case_id, outcome="failed", **fields):
    run = {"id": case_id, "issue_id": "i-" + case_id,
           "model_id": "m1", "outcome": outcome}
    run.update(fields)
    return run


def cause_receipt_cases():
    """25 labeled run cases: (case_id, run, expected cause,
    expected decision)."""
    cases = []

    # The unsolved issue: difficulty 1.0, no repeat solved it,
    # small ability gap. Escalate, never retry or switch.
    cases.append((
        "unsolved_issue",
        _run("unsolved_issue", issue_difficulty=1.0,
             repeat_outcomes=[False, False],
             model_pass_rate=0.4, best_other_pass_rate=0.5,
             other_model_outcome=False, trajectory_flag=True,
             tokens=1000),
        CAUSE_ISSUE_DIFFICULTY, DECISION_ESCALATE,
    ))

    # The difficulty boundary: exactly 0.9 attributes.
    cases.append((
        "difficulty_boundary",
        _run("difficulty_boundary", issue_difficulty=0.9,
             repeat_outcomes=[False],
             model_pass_rate=0.5, best_other_pass_rate=0.55,
             other_model_outcome=False, trajectory_flag=True,
             tokens=800),
        CAUSE_ISSUE_DIFFICULTY, DECISION_ESCALATE,
    ))

    # The mixed-repeat bad run: one repeat solved it.
    cases.append((
        "bad_run_mixed",
        _run("bad_run_mixed", issue_difficulty=0.6,
             repeat_outcomes=[False, True],
             model_pass_rate=0.6, best_other_pass_rate=0.7,
             other_model_outcome=False, trajectory_flag=False,
             tokens=1200),
        CAUSE_BAD_RUN, DECISION_RETRY,
    ))

    # A single True repeat is enough: the model solved it once.
    cases.append((
        "bad_run_single_true",
        _run("bad_run_single_true", issue_difficulty=0.5,
             repeat_outcomes=[True],
             other_model_outcome=False, trajectory_flag=False,
             tokens=600),
        CAUSE_BAD_RUN, DECISION_RETRY,
    ))

    # The bad run beats a high difficulty: the repeat solved an
    # issue at difficulty 0.95, so the run was the variable.
    cases.append((
        "bad_run_beats_difficulty",
        _run("bad_run_beats_difficulty", issue_difficulty=0.95,
             repeat_outcomes=[False, True],
             other_model_outcome=False, trajectory_flag=True,
             tokens=900),
        CAUSE_BAD_RUN, DECISION_RETRY,
    ))

    # The ability gap: best other model beats this one by 0.35.
    cases.append((
        "model_ability",
        _run("model_ability", issue_difficulty=0.4,
             repeat_outcomes=[False, False],
             model_pass_rate=0.3, best_other_pass_rate=0.65,
             other_model_outcome=True, trajectory_flag=False,
             tokens=1500),
        CAUSE_MODEL_ABILITY, DECISION_SWITCH,
    ))

    # The ability boundary: exactly a 0.25 gap attributes.
    cases.append((
        "ability_boundary",
        _run("ability_boundary", issue_difficulty=0.4,
             repeat_outcomes=[False],
             model_pass_rate=0.5, best_other_pass_rate=0.75,
             other_model_outcome=True, trajectory_flag=False,
             tokens=700),
        CAUSE_MODEL_ABILITY, DECISION_SWITCH,
    ))

    # Unknown with no signals at all: escalate, never guess.
    cases.append((
        "unknown_no_signals",
        _run("unknown_no_signals", tokens=500),
        CAUSE_UNKNOWN, DECISION_ESCALATE,
    ))

    # Unknown with a small gap: 0.10 is below the 0.25 bar.
    cases.append((
        "unknown_small_gap",
        _run("unknown_small_gap", issue_difficulty=0.3,
             repeat_outcomes=[False, False],
             model_pass_rate=0.6, best_other_pass_rate=0.7,
             other_model_outcome=False, trajectory_flag=False,
             tokens=400),
        CAUSE_UNKNOWN, DECISION_ESCALATE,
    ))

    # A passed run is not a failure to attribute.
    cases.append((
        "passed_run",
        _run("passed_run", outcome="passed",
             issue_difficulty=1.0, tokens=1000),
        CAUSE_NOT_A_FAILURE, DECISION_NONE,
    ))

    # The bad run with no difficulty recorded: the repeat is
    # enough on its own.
    cases.append((
        "bad_run_missing_difficulty",
        _run("bad_run_missing_difficulty",
             repeat_outcomes=[False, True],
             other_model_outcome=False, trajectory_flag=False,
             tokens=1100),
        CAUSE_BAD_RUN, DECISION_RETRY,
    ))

    # The difficulty with no repeats recorded: 0.92 attributes
    # on the population statistic alone.
    cases.append((
        "difficulty_missing_repeats",
        _run("difficulty_missing_repeats", issue_difficulty=0.92,
             model_pass_rate=0.5, best_other_pass_rate=0.55,
             other_model_outcome=False, trajectory_flag=True,
             tokens=750),
        CAUSE_ISSUE_DIFFICULTY, DECISION_ESCALATE,
    ))

    # Unknown with no ability fields: no gap is computable.
    cases.append((
        "unknown_missing_ability",
        _run("unknown_missing_ability", issue_difficulty=0.5,
             repeat_outcomes=[False],
             other_model_outcome=False, trajectory_flag=False,
             tokens=650),
        CAUSE_UNKNOWN, DECISION_ESCALATE,
    ))

    # The cheap retry recovery: two failures then a success.
    cases.append((
        "retry_recovers_cheap",
        _run("retry_recovers_cheap", issue_difficulty=0.55,
             repeat_outcomes=[False, False, True],
             other_model_outcome=False, trajectory_flag=False,
             tokens=300),
        CAUSE_BAD_RUN, DECISION_RETRY,
    ))

    # The switch recovery: a 0.60 gap and the other model solves it.
    cases.append((
        "switch_recovers",
        _run("switch_recovers", issue_difficulty=0.45,
             repeat_outcomes=[False],
             model_pass_rate=0.2, best_other_pass_rate=0.8,
             other_model_outcome=True, trajectory_flag=False,
             tokens=2000),
        CAUSE_MODEL_ABILITY, DECISION_SWITCH,
    ))

    # Escalate with no recovery: the issue is unsolved and the
    # flag still fires, which is the trajectory-flag waste.
    cases.append((
        "escalate_no_recovery",
        _run("escalate_no_recovery", issue_difficulty=1.0,
             repeat_outcomes=[False],
             other_model_outcome=False, trajectory_flag=True,
             tokens=1300),
        CAUSE_ISSUE_DIFFICULTY, DECISION_ESCALATE,
    ))

    # The flag wastes budget: difficulty 0.95, no repeat solved
    # it, flagged anyway, because the flag grades the task.
    cases.append((
        "flag_wastes",
        _run("flag_wastes", issue_difficulty=0.95,
             repeat_outcomes=[False, False],
             other_model_outcome=False, trajectory_flag=True,
             tokens=1000),
        CAUSE_ISSUE_DIFFICULTY, DECISION_ESCALATE,
    ))

    # The router beats always-switch: retry recovers, switch
    # would not, and the gap is only 0.05.
    cases.append((
        "router_beats_switch",
        _run("router_beats_switch", issue_difficulty=0.5,
             repeat_outcomes=[False, True],
             model_pass_rate=0.7, best_other_pass_rate=0.75,
             other_model_outcome=False, trajectory_flag=False,
             tokens=1400),
        CAUSE_BAD_RUN, DECISION_RETRY,
    ))

    # The router beats always-retry: switch recovers, retry
    # would not, and no repeat ever solved it.
    cases.append((
        "router_beats_retry",
        _run("router_beats_retry", issue_difficulty=0.35,
             repeat_outcomes=[False, False],
             model_pass_rate=0.25, best_other_pass_rate=0.6,
             other_model_outcome=True, trajectory_flag=False,
             tokens=1600),
        CAUSE_MODEL_ABILITY, DECISION_SWITCH,
    ))

    # Unknown that escalates: high ability, low difficulty,
    # one failed repeat, no other model solves it.
    cases.append((
        "unknown_escalates",
        _run("unknown_escalates", issue_difficulty=0.2,
             repeat_outcomes=[False],
             model_pass_rate=0.8, best_other_pass_rate=0.85,
             other_model_outcome=False, trajectory_flag=False,
             tokens=450),
        CAUSE_UNKNOWN, DECISION_ESCALATE,
    ))

    # Ability, not difficulty: 0.89 is below the 0.9 bar, and
    # the 0.30 gap attributes.
    cases.append((
        "ability_not_difficulty",
        _run("ability_not_difficulty", issue_difficulty=0.89,
             repeat_outcomes=[False],
             model_pass_rate=0.4, best_other_pass_rate=0.7,
             other_model_outcome=True, trajectory_flag=False,
             tokens=1000),
        CAUSE_MODEL_ABILITY, DECISION_SWITCH,
    ))

    # Ability with all-false repeats: no variance evidence, but
    # the 0.30 gap attributes.
    cases.append((
        "ability_all_false_repeats",
        _run("ability_all_false_repeats", issue_difficulty=0.5,
             repeat_outcomes=[False, False, False],
             model_pass_rate=0.35, best_other_pass_rate=0.65,
             other_model_outcome=True, trajectory_flag=False,
             tokens=900),
        CAUSE_MODEL_ABILITY, DECISION_SWITCH,
    ))

    # Difficulty with empty repeats: no repeat evidence, but
    # 1.0 attributes on the statistic alone.
    cases.append((
        "difficulty_empty_repeats",
        _run("difficulty_empty_repeats", issue_difficulty=1.0,
             repeat_outcomes=[],
             model_pass_rate=0.5, best_other_pass_rate=0.6,
             other_model_outcome=False, trajectory_flag=True,
             tokens=850),
        CAUSE_ISSUE_DIFFICULTY, DECISION_ESCALATE,
    ))

    # The retry with no token cost recorded: recovers at 0 cost.
    cases.append((
        "tokens_missing",
        _run("tokens_missing", issue_difficulty=0.6,
             repeat_outcomes=[False, True],
             other_model_outcome=False, trajectory_flag=False),
        CAUSE_BAD_RUN, DECISION_RETRY,
    ))

    # High difficulty with no flag recorded: escalate, and the
    # flag baseline spends nothing on it.
    cases.append((
        "flag_not_set_high_difficulty",
        _run("flag_not_set_high_difficulty", issue_difficulty=0.93,
             repeat_outcomes=[False],
             other_model_outcome=False, tokens=750),
        CAUSE_ISSUE_DIFFICULTY, DECISION_ESCALATE,
    ))

    return cases


def main():
    assert REPORTS.endswith("cause-receipt-verify"), REPORTS
    os.makedirs(REPORTS, exist_ok=True)
    results = []
    runs = []
    for case in cause_receipt_cases():
        (case_id, run, expected_cause, expected_decision) = case
        run["expected_cause"] = expected_cause
        runs.append(run)
        result = attribute_failure(run)
        match = (
            result["cause"] == expected_cause
            and result["decision"] == expected_decision
        )
        results.append({
            "case_id": case_id,
            "expected_cause": expected_cause,
            "actual_cause": result["cause"],
            "expected_decision": expected_decision,
            "actual_decision": result["decision"],
            "match": match,
        })
    matched = sum(1 for item in results if item["match"])

    campaign = score_campaign(runs)
    campaign_match = (
        campaign["runs"] == EXPECTED_CAMPAIGN["runs"]
        and campaign["failed"] == EXPECTED_CAMPAIGN["failed"]
        and campaign["attributions"] == EXPECTED_CAMPAIGN["attributions"]
        and campaign["unknown"] == EXPECTED_CAMPAIGN["unknown"]
        and campaign["attribution_accuracy"]
        == EXPECTED_CAMPAIGN["attribution_accuracy"]
        and campaign["router"] == EXPECTED_CAMPAIGN["router"]
        and campaign["always_retry"] == EXPECTED_CAMPAIGN["always_retry"]
        and campaign["always_switch"] == EXPECTED_CAMPAIGN["always_switch"]
        and campaign["trajectory_flag"]
        == EXPECTED_CAMPAIGN["trajectory_flag"]
        and campaign["verdict"] == EXPECTED_CAMPAIGN["verdict"]
    )
    summary = {
        "cases": len(results),
        "matched": matched,
        "results": results,
        "campaign": campaign,
        "campaign_match": campaign_match,
    }
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=1)
    print("cause-receipt labeled cases: %d/%d match"
          % (matched, len(results)))
    for item in results:
        if not item["match"]:
            print(
                "MISMATCH %s: expected %s/%s, got %s/%s"
                % (
                    item["case_id"],
                    item["expected_cause"],
                    item["expected_decision"],
                    item["actual_cause"],
                    item["actual_decision"],
                )
            )
    print("cause-receipt campaign block: %s"
          % ("match" if campaign_match else "MISMATCH"))
    if not campaign_match:
        print("expected: %s" % json.dumps(EXPECTED_CAMPAIGN, indent=1))
        print("actual: %s" % json.dumps({
            "runs": campaign["runs"],
            "failed": campaign["failed"],
            "attributions": campaign["attributions"],
            "unknown": campaign["unknown"],
            "attribution_accuracy": campaign["attribution_accuracy"],
            "router": campaign["router"],
            "always_retry": campaign["always_retry"],
            "always_switch": campaign["always_switch"],
            "trajectory_flag": campaign["trajectory_flag"],
            "verdict": campaign["verdict"],
        }, indent=1))
    if matched != len(results) or not campaign_match:
        sys.exit(1)


if __name__ == "__main__":
    main()
