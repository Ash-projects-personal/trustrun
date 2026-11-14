"""GraderAudit: audit Trustrun's own verdict-extraction path.

Every benchmark and every audit harness ends with a small piece of
code that converts free-form text into a verdict. In Trustrun the
contract judge's callables return a (decision, note) tuple, but when
the judge is a language model its free-form text has to be parsed
into that decision, and no rule for that conversion is specified or
audited anywhere in the harness (verified by grep this run: no
difflib, get_close_matches, or verdict-extraction code exists in
trustrun/ or evals/). The conversion is an unaudited variance
source of exactly the class Hasan and Lwowski measure.

The paper (Hasan and Lwowski, "Same Outputs, Different Scores:
Auditing the Unchecked Graders of Multimodal LLM Benchmarks",
arXiv:2611.03377, Nov 2, 2026, accepted at WACV 2027; abstract
read this run; code at github.com/ahmadhasan2k8/grader-audit):
reproduced the official scorers of eight peer-reviewed multimodal
benchmarks on five open vision-language models and found the
scoring rule alone moves accuracy by up to 22 points on identical
outputs, yet exactly 0 wherever a model emits clean option
letters, so the artifact hides on strong-model leaderboards. A
reasoning model with non-compliance 0.000 still swings 9.5 points
depending on which regex match of its trace the parser keeps. The
benchmark with the highest non-compliance measured has an artifact
of exactly zero, because its scorer abstains instead of guessing.
No standard rule is reliable: snapping a non-answer to its
closest option credits answers never given yet buries correct
ones, abstention discards answers stated in words, and likelihood
scoring follows answer-token priors. The paper's recommendation:
benchmarks should report a non-compliance rate and at least two
rules, not one unexamined grade. Blinded human-plus-LLM-judge
adjudication (Cohen's kappa 0.956) recovers what the model
actually answered; that adjudicated verdict is the ground truth
this module scores against.

Adjacent work is real and named. judge-audit (PyPI) audits LLM
judges for drift (anchor-set EWMA/CUSUM control charts) and
calibration (isotonic, ECE); it does not audit the extraction
rule. judgecal (PyPI) audits judges for behavioral bias with
clustered bootstrap confidence intervals; it does not audit the
extraction rule. judge-drift-sentinel (PyPI) detects judge drift
on a frozen anchor set; it does not audit the extraction rule.
The Hasan and Lwowski code audits benchmark scorers, not an
audit harness's own extraction path.

What is new here is the same audit applied to Trustrun's own
extraction path, with a non-compliance rate reported alongside
every judge score in the trust report. Four extraction rules,
the paper's fallback families adapted to Trustrun's
pass/fail/unverified categories:

- strict (abstain): only a clean verdict counts, the whole text
  is exactly one verdict token, or a JSON object with a "verdict"
  key holding one token. Anything else is non-compliant, never a
  guess. The artifact is exactly zero by construction, but it
  discards answers stated in words.
- first_match: the first PASS/FAIL/UNVERIFIED token anywhere in
  the text wins.
- last_match: the last token wins. Which regex match the parser
  keeps is the paper's 9.5-point swing on a reasoning model.
- snap: the nearest option by difflib similarity with no
  threshold, the MMAD-style no-threshold snap. It always
  manufactures a verdict, never non-compliant, and it credits
  answers never given.

A record is one recorded judge output: the raw free-form text
plus the adjudicated verdict (what a blinded reader says the
judge actually answered: pass, fail, or unverified). Accuracy is
correct extractions over all records; a non-compliant
extraction counts as incorrect, because it produced no verdict.
The swing is the largest accuracy gap between any two rules on
the identical outputs, in percentage points. The verdict bars
are Trustrun's chosen bars: PASS when the swing is at most 2
points, the worst non-compliance rate at most 0.05, and every
rule's accuracy at least 0.90; BLOCK when the swing is at least
10 points, the worst non-compliance rate at least 0.25, or any
rule's accuracy below 0.50; otherwise REVIEW. An empty record
set is REVIEW: there is nothing to score, so it is unscored,
never passed.

Honest limits, read before quoting any number from this module:
the fixture swing (30 points on the 10-record main fixture) is
a property of that small adversarial fixture, which deliberately
includes rambles, not a general claim about Trustrun's judge.
Snap's verdicts on rambles are luck, in both directions: it
happens to match the adjudicated verdict on some rambles and
misses on others, which is the paper's point, that a single
grade conflates capability with luck. The labeled cases in the
verify script are fixed fixture outputs with hand-computed
scores, using fixture texts, not recorded judge outputs from a
live round; the run over a team's real recorded judge outputs
stays future work. The module audits extraction, not the judge:
a clean PASS extraction of a wrong judge answer scores as
extraction-correct, and the judge being wrong is a different
module's problem.
"""

import difflib
import json
import re

VERDICT_BLOCK = "BLOCK"
VERDICT_REVIEW = "REVIEW"
VERDICT_PASS = "PASS"

CATEGORIES = ("pass", "fail", "unverified")

RULE_STRICT = "strict"
RULE_FIRST = "first_match"
RULE_LAST = "last_match"
RULE_SNAP = "snap"

RULES = (RULE_STRICT, RULE_FIRST, RULE_LAST, RULE_SNAP)

_TOKENS = ("PASS", "FAIL", "UNVERIFIED")
_TOKEN_TO_CATEGORY = {
    "PASS": "pass",
    "FAIL": "fail",
    "UNVERIFIED": "unverified",
}
_TOKEN_RE = re.compile(r"\b(PASS|FAIL|UNVERIFIED)\b", re.IGNORECASE)

# Trustrun's chosen bars (not the paper's).
SWING_PASS = 2.0
NON_COMPLIANCE_PASS = 0.05
ACCURACY_PASS = 0.90
SWING_BLOCK = 10.0
NON_COMPLIANCE_BLOCK = 0.25
ACCURACY_BLOCK = 0.50


def _check_text(text):
    if not isinstance(text, str):
        raise ValueError("output text must be a string")


def _check_rule(rule):
    if rule not in RULES:
        raise ValueError("rule must be one of %s" % (RULES,))


def _extract_strict(text):
    """Clean verdict only: the whole text is one token, or JSON.

    Case-insensitive: a judge emitting lowercase "pass" is
    format-compliant in substance. A JSON object counts when its
    "verdict" key holds one token, whatever else the object holds.
    Anything else is non-compliant, never a guess.
    """
    stripped = text.strip()
    upper = stripped.upper()
    if upper in _TOKEN_TO_CATEGORY:
        return _TOKEN_TO_CATEGORY[upper]
    try:
        parsed = json.loads(stripped)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    verdict = parsed.get("verdict")
    if not isinstance(verdict, str):
        return None
    if verdict.strip().upper() in _TOKEN_TO_CATEGORY:
        return _TOKEN_TO_CATEGORY[verdict.strip().upper()]
    return None


def _extract_first(text):
    match = _TOKEN_RE.search(text)
    if match is None:
        return None
    return _TOKEN_TO_CATEGORY[match.group(1).upper()]


def _extract_last(text):
    matches = _TOKEN_RE.findall(text)
    if not matches:
        return None
    return _TOKEN_TO_CATEGORY[matches[-1].upper()]


def _extract_snap(text):
    """Nearest option by difflib similarity, no threshold.

    Always manufactures a verdict, never non-compliant. The
    MMAD-style artifact: on a ramble it credits an answer never
    given. The text is uppercased first, so the rule differs
    from first/last match only in its fallback, not in case
    handling: a judge emitting lowercase "pass" is read as PASS,
    and the artifact is the snapping itself. difflib is
    deterministic, so the manufactured verdict is reproducible
    for a given text.
    """
    close = difflib.get_close_matches(
        text.upper(), list(_TOKENS), n=1, cutoff=0.0
    )
    if not close:
        return "unverified"
    return _TOKEN_TO_CATEGORY[close[0]]


_EXTRACTORS = {
    RULE_STRICT: _extract_strict,
    RULE_FIRST: _extract_first,
    RULE_LAST: _extract_last,
    RULE_SNAP: _extract_snap,
}


def extract(text, rule):
    """Extract one verdict from free-form judge text under a rule.

    Returns "pass", "fail", or "unverified", or None when the
    rule cannot extract a verdict (non-compliant). Only snap
    never returns None.
    """
    _check_text(text)
    _check_rule(rule)
    return _EXTRACTORS[rule](text)


def _check_records(records):
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each record must be a dict")
        if "output" not in record or "truth" not in record:
            raise ValueError("each record needs output and truth")
        _check_text(record["output"])
        if record["truth"] not in CATEGORIES:
            raise ValueError(
                "truth must be one of %s" % (CATEGORIES,)
            )


def _rate(numerator, denominator):
    if denominator == 0:
        return None
    return numerator / denominator


def audit_extraction(records, rules=RULES):
    """Audit extraction rules on identical recorded outputs.

    records: a list of {"output": raw judge text, "truth":
    adjudicated verdict}. rules: the extraction rules to compare,
    default all four. Returns the per-rule accuracy and
    non-compliance rate, the compliant-only accuracy, the swing
    in percentage points between the best and worst rule, the
    worst non-compliance rate, and the worst accuracy. Accuracy
    counts a non-compliant extraction as incorrect, because it
    produced no verdict.
    """
    _check_records(records)
    rules = tuple(rules)
    for rule in rules:
        _check_rule(rule)
    if not rules:
        raise ValueError("at least one rule is needed")
    per_rule = {}
    for rule in rules:
        correct = 0
        compliant_correct = 0
        compliant = 0
        non_compliant = 0
        for record in records:
            got = _EXTRACTORS[rule](record["output"])
            if got is None:
                non_compliant += 1
                continue
            compliant += 1
            if got == record["truth"]:
                correct += 1
                compliant_correct += 1
        per_rule[rule] = {
            "n": len(records),
            "correct": correct,
            "accuracy": _rate(correct, len(records)),
            "compliant": compliant,
            "compliant_accuracy": _rate(compliant_correct, compliant),
            "non_compliant": non_compliant,
            "non_compliance_rate": _rate(non_compliant, len(records)),
        }
    accuracies = [
        per_rule[rule]["accuracy"] for rule in rules
        if per_rule[rule]["accuracy"] is not None
    ]
    non_compliances = [
        per_rule[rule]["non_compliance_rate"] for rule in rules
        if per_rule[rule]["non_compliance_rate"] is not None
    ]
    if accuracies:
        swing = (max(accuracies) - min(accuracies)) * 100.0
        min_accuracy = min(accuracies)
    else:
        swing = None
        min_accuracy = None
    max_non_compliance = max(non_compliances) if non_compliances else None
    return {
        "n": len(records),
        "rules": per_rule,
        "swing_pp": swing,
        "max_non_compliance_rate": max_non_compliance,
        "min_accuracy": min_accuracy,
    }


def score_campaign(records, rules=RULES):
    """Score a set of recorded judge outputs by extraction audit.

    Runs the audit and applies Trustrun's verdict bars: PASS when
    the swing is at most 2 points, the worst non-compliance rate
    at most 0.05, and every rule's accuracy at least 0.90; BLOCK
    when the swing is at least 10 points, the worst
    non-compliance rate at least 0.25, or any rule's accuracy
    below 0.50; otherwise REVIEW. An empty record set is REVIEW.
    """
    audit = audit_extraction(records, rules)
    if audit["n"] == 0:
        verdict = VERDICT_REVIEW
    elif (
        audit["swing_pp"] is not None
        and audit["swing_pp"] >= SWING_BLOCK
    ):
        verdict = VERDICT_BLOCK
    elif (
        audit["max_non_compliance_rate"] is not None
        and audit["max_non_compliance_rate"] >= NON_COMPLIANCE_BLOCK
    ):
        verdict = VERDICT_BLOCK
    elif (
        audit["min_accuracy"] is not None
        and audit["min_accuracy"] < ACCURACY_BLOCK
    ):
        verdict = VERDICT_BLOCK
    elif (
        audit["swing_pp"] is not None
        and audit["swing_pp"] <= SWING_PASS
        and audit["max_non_compliance_rate"] is not None
        and audit["max_non_compliance_rate"] <= NON_COMPLIANCE_PASS
        and audit["min_accuracy"] is not None
        and audit["min_accuracy"] >= ACCURACY_PASS
    ):
        verdict = VERDICT_PASS
    else:
        verdict = VERDICT_REVIEW
    return {
        "n": audit["n"],
        "rules": audit["rules"],
        "swing_pp": audit["swing_pp"],
        "max_non_compliance_rate": audit["max_non_compliance_rate"],
        "min_accuracy": audit["min_accuracy"],
        "verdict": verdict,
    }


def score_card(judge_score, campaign, rule=RULE_STRICT):
    """Report a non-compliance rate alongside a judge score.

    judge_score: the judge's score (accuracy, agreement, or any
    0..1 score) computed under one extraction rule. campaign: a
    score_campaign result. Returns the score with that rule's
    non-compliance rate, the audit swing, and the campaign
    verdict, so a trust report never quotes a judge score without
    saying how much of it the extraction rule manufactured or
    discarded.
    """
    if isinstance(judge_score, bool) or not isinstance(
        judge_score, (int, float)
    ):
        raise ValueError("judge_score must be a number")
    if judge_score < 0.0 or judge_score > 1.0:
        raise ValueError("judge_score must be between 0.0 and 1.0")
    _check_rule(rule)
    if not isinstance(campaign, dict) or "rules" not in campaign:
        raise ValueError("campaign must be a score_campaign result")
    if rule not in campaign["rules"]:
        raise ValueError("rule %s was not audited" % rule)
    return {
        "judge_score": judge_score,
        "extraction_rule": rule,
        "non_compliance_rate": campaign["rules"][rule][
            "non_compliance_rate"
        ],
        "extraction_accuracy": campaign["rules"][rule]["accuracy"],
        "swing_pp": campaign["swing_pp"],
        "verdict": campaign["verdict"],
    }


def format_summary(campaign):
    """One-line human summary of a scored extraction audit."""
    parts = []
    for rule in RULES:
        if rule not in campaign["rules"]:
            continue
        row = campaign["rules"][rule]
        accuracy = row["accuracy"]
        accuracy_text = "%.4f" % accuracy if accuracy is not None else "n/a"
        non_compliance = row["non_compliance_rate"]
        non_text = (
            "%.4f" % non_compliance
            if non_compliance is not None
            else "n/a"
        )
        parts.append(
            "%s %s (non-compliance %s)" % (rule, accuracy_text, non_text)
        )
    swing = campaign["swing_pp"]
    swing_text = "%.2fpp" % swing if swing is not None else "n/a"
    return (
        "GraderAudit: %d outputs, %s, swing %s, verdict %s"
        % (
            campaign["n"],
            ", ".join(parts),
            swing_text,
            campaign["verdict"],
        )
    )
