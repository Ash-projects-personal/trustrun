"""Contract module: did the agent do what was agreed.

Every run gets a machine checkable contract of what the agent was supposed
to do. A verifier judges the delivered output against the contract, claim
by claim, with evidence attached to every verdict.

A contract is a dict with a "task" label and a "claims" list. Each claim
is a dict:

    id:        short claim id, also the default output field it checks
    statement: the claim in plain words
    kind:      one of "exact", "contains", "numeric", "judge"
    expected:  the value the output must match (exact, contains, numeric)
    tolerance: allowed absolute difference for "numeric" (default 0)
    field:     output key to check (defaults to the claim id)
    judge:     for kind "judge", a callable taking (value, claim, output)
               and returning (True, evidence), (False, evidence), or
               (None, evidence) when it cannot decide

Verdicts per claim: "pass", "fail", "unverified". A missing value, a None
value, or a check that cannot be evaluated is "unverified", never a pass.
The overall verdict is "fail" if any claim fails, "unverified" if nothing
fails but something is unverified, else "pass".

Each judged claim also carries an "agent_error" flag. Agent wrappers
report a hard failure with an "AGENT-ERROR" prefix instead of an answer.
A claim that fails because the agent errored is not the same as a claim
that fails because the agent gave a wrong answer, so the flag keeps the
distinction visible. The flag never changes the verdict taxonomy: an
errored claim still fails when it was supposed to contain an answer.

Method source: the Pact verifier battery, which judges delivered work
against negotiated deal terms claim by claim over real market cases
(experiments/real_cases.py in the Pact project). This module generalizes
that method to any agent task.

Judge reliability (TRUSTRUN-JudgeRedesign): kind "judge" claims are
single-trial verdicts by default, which the 2026 judge-reliability
literature shows flip often enough to matter. Pass judge_trials=11 or
more to verify_delivery to judge those claims by repeated trials with
position randomization and majority vote, with Fleiss' kappa reported
across the contract's judge-kind claims. See trustrun/contract/judge.py
for the method and its sources. Rule-kind claims (exact, contains,
numeric) are binary-verifiable atoms and are judged once, deterministically.

Side-effect oracle (TRUSTRUN-SABenchAdopt, TRUSTRUN-CarefulAdopt):
passing effects and authorization to verify_delivery scores the
recorded tool-call trace judge-free against the task's authorization
set (see trustrun/contract/side_effects.py). SABench showed 12.8% of
goal-satisfied runs still produce unauthorized writes, so a delivery
that meets its claims while doing unauthorized damage fails the
contract. The oracle is a closed world: an effect the authorization
set does not list is unauthorized, and an effect with no recorded kind
is unverified, never authorized.
"""

import random

from trustrun.contract.judge import (
    MIN_TRIALS,
    call_judge,
    binary_coverage,
    fleiss_kappa,
    judge_claim_trials,
)
from trustrun.contract.side_effects import score_side_effects

_MISSING = object()

# Agent wrappers report a hard failure with this prefix instead of an
# answer (for example "AGENT-ERROR: ProviderError: content filtered").
_AGENT_ERROR_MARKER = "AGENT-ERROR"


def _is_agent_error(value):
    """True when the recorded value is an agent failure, not an answer."""
    return isinstance(value, str) and value.startswith(_AGENT_ERROR_MARKER)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _judge_exact(claim, value):
    expected = claim.get("expected", _MISSING)
    if expected is _MISSING:
        return None, "claim has no expected value, cannot judge"
    ok = value == expected
    return ok, "expected %r, recorded %r" % (expected, value)


def _judge_contains(claim, value):
    expected = claim.get("expected", _MISSING)
    if expected is _MISSING:
        return None, "claim has no expected value, cannot judge"
    ok = str(expected) in str(value)
    return ok, "expected %r inside recorded %r" % (expected, value)


def _judge_numeric(claim, value):
    expected = claim.get("expected", _MISSING)
    if expected is _MISSING:
        return None, "claim has no expected value, cannot judge"
    if not _is_number(value) or not _is_number(expected):
        return None, "numeric check needs numbers, got %r vs %r" % (value, expected)
    tolerance = claim.get("tolerance", 0)
    ok = abs(value - expected) <= tolerance
    return ok, "expected %r within %r, recorded %r" % (expected, tolerance, value)


def _judge_judge(claim, value, output):
    func = claim.get("judge")
    if not callable(func):
        return None, "judge claim needs a callable judge, cannot judge"
    # A four-argument judge takes a context (trial, position, tools);
    # a single-trial call runs as trial 0 of 1 at position 0.
    context = {
        "trial": 0,
        "trials": 1,
        "position": 0,
        "judge_index": 0,
        "judge_name": getattr(func, "__name__", "judge"),
        "tools": {},
    }
    result = call_judge(func, value, claim, output, context)
    if not isinstance(result, tuple) or len(result) != 2:
        return None, "judge returned a bad shape, cannot judge"
    decision, evidence = result
    if decision is True:
        return True, str(evidence)
    if decision is False:
        return False, str(evidence)
    return None, str(evidence)


_CHECKERS = {
    "exact": lambda claim, value, output: _judge_exact(claim, value),
    "contains": lambda claim, value, output: _judge_contains(claim, value),
    "numeric": lambda claim, value, output: _judge_numeric(claim, value),
    "judge": _judge_judge,
}


def verify_delivery(contract, output, *, judge_trials=1, judges=None,
                    tools=None, seed=0, effects=None, authorization=None,
                    goal_satisfied=None, trap_family=None,
                    reference_effects=None):
    """Judge delivered output against a task contract.

    contract: dict with "task" and "claims" (see module docstring).
    output: dict of recorded values keyed by claim id or claim "field".

    judge_trials: rounds of judging per judge-kind claim. 1 (default)
    is the historical single-trial behavior, unchanged. 11 or more
    runs the JudgeRedesign path: repeated trials with position
    randomization, majority vote, and Fleiss' kappa across the
    contract's judge-kind claims. judges: an optional panel of judge
    callables overriding each claim's own judge. tools: an optional
    mapping of tools handed to judges in their context. seed: fixes
    the position draws so a run is reproducible.

    effects, authorization: optional side-effect oracle inputs (see
    trustrun/contract/side_effects.py). When either is given, the
    report gains a "side_effects" section scored judge-free against
    the per-task authorization set. Task success is not enough: when
    the oracle finds collateral damage, or any unauthorized call
    including a forbidden-target read, the overall verdict is "fail",
    even when every claim passes. When neither is given the report
    has no side_effects key and the behavior is the historical one.
    goal_satisfied defaults to whether every claim passed; pass it
    explicitly when the goal is judged elsewhere. trap_family and
    reference_effects are passed through to the oracle (the SABench
    trap family the task exercises, and the minimal effect list the
    surplus-step count is measured against).

    Returns a dict with the per claim verdicts plus evidence, the counts,
    and the overall verdict. In multi-trial mode each judge-kind claim
    also carries its trial record, and the report gains a
    "judge_reliability" summary (trials, binary coverage, mean flip
    rate, kappa, per-family agreement). Rule-kind claims are
    deterministic: flip rate 0.0, one trial.
    """
    if not isinstance(contract, dict) or not isinstance(output, dict):
        raise TypeError("contract and output must both be dicts")
    if judge_trials < 1:
        raise ValueError("judge_trials must be at least 1")
    multi_trial = judge_trials > 1
    claims = contract.get("claims", []) or []
    rng = random.Random(seed) if multi_trial else None
    judged = []
    judge_vote_lists = []
    for claim in claims:
        claim_id = claim.get("id", "?")
        field = claim.get("field", claim_id)
        value = output.get(field, _MISSING)
        if value is _MISSING or value is None:
            judged.append({
                "id": claim_id,
                "statement": claim.get("statement", ""),
                "verdict": "unverified",
                "evidence": "no value recorded for %r" % field,
                "agent_error": False,
            })
            continue
        kind = claim.get("kind", "exact")
        if multi_trial and kind == "judge":
            record = judge_claim_trials(
                claim, value, output, trials=judge_trials,
                judges=judges, tools=tools, rng=rng)
            if record["votes"]:
                judge_vote_lists.append(record["votes"])
            judged.append({
                "id": claim_id,
                "statement": claim.get("statement", ""),
                "verdict": record["verdict"],
                "evidence": "; ".join(record["evidence"]),
                "agent_error": _is_agent_error(value),
                "trials": record["trials"],
                "n_votes": len(record["votes"]),
                "flip_rate": record["flip_rate"],
                "majority_share": record["majority_share"],
                "kappa": None,  # set below, across all judge-kind claims
                "per_judge": record["per_judge"],
                "family_agreement": record["family_agreement"],
            })
            continue
        checker = _CHECKERS.get(kind)
        if checker is None:
            judged.append({
                "id": claim_id,
                "statement": claim.get("statement", ""),
                "verdict": "unverified",
                "evidence": "unknown check kind %r" % kind,
                "agent_error": _is_agent_error(value),
            })
            continue
        decision, evidence = checker(claim, value, output)
        if decision is True:
            verdict = "pass"
        elif decision is False:
            verdict = "fail"
        else:
            verdict = "unverified"
        entry = {
            "id": claim_id,
            "statement": claim.get("statement", ""),
            "verdict": verdict,
            "evidence": evidence,
            "agent_error": _is_agent_error(value),
        }
        if multi_trial:
            entry["trials"] = 1
            entry["flip_rate"] = 0.0
            entry["majority_share"] = 1.0
            entry["deterministic"] = True
        judged.append(entry)
    passed = sum(1 for j in judged if j["verdict"] == "pass")
    failed = sum(1 for j in judged if j["verdict"] == "fail")
    unverified = sum(1 for j in judged if j["verdict"] == "unverified")
    if failed:
        overall = "fail"
    elif unverified:
        overall = "unverified"
    else:
        overall = "pass"
    report = {
        "task": contract.get("task", ""),
        "claims": judged,
        "passed": passed,
        "failed": failed,
        "unverified": unverified,
        "verdict": overall,
    }
    if effects is not None or authorization is not None:
        if authorization is None:
            raise ValueError(
                "side-effect scoring needs an authorization set")
        if goal_satisfied is None:
            goal_satisfied = overall == "pass"
        side = score_side_effects(
            effects, authorization, goal_satisfied=goal_satisfied,
            trap_family=trap_family,
            reference_effects=reference_effects)
        report["side_effects"] = side
        # Task success is not enough (SABench): a delivery that met
        # its claims while doing unauthorized damage fails, and so does
        # one that touched a forbidden target even without a side
        # effect.
        if side["collateral_damage"] or side["verdict"] == "unauthorized":
            report["verdict"] = "fail"
        elif side["verdict"] == "unverified" and overall == "pass":
            report["verdict"] = "unverified"
    if multi_trial:
        # Kappa needs every subject rated by the same number of raters;
        # mixed panel sizes across claims cannot support one, so it
        # reports None rather than a wrong number.
        same_length = len({len(v) for v in judge_vote_lists}) <= 1
        kappa = (fleiss_kappa(judge_vote_lists)
                 if judge_vote_lists and same_length else None)
        for entry in judged:
            if "kappa" in entry:
                entry["kappa"] = kappa
        trial_entries = [j for j in judged
                         if j.get("n_votes", 0) > 0 and "flip_rate" in j]
        flip_rates = [j["flip_rate"] for j in trial_entries]
        family = [j["family_agreement"] for j in trial_entries
                  if j.get("family_agreement") is not None]
        report["judge_reliability"] = {
            "trials": judge_trials,
            "min_trials": MIN_TRIALS,
            "binary_coverage": binary_coverage(contract),
            "judge_claims": len(judge_vote_lists),
            "mean_flip_rate": (
                sum(flip_rates) / len(flip_rates) if flip_rates else 0.0),
            "kappa": kappa,
            "family_agreement": (
                sum(family) / len(family) if family else None),
            "positions_randomized": True,
        }
    return report
