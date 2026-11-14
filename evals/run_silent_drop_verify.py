"""Focused verification for TRUSTRUN-SilentDrop.

Scores the module's 25 labeled cases: three failures, nine
successes, eight successes, failure-failure-success-failure,
alternating to regression on run 8, alternating inconclusive,
five failures, twelve successes, failure-success-success-
failure, nine-step alternating to regression on run 7, the empty
stream, a single success, a single failure, failure-heavy
inconclusive, three successes then three failures, nine
successes then failures, eight failures, a mixed inconclusive
stream, failure-failure-success-failure-failure, success-
failure-failure-success-failure-failure-success, and the aiobs
rates (0.91 to 0.76): three failures, thirteen successes,
twelve successes, alternating inconclusive, and failure-
failure-success-failure-failure. Every case is a fixed outcome
stream with a hand-computed decision and runs-used, scored by
trustrun.silent_drop. The campaign block checks the aggregate
numbers by hand: 25 streams, 10 BLOCK / 11 REVIEW / 4 PASS,
mean 6.14 runs to decision over the 14 decided streams, mean
460 production runs to detection at 1% label coverage over the
10 BLOCK streams, verdict BLOCK. The sequential-vs-fixed check
compares Wald's expected runs to detect (15.46 labeled runs at
0.90 to 0.70) against the fixed-sample size (29.20), a 1.89x
ratio on those rates, and the aiobs check (24.12 labeled runs,
about 2,412 production runs at 1% coverage).

Writes a machine-readable summary into
reports/silent-drop-verify/summary.json. Expected yield: 25
labeled stream cases, 25/25 match, campaign block matches.
Exits non-zero on any mismatch.

The cases are synthetic streams with hand-computed verdicts,
not production traces.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.silent_drop import (  # noqa: E402
    DECISION_INCONCLUSIVE,
    DECISION_NO_REGRESSION,
    DECISION_REGRESSION,
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_REVIEW,
    detection_delay,
    expected_runs_to_detect,
    fixed_sample_size,
    score_campaign,
    score_stream,
)

REPORTS = os.path.join(HERE, "reports", "silent-drop-verify")

# (case_id, stream as "S"/"F" string, p0, p1, expected decision, expected runs)
CASES = [
    ("three-failures", "FFF", 0.9, 0.7, DECISION_REGRESSION, 3),
    ("nine-successes", "S" * 9, 0.9, 0.7, DECISION_NO_REGRESSION, 9),
    ("eight-successes", "S" * 8, 0.9, 0.7, DECISION_INCONCLUSIVE, 8),
    ("ffsf", "FFSF", 0.9, 0.7, DECISION_REGRESSION, 4),
    ("alternating-to-regression", "SFSFSFSF", 0.9, 0.7, DECISION_REGRESSION, 8),
    ("alternating-inconclusive", "SFSFSF", 0.9, 0.7, DECISION_INCONCLUSIVE, 6),
    ("five-failures", "F" * 5, 0.9, 0.7, DECISION_REGRESSION, 3),
    ("twelve-successes", "S" * 12, 0.9, 0.7, DECISION_NO_REGRESSION, 9),
    ("fssf", "FSSF", 0.9, 0.7, DECISION_INCONCLUSIVE, 4),
    ("nine-step-alternating", "FSFSFSFSF", 0.9, 0.7, DECISION_REGRESSION, 7),
    ("empty-stream", "", 0.9, 0.7, DECISION_INCONCLUSIVE, 0),
    ("single-success", "S", 0.9, 0.7, DECISION_INCONCLUSIVE, 1),
    ("single-failure", "F", 0.9, 0.7, DECISION_INCONCLUSIVE, 1),
    ("failure-heavy-inconclusive", "FFSSSSF", 0.9, 0.7, DECISION_INCONCLUSIVE, 7),
    ("successes-then-failures", "SSSFFF", 0.9, 0.7, DECISION_INCONCLUSIVE, 6),
    ("successes-then-failures-long", "S" * 9 + "F" * 5, 0.9, 0.7,
     DECISION_NO_REGRESSION, 9),
    ("eight-failures", "F" * 8, 0.9, 0.7, DECISION_REGRESSION, 3),
    ("mixed-inconclusive", "SFSSFSSF", 0.9, 0.7, DECISION_INCONCLUSIVE, 8),
    ("ffsff", "FFSFF", 0.9, 0.7, DECISION_REGRESSION, 4),
    ("sffsffs", "SFFSFFS", 0.9, 0.7, DECISION_REGRESSION, 6),
    ("aiobs-three-failures", "FFF", 0.91, 0.76, DECISION_REGRESSION, 3),
    ("aiobs-thirteen-successes", "S" * 13, 0.91, 0.76,
     DECISION_NO_REGRESSION, 13),
    ("aiobs-twelve-successes", "S" * 12, 0.91, 0.76, DECISION_INCONCLUSIVE, 12),
    ("aiobs-alternating", "SFSFSF", 0.91, 0.76, DECISION_INCONCLUSIVE, 6),
    ("aiobs-ffsff", "FFSFF", 0.91, 0.76, DECISION_REGRESSION, 5),
]

EXPECTED_CAMPAIGN = {
    "verdicts": {VERDICT_BLOCK: 10, VERDICT_REVIEW: 11, VERDICT_PASS: 4},
    "mean_runs_to_decision": 6.14,
    "mean_detection_delay_runs": 460.0,
    "verdict": VERDICT_BLOCK,
}

EXPECTED_SEQUENTIAL = {
    "expected_runs_to_detect": 15.46,
    "fixed_sample_size": 29.20,
    "ratio": 1.89,
}

EXPECTED_AIOBS = {
    "expected_runs_to_detect": 24.12,
    "detection_delay_runs_at_1pct": 2412.0,
}


def _outcomes(stream):
    return [1 if ch == "S" else 0 for ch in stream]


def _expected_verdict(decision):
    if decision == DECISION_REGRESSION:
        return VERDICT_BLOCK
    if decision == DECISION_NO_REGRESSION:
        return VERDICT_PASS
    return VERDICT_REVIEW


def main():
    rows = []
    matched = 0
    for case_id, stream, p0, p1, expected_decision, expected_runs in CASES:
        receipt = score_stream(_outcomes(stream), p0, p1)
        expected_verdict = _expected_verdict(expected_decision)
        match = (
            receipt["decision"] == expected_decision
            and receipt["runs_used"] == expected_runs
            and receipt["verdict"] == expected_verdict
        )
        matched += 1 if match else 0
        rows.append({
            "case_id": case_id,
            "expected_decision": expected_decision,
            "actual_decision": receipt["decision"],
            "expected_verdict": expected_verdict,
            "actual_verdict": receipt["verdict"],
            "expected_runs_used": expected_runs,
            "actual_runs_used": receipt["runs_used"],
            "final_llr": receipt["final_llr"],
            "match": match,
        })

    campaign_a = score_campaign(
        [_outcomes(s) for _, s, p0, p1, _, _ in CASES if p0 == 0.9],
        0.9, 0.7,
    )
    campaign_b = score_campaign(
        [_outcomes(s) for _, s, p0, p1, _, _ in CASES if p0 == 0.91],
        0.91, 0.76,
    )
    verdicts = {
        v: campaign_a["verdicts"][v] + campaign_b["verdicts"][v]
        for v in (VERDICT_BLOCK, VERDICT_REVIEW, VERDICT_PASS)
    }
    decided_runs = []
    blocked_delays = []
    for campaign in (campaign_a, campaign_b):
        for item in campaign["results"]:
            if item["decision"] != DECISION_INCONCLUSIVE:
                decided_runs.append(item["runs_used"])
            if item["verdict"] == VERDICT_BLOCK:
                blocked_delays.append(item["detection_delay_runs"])
    campaign = {
        "verdicts": verdicts,
        "streams": len(CASES),
        "mean_runs_to_decision": round(sum(decided_runs) / len(decided_runs), 2),
        "mean_detection_delay_runs": round(
            sum(blocked_delays) / len(blocked_delays), 1
        ),
        "verdict": VERDICT_BLOCK
        if verdicts[VERDICT_BLOCK]
        else VERDICT_REVIEW
        if verdicts[VERDICT_REVIEW]
        else VERDICT_PASS,
    }

    sequential = {
        "expected_runs_to_detect": round(
            expected_runs_to_detect(0.9, 0.7), 2
        ),
        "fixed_sample_size": round(fixed_sample_size(0.9, 0.7), 2),
        "ratio": round(
            fixed_sample_size(0.9, 0.7) / expected_runs_to_detect(0.9, 0.7), 2
        ),
    }
    aiobs = {
        "expected_runs_to_detect": round(
            expected_runs_to_detect(0.91, 0.76), 2
        ),
        "detection_delay_runs_at_1pct": round(
            detection_delay(expected_runs_to_detect(0.91, 0.76), 0.01), 1
        ),
    }

    campaign_ok = (
        campaign["verdicts"] == EXPECTED_CAMPAIGN["verdicts"]
        and campaign["mean_runs_to_decision"]
        == EXPECTED_CAMPAIGN["mean_runs_to_decision"]
        and campaign["mean_detection_delay_runs"]
        == EXPECTED_CAMPAIGN["mean_detection_delay_runs"]
        and campaign["verdict"] == EXPECTED_CAMPAIGN["verdict"]
    )
    sequential_ok = (
        abs(sequential["expected_runs_to_detect"]
            - EXPECTED_SEQUENTIAL["expected_runs_to_detect"]) <= 0.01
        and abs(sequential["fixed_sample_size"]
                - EXPECTED_SEQUENTIAL["fixed_sample_size"]) <= 0.05
        and abs(sequential["ratio"] - EXPECTED_SEQUENTIAL["ratio"]) <= 0.01
    )
    aiobs_ok = (
        abs(aiobs["expected_runs_to_detect"]
            - EXPECTED_AIOBS["expected_runs_to_detect"]) <= 0.01
        and abs(aiobs["detection_delay_runs_at_1pct"]
                - EXPECTED_AIOBS["detection_delay_runs_at_1pct"]) <= 1.0
    )

    summary = {
        "cases": rows,
        "matched": matched,
        "total": len(CASES),
        "campaign": campaign,
        "campaign_match": campaign_ok,
        "sequential_vs_fixed": sequential,
        "sequential_match": sequential_ok,
        "aiobs_delay": aiobs,
        "aiobs_match": aiobs_ok,
    }
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2)

    print("SilentDrop verify: %d/%d cases matched" % (matched, len(CASES)))
    print("campaign:", json.dumps(campaign, sort_keys=True))
    print("sequential vs fixed:", json.dumps(sequential, sort_keys=True))
    print("aiobs delay:", json.dumps(aiobs, sort_keys=True))
    ok = (
        matched == len(CASES)
        and campaign_ok
        and sequential_ok
        and aiobs_ok
    )
    if not ok:
        print("MISMATCH: see summary.json")
        return 1
    print("25/25 match, campaign block matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
