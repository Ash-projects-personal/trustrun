"""Focused verification for TRUSTRUN-GraderAudit.

Scores the module's 25 labeled cases: single-output extraction
(the clean tokens, JSON verdicts, lowercase, rambles, answers
stated in words, the empty string, the mixed-trace first/last
split, the snap manufacture, the word-boundary case), and
campaign verdicts (the 10-output BLOCK fixture, the clean PASS
fixture, the 20-output REVIEW fixture, the all-ramble BLOCK on
non-compliance, the empty campaign, the two-rule audit the paper
recommends, the score card, and the one-line summaries). Every
case is a fixed fixture output with a hand-computed score, scored
by trustrun.grader_audit. The campaign block checks the aggregate
numbers by hand: 10 outputs, strict accuracy 0.4000
(non-compliance 0.6000), first_match 0.6000 (0.3000), last_match
0.7000 (0.3000), snap 0.6000 (0.0000), swing 30.00pp, verdict
BLOCK. The 30-point swing is a property of this small adversarial
fixture, which deliberately includes rambles, not a general claim
about Trustrun's judge.

Writes a machine-readable summary into
reports/grader-audit-verify/summary.json. Expected yield: 25
labeled cases, 25/25 match, campaign block matches.
Exits non-zero on any mismatch.

The cases are fixed fixture outputs with hand-computed scores,
using fixture texts, not recorded judge outputs from a live round.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.grader_audit import (  # noqa: E402
    RULE_STRICT,
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_REVIEW,
    audit_extraction,
    extract,
    format_summary,
    score_campaign,
    score_card,
)

REPORTS = os.path.join(HERE, "reports", "grader-audit-verify")

MIXED = (
    "PASS at first glance, but on reflection the claim "
    "does not hold. FAIL"
)


def _record(output, truth):
    return {"output": output, "truth": truth}


MAIN = [
    _record("PASS", "pass"),
    _record("FAIL", "fail"),
    _record("UNVERIFIED", "unverified"),
    _record('{"verdict": "PASS"}', "pass"),
    _record("The claim holds. PASS", "pass"),
    _record("I think this fails. The answer is FAIL", "fail"),
    _record(MIXED, "fail"),
    _record("The object is a nail.", "unverified"),
    _record("The answer is no, the claim fails.", "fail"),
    _record("", "unverified"),
]

CLEAN = [
    _record("PASS", "pass"),
    _record("FAIL", "fail"),
    _record("UNVERIFIED", "unverified"),
    _record('{"verdict": "PASS"}', "pass"),
    _record("pass", "pass"),
    _record("FAIL", "fail"),
    _record("UNVERIFIED", "unverified"),
    _record('{"verdict": "PASS"}', "pass"),
]

REVIEW_RECORDS = (
    [_record("PASS", "pass")] * 5
    + [_record("FAIL", "fail")] * 5
    + [_record("UNVERIFIED", "unverified")] * 5
    + [_record('{"verdict": "PASS"}', "pass")] * 4
    + [_record("Not sure.", "unverified")]
)

RAMBLES = [
    _record("The object is a nail.", "unverified"),
    _record("The answer is no, the claim fails.", "fail"),
    _record("The claim holds, mostly.", "pass"),
    _record("Not sure.", "unverified"),
    _record("It works.", "pass"),
]

# (case_id, kind, payload, expected)
CASES = [
    ("strict-clean-pass", "extract", ("PASS", "strict"), "pass"),
    ("strict-clean-fail", "extract", ("FAIL", "strict"), "fail"),
    ("strict-clean-unverified", "extract",
     ("UNVERIFIED", "strict"), "unverified"),
    ("strict-json", "extract",
     ('{"verdict": "PASS"}', "strict"), "pass"),
    ("strict-ramble", "extract",
     ("The claim holds. PASS", "strict"), None),
    ("strict-words-answer", "extract",
     ("The answer is no, the claim fails.", "strict"), None),
    ("strict-empty", "extract", ("", "strict"), None),
    ("first-multi-token", "extract", (MIXED, "first_match"), "pass"),
    ("last-multi-token", "extract", (MIXED, "last_match"), "fail"),
    ("snap-ramble", "extract",
     ("The object is a nail.", "snap"), "fail"),
    ("snap-empty", "extract", ("", "snap"), "unverified"),
    ("first-bypass", "extract",
     ("bypass the check", "first_match"), None),
    ("strict-lowercase", "extract", ("pass", "strict"), "pass"),
    ("strict-bad-json-verdict", "extract",
     ('{"verdict": "maybe"}', "strict"), None),
    ("campaign-block", "campaign", MAIN,
     {"verdict": VERDICT_BLOCK, "n": 10, "swing_pp": 30.0,
      "max_non_compliance_rate": 0.6, "min_accuracy": 0.4,
      "strict_accuracy": 0.4, "strict_non_compliance": 0.6,
      "first_match_accuracy": 0.6, "first_match_non_compliance": 0.3,
      "last_match_accuracy": 0.7, "last_match_non_compliance": 0.3,
      "snap_accuracy": 0.6, "snap_non_compliance": 0.0}),
    ("campaign-pass", "campaign", CLEAN,
     {"verdict": VERDICT_PASS, "n": 8, "swing_pp": 0.0,
      "max_non_compliance_rate": 0.0, "min_accuracy": 1.0}),
    ("campaign-review", "campaign", REVIEW_RECORDS,
     {"verdict": VERDICT_REVIEW, "n": 20, "swing_pp": 5.0,
      "max_non_compliance_rate": 0.05, "min_accuracy": 0.95}),
    ("campaign-block-noncompliance", "campaign", RAMBLES,
     {"verdict": VERDICT_BLOCK, "n": 5,
      "max_non_compliance_rate": 1.0}),
    ("campaign-empty", "campaign", [],
     {"verdict": VERDICT_REVIEW, "n": 0, "swing_pp": None,
      "max_non_compliance_rate": None, "min_accuracy": None}),
    ("audit-two-rules", "audit", (MAIN, ("strict", "first_match")),
     {"swing_pp": 20.0, "rules": ["first_match", "strict"]}),
    ("score-card", "card", (0.85, MAIN),
     {"judge_score": 0.85, "extraction_rule": RULE_STRICT,
      "non_compliance_rate": 0.6, "extraction_accuracy": 0.4,
      "swing_pp": 30.0, "verdict": VERDICT_BLOCK}),
    ("format-summary", "summary", MAIN,
     "GraderAudit: 10 outputs, strict 0.4000 (non-compliance 0.6000), "
     "first_match 0.6000 (non-compliance 0.3000), "
     "last_match 0.7000 (non-compliance 0.3000), "
     "snap 0.6000 (non-compliance 0.0000), "
     "swing 30.00pp, verdict BLOCK"),
    ("format-summary-empty", "summary", [],
     "GraderAudit: 0 outputs, strict n/a (non-compliance n/a), "
     "first_match n/a (non-compliance n/a), "
     "last_match n/a (non-compliance n/a), "
     "snap n/a (non-compliance n/a), "
     "swing n/a, verdict REVIEW"),
    ("extract-error-bad-rule", "extract_error", None, "ValueError"),
    ("campaign-error-bad-record", "campaign_error", None, "ValueError"),
]

EXPECTED_CAMPAIGN = {
    "n": 10,
    "swing_pp": 30.0,
    "max_non_compliance_rate": 0.6,
    "min_accuracy": 0.4,
    "strict_accuracy": 0.4,
    "strict_non_compliance": 0.6,
    "first_match_accuracy": 0.6,
    "first_match_non_compliance": 0.3,
    "last_match_accuracy": 0.7,
    "last_match_non_compliance": 0.3,
    "snap_accuracy": 0.6,
    "snap_non_compliance": 0.0,
    "verdict": VERDICT_BLOCK,
}


def _round(value):
    return None if value is None else round(value, 4)


def _campaign_dict(campaign):
    got = {
        "verdict": campaign["verdict"],
        "n": campaign["n"],
        "swing_pp": _round(campaign["swing_pp"]),
        "max_non_compliance_rate": _round(
            campaign["max_non_compliance_rate"]
        ),
        "min_accuracy": _round(campaign["min_accuracy"]),
    }
    for rule, row in campaign["rules"].items():
        got[rule + "_accuracy"] = _round(row["accuracy"])
        got[rule + "_non_compliance"] = _round(
            row["non_compliance_rate"]
        )
    return got


def _check(kind, payload, expected):
    if kind == "extract":
        text, rule = payload
        got = extract(text, rule)
        return got == expected, got
    if kind == "campaign":
        campaign = score_campaign(payload)
        got = _campaign_dict(campaign)
        got = {key: got[key] for key in expected}
        return got == expected, got
    if kind == "audit":
        records, rules = payload
        audit = audit_extraction(records, rules=rules)
        got = {
            "swing_pp": _round(audit["swing_pp"]),
            "rules": sorted(audit["rules"]),
        }
        return got == expected, got
    if kind == "card":
        judge_score, records = payload
        campaign = score_campaign(records)
        got = score_card(judge_score, campaign, rule=RULE_STRICT)
        got = {
            "judge_score": got["judge_score"],
            "extraction_rule": got["extraction_rule"],
            "non_compliance_rate": _round(
                got["non_compliance_rate"]
            ),
            "extraction_accuracy": _round(
                got["extraction_accuracy"]
            ),
            "swing_pp": _round(got["swing_pp"]),
            "verdict": got["verdict"],
        }
        return got == expected, got
    if kind == "summary":
        campaign = score_campaign(payload)
        got = format_summary(campaign)
        return got == expected, got
    if kind == "extract_error":
        try:
            extract("PASS", "random")
        except ValueError:
            return expected == "ValueError", "ValueError"
        return False, "no error"
    if kind == "campaign_error":
        try:
            score_campaign([{"output": "PASS"}])
        except ValueError:
            return expected == "ValueError", "ValueError"
        return False, "no error"
    raise ValueError("unknown case kind %s" % kind)


def main():
    rows = []
    matched = 0
    for case_id, kind, payload, expected in CASES:
        match, got = _check(kind, payload, expected)
        matched += 1 if match else 0
        rows.append({
            "case_id": case_id,
            "kind": kind,
            "expected": expected,
            "actual": got,
            "match": match,
        })

    campaign = score_campaign(MAIN)
    campaign_block = _campaign_dict(campaign)
    campaign_ok = campaign_block == EXPECTED_CAMPAIGN

    summary = {
        "cases": rows,
        "matched": matched,
        "total": len(CASES),
        "campaign": campaign_block,
        "campaign_match": campaign_ok,
    }
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2)

    print("GraderAudit verify: %d/%d cases matched"
          % (matched, len(CASES)))
    print("campaign:", json.dumps(campaign_block, sort_keys=True))
    ok = matched == len(CASES) and campaign_ok
    if not ok:
        print("MISMATCH: see summary.json")
        return 1
    print("25/25 match, campaign block matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
