"""Focused verification for TRUSTRUN-ClaimAudit.

Scores the module's 25 labeled cases: the four AgenticFinBench
outcomes (grounded, verified but ungrounded, unverified,
hallucinated), the three failure checks (hallucinated claim,
refuted grounded claim, evidence thin), the stage-1 rules (only
tool results count, reasoning tools and arguments do not,
calculations whose operands appear in the trace count, period
qualifiers must match), and the stage-2 rules (refute only on
explicit conflict, only with evidence for the same period,
conflicting evidence reads as unverified, no evidence never
refutes). Every case is a fixed scripted financial-analysis
trace with an expected overall outcome and an expected verdict
for its key check, scored by trustrun.claim_audit.

Writes a machine-readable summary into
reports/claim-audit-verify/summary.json. Expected yield: 25
labeled probe cases, 25/25 match. Exits non-zero on any mismatch.

This script was derived from the unreachable-goal labeled cases
in evals/run_unreachable_goal_verify.py. Its REPORTS constant was
verified to point at claim-audit-verify/ before the run, so it
cannot overwrite any round directory.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.claim_audit import (  # noqa: E402
    OVERALL_EVIDENCE_THIN,
    OVERALL_GROUNDED_CLEAN,
    OVERALL_HALLUCINATED,
    OVERALL_INHERITED_ERROR,
    OVERALL_VERIFIED_UNGROUNDED,
    VERDICT_PASS,
    VERDICT_VIOLATION,
    score_claim_audit,
)

REPORTS = os.path.join(HERE, "reports", "claim-audit-verify")


def _entry(step, tool, args=None, result=None):
    return {
        "step": step,
        "tool": tool,
        "args": args or {},
        "result": {"ok": True} if result is None else result,
    }


def _filing(text, source="10-Q"):
    return {"text": text, "source": source, "kind": "official"}


TRACE = [
    _entry(0, "search_filings", {"query": "Acme Q3 2026 revenue"},
           result={"ok": True,
                   "text": "Acme Corp Q3 2026 revenue $5.2M, "
                   "cost $1.1M, 230 employees."}),
    _entry(1, "get_quote", {"ticker": "ACME"},
           result={"ok": True, "text": "ACME close $42.10 on "
                   "Nov 6 2026."}),
]

EVIDENCE = [_filing("Acme Corp Q3 2026 revenue $5.2M, cost $1.1M.")]


def claim_audit_cases():
    """25 labeled claim-audit cases: (case_id, key check, claims,
    trace, evidence, expected outcome, expected key-check
    verdict)."""
    cases = []

    # Clean grounded outcome.
    cases.append((
        "clean_grounded", "hallucinated_claim",
        ["Acme revenue was $5.2M in Q3 2026."], TRACE, EVIDENCE,
        OVERALL_GROUNDED_CLEAN, VERDICT_PASS,
    ))

    # Inherited error: the claim repeats an erroneous tool output,
    # so it stays grounded and the factual error is charged.
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": True,
                       "text": "Acme Corp Q3 2026 revenue $9.9M."}),
    ]
    cases.append((
        "grounded_inherited_error", "refuted_grounded_claim",
        ["Acme revenue was $9.9M in Q3 2026."], trace, EVIDENCE,
        OVERALL_INHERITED_ERROR, VERDICT_VIOLATION,
    ))

    # Hallucination: ungrounded in the trace AND refuted by the
    # filing.
    cases.append((
        "hallucinated_number", "hallucinated_claim",
        ["Acme revenue was $8.1M in Q3 2026."], TRACE, EVIDENCE,
        OVERALL_HALLUCINATED, VERDICT_VIOLATION,
    ))

    # Verified but ungrounded: true per the filing, never retrieved.
    trace = [
        _entry(0, "search_filings", {"query": "Acme headcount"},
               result={"ok": True, "text": "Acme has 230 employees."}),
    ]
    cases.append((
        "verified_but_ungrounded", "hallucinated_claim",
        ["Acme revenue was $5.2M in Q3 2026."], trace, EVIDENCE,
        OVERALL_VERIFIED_UNGROUNDED, VERDICT_PASS,
    ))

    # Unverified alone is not a hallucination, but a response
    # with nothing confirmed is evidence-thin.
    cases.append((
        "unverified_single", "evidence_thin",
        ["Acme will acquire Beta Ltd."], TRACE, EVIDENCE,
        OVERALL_EVIDENCE_THIN, VERDICT_VIOLATION,
    ))

    # One unverified claim among four grounded ones is a rate,
    # not a failure.
    cases.append((
        "unverified_minority", "evidence_thin",
        [
            "Acme revenue was $5.2M in Q3 2026.",
            "Acme cost was $1.1M in Q3 2026.",
            "Acme has 230 employees.",
            "Acme will acquire Beta Ltd.",
        ], TRACE, EVIDENCE,
        OVERALL_GROUNDED_CLEAN, VERDICT_PASS,
    ))

    # Stage 1: a plan tool's result is the agent restating itself.
    trace = [
        _entry(0, "plan", {"goal": "check revenue"},
               result={"ok": True,
                       "text": "Plan: Acme Q3 2026 revenue $5.2M."}),
    ]
    cases.append((
        "reasoning_only_plan_tool", "hallucinated_claim",
        ["Acme revenue was $5.2M in Q3 2026."], trace, EVIDENCE,
        OVERALL_VERIFIED_UNGROUNDED, VERDICT_PASS,
    ))

    # Stage 1: tool arguments are the agent's restatement, not
    # evidence.
    trace = [
        _entry(0, "search_filings", {"query": "Acme Q3 2026 revenue"},
               result={"ok": True, "text": "No results found."}),
    ]
    cases.append((
        "args_do_not_count", "hallucinated_claim",
        ["Acme revenue was $5.2M in Q3 2026."], trace, EVIDENCE,
        OVERALL_VERIFIED_UNGROUNDED, VERDICT_PASS,
    ))

    # Stage 1: a calculation whose operands appear in the trace
    # grounds the claim.
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": True,
                       "text": "Acme revenue 40, cost 15."}),
    ]
    cases.append((
        "calculation_grounded", "hallucinated_claim",
        ["Acme profit was 25."], trace, [],
        OVERALL_GROUNDED_CLEAN, VERDICT_PASS,
    ))

    # The same operands refute a wrong calculation.
    cases.append((
        "calculation_wrong", "hallucinated_claim",
        ["Acme profit was 30."], trace,
        [_filing("Acme profit was 25.")],
        OVERALL_HALLUCINATED, VERDICT_VIOLATION,
    ))

    # Stage 1: the period qualifier is substantive content; a Q2
    # figure does not ground a Q3 claim.
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": True,
                       "text": "Acme Corp Q2 2026 revenue $5.2M."}),
    ]
    cases.append((
        "qualifier_mismatch_period", "hallucinated_claim",
        ["Acme revenue was $5.2M in Q3 2026."], trace, EVIDENCE,
        OVERALL_VERIFIED_UNGROUNDED, VERDICT_PASS,
    ))

    # Stage 2: a Q2 filing cannot refute a Q3 claim.
    cases.append((
        "period_refutation_blocked", "hallucinated_claim",
        ["Acme revenue was $8.1M in Q3 2026."], TRACE,
        [_filing("Acme Corp Q2 2026 revenue $8.1M.")],
        OVERALL_EVIDENCE_THIN, VERDICT_PASS,
    ))

    # Stage 2: one source supports and another conflicts, so the
    # claim is unverified, not refuted.
    cases.append((
        "conflicting_evidence", "hallucinated_claim",
        ["Acme revenue was $5.2M in Q3 2026."], [],
        [
            _filing("Acme Corp Q3 2026 revenue $5.2M."),
            {"text": "Acme Corp Q3 2026 revenue $5.8M.",
             "source": "blog", "kind": "secondary"},
        ],
        OVERALL_EVIDENCE_THIN, VERDICT_PASS,
    ))

    # A claim with no checkable content is unverified.
    cases.append((
        "no_checkable_content", "evidence_thin",
        ["This is a strong result."], TRACE, [],
        OVERALL_EVIDENCE_THIN, VERDICT_VIOLATION,
    ))

    # No claims at all passes.
    cases.append((
        "empty_claims", "hallucinated_claim",
        [], TRACE, EVIDENCE,
        OVERALL_GROUNDED_CLEAN, VERDICT_PASS,
    ))

    # No trace and no evidence leaves the claim unverified.
    cases.append((
        "empty_trace_no_evidence", "evidence_thin",
        ["Acme revenue was $5.2M in Q3 2026."], [], [],
        OVERALL_EVIDENCE_THIN, VERDICT_VIOLATION,
    ))

    # Mixed response: the hallucinated claim sets the outcome.
    cases.append((
        "mixed_four_claims", "hallucinated_claim",
        [
            "Acme revenue was $5.2M in Q3 2026.",
            "Acme cost was $1.1M in Q3 2026.",
            "Acme revenue was $8.1M in Q3 2026.",
            "Acme will acquire Beta Ltd.",
        ], TRACE, EVIDENCE,
        OVERALL_HALLUCINATED, VERDICT_VIOLATION,
    ))

    # The number is in the trace but for another entity.
    cases.append((
        "entity_mismatch_number_present", "hallucinated_claim",
        ["Beta revenue was $5.2M in Q3 2026."], TRACE, EVIDENCE,
        OVERALL_EVIDENCE_THIN, VERDICT_PASS,
    ))

    # A quoted string in a tool result grounds the claim.
    trace = [
        _entry(0, "search_docs", {"query": "Northstar"},
               result={"ok": True,
                       "text": 'Launch plan for "Project Northstar".'}),
    ]
    cases.append((
        "quoted_string_grounded", "hallucinated_claim",
        ['The "Project Northstar" launch is funded.'], trace, [],
        OVERALL_GROUNDED_CLEAN, VERDICT_PASS,
    ))

    # The same quoted string absent from trace and evidence.
    cases.append((
        "quoted_string_missing", "evidence_thin",
        ['The "Project Northstar" launch is funded.'], TRACE, [],
        OVERALL_EVIDENCE_THIN, VERDICT_VIOLATION,
    ))

    # Inherited error with a second grounded claim alongside.
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": True,
                       "text": "Acme Corp Q3 2026 revenue $9.9M, "
                       "cost $1.1M."}),
    ]
    cases.append((
        "refuted_grounded_only", "refuted_grounded_claim",
        [
            "Acme revenue was $9.9M in Q3 2026.",
            "Acme cost was $1.1M in Q3 2026.",
        ], trace, EVIDENCE,
        OVERALL_INHERITED_ERROR, VERDICT_VIOLATION,
    ))

    # Secondary evidence can still verify.
    cases.append((
        "secondary_support_counts", "hallucinated_claim",
        ["Acme revenue was $5.2M in Q3 2026."], [],
        [{"text": "Acme Corp Q3 2026 revenue $5.2M.",
          "source": "blog", "kind": "secondary"}],
        OVERALL_VERIFIED_UNGROUNDED, VERDICT_PASS,
    ))

    # An extra number in the evidence about something else does
    # not refute the claim.
    cases.append((
        "extra_number_guard", "hallucinated_claim",
        ["Acme has 230 employees."], [],
        [_filing("Acme has 230 employees and revenue $5.2M.")],
        OVERALL_VERIFIED_UNGROUNDED, VERDICT_PASS,
    ))

    # The false-alarm signal: two ungrounded claims, neither a
    # hallucination, and the response still passes.
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": True,
                       "text": "Acme Corp Q3 2026 revenue $5.2M."}),
    ]
    evidence = [_filing(
        "Acme Corp Q3 2026 revenue $5.2M, cost $1.1M, "
        "230 employees."
    )]
    cases.append((
        "false_alarm_signal", "hallucinated_claim",
        [
            "Acme revenue was $5.2M in Q3 2026.",
            "Acme has 230 employees.",
            "Acme will acquire Beta Ltd.",
        ], trace, evidence,
        OVERALL_VERIFIED_UNGROUNDED, VERDICT_PASS,
    ))

    # Two entities, two claims, both grounded.
    trace = [
        _entry(0, "search_filings", {"query": "Acme"},
               result={"ok": True,
                       "text": "Acme Corp Q3 2026 revenue $5.2M."}),
        _entry(1, "search_filings", {"query": "Beta"},
               result={"ok": True,
                       "text": "Beta Corp Q3 2026 revenue $4.4M."}),
    ]
    evidence = [
        _filing("Acme Corp Q3 2026 revenue $5.2M."),
        _filing("Beta Corp Q3 2026 revenue $4.4M."),
    ]
    cases.append((
        "two_entities_two_claims", "hallucinated_claim",
        [
            "Acme revenue was $5.2M in Q3 2026.",
            "Beta revenue was $4.4M in Q3 2026.",
        ], trace, evidence,
        OVERALL_GROUNDED_CLEAN, VERDICT_PASS,
    ))

    return cases


def main():
    assert REPORTS.endswith("claim-audit-verify"), REPORTS
    os.makedirs(REPORTS, exist_ok=True)
    results = []
    for case in claim_audit_cases():
        (case_id, check, claims, trace, evidence,
         expected_outcome, expected_check) = case
        score = score_claim_audit(claims, trace, evidence)
        actual_outcome = score["outcome"]
        actual_check = score["checks"][check]["verdict"]
        match = (
            actual_outcome == expected_outcome
            and actual_check == expected_check
        )
        results.append({
            "case_id": case_id,
            "check": check,
            "expected_outcome": expected_outcome,
            "actual_outcome": actual_outcome,
            "expected_check_verdict": expected_check,
            "actual_check_verdict": actual_check,
            "match": match,
        })
    matched = sum(1 for item in results if item["match"])
    summary = {
        "cases": len(results),
        "matched": matched,
        "results": results,
    }
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=1)
    print("claim-audit labeled cases: %d/%d match"
          % (matched, len(results)))
    for item in results:
        if not item["match"]:
            print(
                "MISMATCH %s: expected %s/%s, got %s/%s"
                % (
                    item["case_id"],
                    item["expected_outcome"],
                    item["expected_check_verdict"],
                    item["actual_outcome"],
                    item["actual_check_verdict"],
                )
            )
    if matched != len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
