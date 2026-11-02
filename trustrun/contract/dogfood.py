"""Dogfood: run Pact's real market cases through Trustrun's contract module.

Not part of the package API. Reads the recorded settlements from
experiments/real_cases_results.json and the attack results from
experiments/adversarial_results.json in the Pact project, and judges each
record against a contract built from the deal's own terms.

Nothing here is invented. The 18 settlement cases and the 13 attack cases
are recorded runs. The deal type labels (honest or cheat) come from the
case definitions in experiments/real_cases.py. The limit case is Pact's
own documented verifier limit: a translation cheat that counting checks
cannot catch.

Run with: python3 trustrun/contract/dogfood.py
"""

import json
import sys
from pathlib import Path

from trustrun.contract import verify_delivery

PACT_EXPERIMENTS = Path.home() / "workspace" / "projects" / "pact-agentic-commerce" / "experiments"

# Deal type per case index in real_cases_results.json, from the case
# definitions in experiments/real_cases.py: cases 1, 2, and 17 are the
# documented cheats ("under delivered then abandoned", "recycled copy
# cheat", "cheat labeler"); the rest are honest sellers, including case 6
# whose weak first draft was rescued on the contractual revision round.
CHEAT_CASES = {1, 2, 17}


def _parse_checks(checks):
    passed, _, total = checks.partition("/")
    return int(passed), int(total)


def _settlement_judge(value, claim, output):
    passed, total = _parse_checks(str(value))
    if passed == total:
        ok = (output.get("outcome") == "released"
              and output.get("payment_status") == "released"
              and output.get("bond_status") == "returned")
        return ok, "checks %s, settlement %s/%s/%s" % (
            value, output.get("outcome"),
            output.get("payment_status"), output.get("bond_status"))
    ok = (output.get("outcome") == "refunded"
          and output.get("payment_status") == "refunded"
          and output.get("bond_status") == "slashed")
    return ok, "checks %s, settlement %s/%s/%s" % (
        value, output.get("outcome"),
        output.get("payment_status"), output.get("bond_status"))


def _bond_ratio_judge(value, claim, output):
    price = output.get("negotiated_price")
    if not isinstance(price, (int, float)) or not price:
        return None, "no usable price to ratio against"
    ratio = value / price
    ok = 0.15 <= ratio <= 0.30
    return ok, "bond %.2f on price %.2f is %.1f percent" % (value, price, ratio * 100)


def contract_for_case(case, deal_type):
    settled = "released" if deal_type == "honest" else "refunded"
    bond = "returned" if deal_type == "honest" else "slashed"
    return {
        "task": "Pact deal settlement: %s" % case["case"],
        "claims": [
            {"id": "outcome", "statement": "Deal outcome matches the deal type",
             "kind": "exact", "expected": settled},
            {"id": "payment_status", "statement": "Payment status matches the deal type",
             "kind": "exact", "expected": settled},
            {"id": "bond_status", "statement": "Bond status matches the deal type",
             "kind": "exact", "expected": bond},
            {"id": "bond", "statement": "Bond sits between 15 and 30 percent of price",
             "kind": "judge", "judge": _bond_ratio_judge},
            {"id": "checks", "statement": "Settlement follows the check results",
             "kind": "judge", "judge": _settlement_judge},
        ],
    }


def contract_for_seller_attack(attack):
    return {
        "task": "Seller attack: %s" % attack["attack"],
        "claims": [
            {"id": "passed_all_checks", "statement": "The attack did not pass all checks",
             "kind": "exact", "expected": False},
            {"id": "failed_checks", "statement": "The caught check is named in the record",
             "kind": "judge",
             "judge": lambda v, c, o: (
                 (True, "caught: %s" % ", ".join(v))
                 if isinstance(v, list) and v
                 else (False, "no failed check named"))},
        ],
    }


def contract_for_api_attack(attack):
    return {
        "task": "API attack: %s" % attack["attack"],
        "claims": [
            {"id": "blocked", "statement": "The attack was blocked",
             "kind": "exact", "expected": True},
            {"id": "detail", "statement": "The block is described in the record",
             "kind": "judge",
             "judge": lambda v, c, o: (
                 (True, "detail recorded")
                 if isinstance(v, str) and v.strip()
                 else (False, "no detail recorded"))},
        ],
    }


def contract_for_limit_case(limit):
    return {
        "task": "Translation limit case: %s" % limit["case"],
        "claims": [
            {"id": "machine_sample_caught",
             "statement": "The word for word machine style sample fails at least one check",
             "kind": "exact", "expected": False,
             "field": "machine_passed_all"},
        ],
    }


def data_available():
    """True when the Pact experiment data files exist on this machine."""
    return ((PACT_EXPERIMENTS / "real_cases_results.json").is_file()
            and (PACT_EXPERIMENTS / "adversarial_results.json").is_file())


def load_records():
    if not data_available():
        raise FileNotFoundError(
            "Pact experiment data not found at %s. "
            "Dogfood tests need a local checkout of the Pact project." % PACT_EXPERIMENTS)
    results = json.loads((PACT_EXPERIMENTS / "real_cases_results.json").read_text())
    attacks = json.loads((PACT_EXPERIMENTS / "adversarial_results.json").read_text())
    return results, attacks


def run_dogfood(results=None, attacks=None):
    """Judge every record. Returns (reports, totals)."""
    if results is None or attacks is None:
        results, attacks = load_records()
    reports = []
    for i, case in enumerate(results["cases"]):
        deal_type = "cheat" if i in CHEAT_CASES else "honest"
        report = verify_delivery(contract_for_case(case, deal_type), case)
        reports.append((case["case"], report))
    for attack in attacks["seller_attacks"]:
        reports.append((attack["attack"], verify_delivery(contract_for_seller_attack(attack), attack)))
    for attack in attacks["api_attacks"]:
        reports.append((attack["attack"], verify_delivery(contract_for_api_attack(attack), attack)))
    limit = results["limit_case"]
    machine_passed = limit["results"]["word for word machine style sample"]["passed_all_checks"]
    limit_report = verify_delivery(
        contract_for_limit_case(limit), {"machine_passed_all": machine_passed})
    reports.append((limit["case"] + " (limit case)", limit_report))
    totals = {"pass": 0, "fail": 0, "unverified": 0, "claims_pass": 0,
              "claims_fail": 0, "claims_unverified": 0}
    for _, report in reports:
        totals[report["verdict"]] += 1
        totals["claims_pass"] += report["passed"]
        totals["claims_fail"] += report["failed"]
        totals["claims_unverified"] += report["unverified"]
    return reports, totals


def main():
    reports, totals = run_dogfood()
    print("Trustrun contract module dogfood")
    print("Records judged: %d  |  claims checked: %d" % (
        len(reports), totals["claims_pass"] + totals["claims_fail"] + totals["claims_unverified"]))
    print("Records: %d pass, %d fail, %d unverified" % (
        totals["pass"], totals["fail"], totals["unverified"]))
    print("Claims:  %d pass, %d fail, %d unverified" % (
        totals["claims_pass"], totals["claims_fail"], totals["claims_unverified"]))
    print()
    for name, report in reports:
        if report["verdict"] != "pass":
            print("[%s] %s" % (report["verdict"].upper(), name))
            for claim in report["claims"]:
                if claim["verdict"] != "pass":
                    print("  %s: %s (%s)" % (
                        claim["verdict"], claim["statement"], claim["evidence"]))
    return 0 if totals["fail"] == 1 and totals["unverified"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
