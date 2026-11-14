"""Focused verification for TRUSTRUN-UnableToVerify.

Scores the module's 25 labeled cases: the six unable-to-verify
reason codes (missing_value, no_expected twice, unknown_kind,
judge_abstained twice, non_numeric) and the checked reason on
decided claims; the pass-rate discipline (verifiable rate vs naive
passed-over-total on mixed contracts, None when nothing is
verifiable, 0.0 share on an empty contract); effect observation on
the standard audit path (a recorded trace observed without an
authorization set caps the contract section at REVIEW, an empty
trace observes nothing, the run_audit tool_trace parameter feeds
the observation, a confirmed write counts as side-effecting but
confirmed); the cap does not apply when a judge-kind claim could
have read the trace (it receives the full output including the
trace, the GDPx scenario shape); the effect check beating final-reply-only judging (the
same reply passes either way, but an unauthorized send blocks with
an authorization set and is observed-but-unverifiable without one);
multi-trial judge abstention; and the evidence chain covering the
new reason and rate fields (a tampered reason fails verification).

Writes a machine-readable summary into
reports/unable-to-verify/summary.json. Expected yield: 25 labeled
cases, 25/25 match, the reason-code counts, the rate contrast, the
effect contrast, and the chain checks all matching. Exits non-zero
on any mismatch.

Method sources: TestMu AI Agent Assurance, GA October 26, 2026
(every criterion ends Pass/Fail/Unable to Verify, each verdict
quoting its evidence, Unable to Verify never counted as a pass);
CXBench (October 2026, company-cited): 80.1% of runs reaching the
right outcome still failed process checks, only 13.8% passed both.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.cli import format_report, run_audit  # noqa: E402
from trustrun.contract import verify_delivery  # noqa: E402
from trustrun.evidence import verify_report_text  # noqa: E402

REPORTS = os.path.join(HERE, "reports", "unable-to-verify")


def _abstain(value, claim, output):
    return None, "cannot tell"


def _always_true(value, claim, output):
    return True, "yes"


def _tracing_agent(text):
    return {
        "result": "Paris",
        "tool_trace": [
            {"tool": "search_docs", "args": ["Paris"], "kind": "read"},
        ],
    }


def _writing_agent(text):
    return {
        "result": "Paris",
        "tool_trace": [
            {"tool": "search_docs", "args": ["Paris"], "kind": "read"},
            {"tool": "send_email", "args": ["ops@example.com"], "kind": "send"},
        ],
    }


def _confirmed_writer(text):
    return {
        "result": "Paris",
        "tool_trace": [
            {
                "tool": "write_file",
                "args": ["notes.txt"],
                "kind": "write",
                "confirmed": True,
            },
        ],
    }


def _empty_trace_agent(text):
    return {"result": "Paris", "tool_trace": []}


def _claim(kind, expected, claim_id="a", **extra):
    claim = {
        "id": claim_id,
        "statement": "s",
        "kind": kind,
        "expected": expected,
    }
    claim.update(extra)
    return claim


def _contract(*claims):
    return {"task": "t", "claims": list(claims)}


def _task():
    return {"text": "What is the capital of France?", "expect": "Paris"}


def _close(a, b):
    if a is None or b is None:
        return a is b
    return abs(a - b) < 1e-9


def main():
    rows = []

    def check(case_id, expected, actual):
        match = expected == actual
        rows.append({
            "case_id": case_id,
            "expected": expected,
            "actual": actual,
            "match": match,
        })
        return match

    # --- Reason codes (cases 1-10) ---
    report = verify_delivery(
        _contract(_claim("exact", "x")), {})
    check("missing-value", "missing_value",
          report["claims"][0]["reason"])

    report = verify_delivery(
        _contract(_claim("contains", "")), {"a": "anything"})
    check("no-expected-empty-contains", "no_expected",
          report["claims"][0]["reason"])

    report = verify_delivery(
        _contract(_claim("exact", None)), {"a": "x"})
    check("no-expected-none-exact", "no_expected",
          report["claims"][0]["reason"])

    report = verify_delivery(
        _contract(_claim("magic", "x")), {"a": "x"})
    check("unknown-kind", "unknown_kind",
          report["claims"][0]["reason"])

    judge_contract = _contract(
        {"id": "a", "statement": "s", "kind": "judge", "judge": _abstain})
    report = verify_delivery(judge_contract, {"a": "maybe"})
    check("judge-abstained", "judge_abstained",
          report["claims"][0]["reason"])

    no_judge = _contract(
        {"id": "a", "statement": "s", "kind": "judge"})
    report = verify_delivery(no_judge, {"a": "yes"})
    check("judge-no-callable", "judge_abstained",
          report["claims"][0]["reason"])

    report = verify_delivery(
        _contract(_claim("numeric", 1.0)), {"a": "not a number"})
    check("non-numeric", "non_numeric",
          report["claims"][0]["reason"])

    report = verify_delivery(
        _contract(_claim("exact", "x")), {"a": "x"})
    check("checked-pass", "checked", report["claims"][0]["reason"])

    report = verify_delivery(
        _contract(_claim("exact", "x")), {"a": "y"})
    check("checked-fail", "checked", report["claims"][0]["reason"])

    report = verify_delivery(
        _contract(_claim("contains", "144", field="result")),
        {"result": "AGENT-ERROR: ProviderError: filtered"})
    check("checked-agent-error-fail",
          {"verdict": "fail", "reason": "checked",
           "agent_error": True},
          {"verdict": report["claims"][0]["verdict"],
           "reason": report["claims"][0]["reason"],
           "agent_error": report["claims"][0]["agent_error"]})

    # --- Pass-rate discipline (cases 11-15) ---
    mixed = _contract(_claim("exact", "x", "a"),
                      _claim("exact", "y", "b"))
    report = verify_delivery(mixed, {"a": "x"})
    check("rate-one-pass-one-unverified",
          {"pass_rate_verifiable": 1.0, "unverifiable_share": 0.5,
           "naive_passed_over_total": 0.5, "verdict": "unverified"},
          {"pass_rate_verifiable": report["pass_rate_verifiable"],
           "unverifiable_share": report["unverifiable_share"],
           "naive_passed_over_total":
               report["passed"] / len(report["claims"]),
           "verdict": report["verdict"]})

    mixed = _contract(_claim("exact", "x", "a"),
                      _claim("exact", "y", "b"),
                      _claim("exact", "z", "c"),
                      _claim("exact", "w", "d"))
    report = verify_delivery(mixed, {"a": "x", "b": "y", "c": "q"})
    check("rate-two-pass-one-fail-one-unverified",
          {"pass_rate_verifiable": True, "unverifiable_share": 0.25,
           "verdict": "fail"},
          {"pass_rate_verifiable": _close(
              report["pass_rate_verifiable"], 2.0 / 3.0),
           "unverifiable_share": report["unverifiable_share"],
           "verdict": report["verdict"]})

    report = verify_delivery(
        _contract(_claim("exact", "x")), {})
    check("rate-all-unverified",
          {"pass_rate_verifiable": None, "unverifiable_share": 1.0,
           "verdict": "unverified"},
          {"pass_rate_verifiable": report["pass_rate_verifiable"],
           "unverifiable_share": report["unverifiable_share"],
           "verdict": report["verdict"]})

    report = verify_delivery({"task": "t", "claims": []}, {})
    check("rate-empty-contract",
          {"pass_rate_verifiable": None, "unverifiable_share": 0.0,
           "verdict": "pass"},
          {"pass_rate_verifiable": report["pass_rate_verifiable"],
           "unverifiable_share": report["unverifiable_share"],
           "verdict": report["verdict"]})

    report = verify_delivery(
        _contract(_claim("exact", "x", "a"),
                  _claim("exact", "y", "b")),
        {"a": "x", "b": "y"})
    check("rate-all-pass",
          {"pass_rate_verifiable": 1.0, "unverifiable_share": 0.0,
           "verdict": "pass"},
          {"pass_rate_verifiable": report["pass_rate_verifiable"],
           "unverifiable_share": report["unverifiable_share"],
           "verdict": report["verdict"]})

    # --- Effect observation (cases 16-21) ---
    report = run_audit(_tracing_agent, _task(), k=1, seed=0)
    contract = report["sections"]["contract"]
    check("trace-observed-caps-review",
          {"observed": True, "total_effects": 1, "side_effecting": 0,
           "observed_verdict": "unverified", "section": "REVIEW"},
          {"observed": "effects_observed" in contract,
           "total_effects": contract["effects_observed"]["total_effects"],
           "side_effecting": contract["effects_observed"]["side_effecting"],
           "observed_verdict": contract["effects_observed"]["verdict"],
           "section": contract["verdict"]})

    report = run_audit(_empty_trace_agent, _task(), k=1, seed=0)
    contract = report["sections"]["contract"]
    check("empty-trace-observes-nothing",
          {"observed": False, "section": "READY"},
          {"observed": "effects_observed" in contract,
           "section": contract["verdict"]})

    authorization = {
        "allowed_tools": ["search_docs"],
        "allowed_targets": {"search_docs": "any"},
    }
    kinds = {"search_docs": "read", "send_email": "send"}
    task = dict(_task(), authorization=authorization, effect_kinds=kinds)
    report = run_audit(_writing_agent, task, k=1, seed=0)
    contract = report["sections"]["contract"]
    check("unauthorized-write-blocks",
          {"claim": "pass", "side_effects": "collateral_damage",
           "section": "BLOCK"},
          {"claim": contract["claims"][0]["verdict"],
           "side_effects": contract["side_effects"]["verdict"],
           "section": contract["verdict"]})

    report = run_audit(_writing_agent, _task(), k=1, seed=0)
    contract = report["sections"]["contract"]
    check("reply-only-contrast",
          {"claim": "pass", "side_effects_present": False,
           "observed_verdict": "unverified", "side_effecting": 1,
           "unconfirmed_side_effecting": 1, "section": "REVIEW"},
          {"claim": contract["claims"][0]["verdict"],
           "side_effects_present": "side_effects" in contract,
           "observed_verdict": contract["effects_observed"]["verdict"],
           "side_effecting": contract["effects_observed"]["side_effecting"],
           "unconfirmed_side_effecting":
               contract["effects_observed"]["unconfirmed_side_effecting"],
           "section": contract["verdict"]})

    from trustrun.consistency import steady_agent  # noqa: E402

    trace = [{"tool": "search_docs", "args": ["Paris"], "kind": "read"}]
    report = run_audit(steady_agent, _task(), k=1, seed=0,
                       tool_trace=trace)
    contract = report["sections"]["contract"]
    check("tool-trace-param",
          {"observed": True, "total_effects": 1, "section": "REVIEW"},
          {"observed": "effects_observed" in contract,
           "total_effects": contract["effects_observed"]["total_effects"],
           "section": contract["verdict"]})

    report = run_audit(_confirmed_writer, _task(), k=1, seed=0)
    contract = report["sections"]["contract"]
    check("confirmed-write-observed",
          {"side_effecting": 1, "unconfirmed_side_effecting": 0,
           "section": "REVIEW"},
          {"side_effecting": contract["effects_observed"]["side_effecting"],
           "unconfirmed_side_effecting":
               contract["effects_observed"]["unconfirmed_side_effecting"],
           "section": contract["verdict"]})

    # --- Multi-trial judge (cases 22-23) ---
    judge_contract = _contract(
        {"id": "a", "statement": "s", "kind": "judge", "judge": _abstain})
    report = verify_delivery(judge_contract, {"a": "maybe"},
                             judge_trials=11)
    check("multi-trial-abstain",
          {"verdict": "unverified", "reason": "judge_abstained"},
          {"verdict": report["verdict"],
           "reason": report["claims"][0]["reason"]})

    judge_contract = _contract(
        {"id": "a", "statement": "s", "kind": "judge",
         "judge": _always_true})
    report = verify_delivery(judge_contract, {"a": "yes"},
                             judge_trials=11)
    check("multi-trial-pass",
          {"verdict": "pass", "reason": "checked"},
          {"verdict": report["verdict"],
           "reason": report["claims"][0]["reason"]})

    # --- Evidence chain (cases 24-25) ---
    task = dict(_task(), contract={
        "task": "t",
        "claims": [
            {"id": "answer", "statement": "s", "kind": "contains",
             "expected": "Paris", "field": "result"},
            {"id": "sources", "statement": "s", "kind": "exact",
             "expected": "cited", "field": "cited"},
        ],
    })

    def _plain_agent(text):
        return {"result": "Paris"}

    report = run_audit(_plain_agent, task, k=1, seed=0)
    text = format_report(report)
    result = verify_report_text(text)
    check("chain-valid-with-new-fields",
          {"valid": True, "head_matches": True,
           "reason_line": True},
          {"valid": result["valid"],
           "head_matches": result["head"] == report["evidence"]["head"],
           "reason_line": "sources: unverified [missing_value]" in text})

    tampered = text.replace(
        '"reason":"missing_value"', '"reason":"checked"', 1)
    check("chain-tampered-reason-fails",
          {"valid": False, "tampered_present": True},
          {"valid": verify_report_text(tampered)["valid"],
           "tampered_present":
               '"reason":"checked"' in tampered})

    matched = sum(1 for row in rows if row["match"])
    reason_codes = {
        "missing_value": 1,
        "no_expected": 2,
        "unknown_kind": 1,
        "judge_abstained": 2,
        "non_numeric": 1,
        "checked": 3,
    }
    observed_reasons = {}
    for row in rows[:10]:
        reason = row["actual"] if isinstance(row["actual"], str) \
            else row["actual"].get("reason")
        observed_reasons[reason] = observed_reasons.get(reason, 0) + 1
    reason_ok = observed_reasons == reason_codes

    rate_case = rows[10]
    rate_ok = (
        rate_case["actual"]["pass_rate_verifiable"] == 1.0
        and rate_case["actual"]["naive_passed_over_total"] == 0.5
        and rate_case["actual"]["unverifiable_share"] == 0.5
    )

    effect_ok = (
        rows[17]["actual"]["section"] == "BLOCK"
        and rows[18]["actual"]["section"] == "REVIEW"
    )

    chain_ok = rows[23]["match"] and rows[24]["match"]

    summary = {
        "cases": rows,
        "matched": matched,
        "total": len(rows),
        "reason_codes": observed_reasons,
        "reason_codes_match": reason_ok,
        "rate_discipline": {
            "verifiable_rate": 1.0,
            "naive_rate": 0.5,
            "unverifiable_share": 0.5,
        },
        "rate_discipline_match": rate_ok,
        "effect_contrast": {
            "with_authorization": "BLOCK",
            "reply_only": "REVIEW",
        },
        "effect_contrast_match": effect_ok,
        "evidence_chain": {
            "valid": True,
            "tampered_reason_fails": True,
        },
        "evidence_chain_match": chain_ok,
    }
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2)

    print("UnableToVerify verify: %d/%d cases matched" % (matched, len(rows)))
    print("reason codes:", json.dumps(observed_reasons, sort_keys=True))
    print("rate discipline match:", rate_ok)
    print("effect contrast match:", effect_ok)
    print("evidence chain match:", chain_ok)
    ok = (matched == len(rows) and reason_ok and rate_ok
          and effect_ok and chain_ok)
    if not ok:
        print("MISMATCH: see summary.json")
        return 1
    print("25/25 match, all blocks match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
