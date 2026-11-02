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

Method source: the Pact verifier battery, which judges delivered work
against negotiated deal terms claim by claim over real market cases
(experiments/real_cases.py in the Pact project). This module generalizes
that method to any agent task.
"""

_MISSING = object()


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
    result = func(value, claim, output)
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


def verify_delivery(contract, output):
    """Judge delivered output against a task contract.

    contract: dict with "task" and "claims" (see module docstring).
    output: dict of recorded values keyed by claim id or claim "field".

    Returns a dict with the per claim verdicts plus evidence, the counts,
    and the overall verdict.
    """
    if not isinstance(contract, dict) or not isinstance(output, dict):
        raise TypeError("contract and output must both be dicts")
    claims = contract.get("claims", []) or []
    judged = []
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
            })
            continue
        kind = claim.get("kind", "exact")
        checker = _CHECKERS.get(kind)
        if checker is None:
            judged.append({
                "id": claim_id,
                "statement": claim.get("statement", ""),
                "verdict": "unverified",
                "evidence": "unknown check kind %r" % kind,
            })
            continue
        decision, evidence = checker(claim, value, output)
        if decision is True:
            verdict = "pass"
        elif decision is False:
            verdict = "fail"
        else:
            verdict = "unverified"
        judged.append({
            "id": claim_id,
            "statement": claim.get("statement", ""),
            "verdict": verdict,
            "evidence": evidence,
        })
    passed = sum(1 for j in judged if j["verdict"] == "pass")
    failed = sum(1 for j in judged if j["verdict"] == "fail")
    unverified = sum(1 for j in judged if j["verdict"] == "unverified")
    if failed:
        overall = "fail"
    elif unverified:
        overall = "unverified"
    else:
        overall = "pass"
    return {
        "task": contract.get("task", ""),
        "claims": judged,
        "passed": passed,
        "failed": failed,
        "unverified": unverified,
        "verdict": overall,
    }
