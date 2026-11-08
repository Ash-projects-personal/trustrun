"""Run the ContractTarget calibration: judge vs maintainer-grade verdicts.

Usage: python3 run_contract_target.py

For each of the six clean-room agents over the eight eval tasks, runs
the agent once, takes its recorded result, and labels the pair with
the maintainer-grade verdict: "pass" when the result contains the
task's expected answer, "fail" otherwise. The judge panel under test
is a strict contains judge plus a noisy judge that flips its verdict
with probability 0.10 (seeded, a stated test instrument: it measures
whether the multi-trial majority machinery recovers ground truth
despite a noisy panel member). calibrate_judge then reports agreement
with the labeled verdicts, mean flip rate, and Fleiss' kappa.

Target instrument: Cognition FrontierCode 2.0 (132 private tasks,
maintainer-merge grading, Opus 5.5 45.5% pass, Claude Sonnet 4.5
33.6%). FrontierCode is private, so this script calibrates on
Trustrun's own labeled corpus as the proxy and records the gap; the
agreement number here is a judge-machinery measurement, not a
FrontierCode score. Writes the machine readable summary into
reports/contract_target/summary.json. Every number in that file comes
from a real run. Nothing is invented.
"""

import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from agents import plan_execute_agent, rag_agent, react_agent  # noqa: E402
from agents_round2 import (  # noqa: E402
    guardrail_rag_agent,
    hardened_agent,
    reflection_agent,
)
from tools import calculator, search_docs  # noqa: E402
from trustrun.contract.calibration import calibrate_judge  # noqa: E402

AGENTS = {
    "react": react_agent,
    "rag": rag_agent,
    "plan_execute": plan_execute_agent,
    "guardrail_rag": guardrail_rag_agent,
    "hardened": hardened_agent,
    "reflection": reflection_agent,
}

TOOL_BUILDERS = {
    "calculator": calculator,
    "search_docs": search_docs,
}

OUT_DIR = os.path.join(HERE, "reports", "contract_target")
NOISE_RATE = 0.10


def _strict_judge(value, claim, output):
    expect = output.get("expect", "")
    if isinstance(value, str) and expect and expect in value:
        return True, "result contains the expected answer"
    return False, "result does not contain the expected answer"


def _noisy_judge_factory(rng, rate=NOISE_RATE):
    def _noisy_judge(value, claim, output):
        decision, evidence = _strict_judge(value, claim, output)
        if rng.random() < rate:
            return (not decision), "noisy flip of the strict verdict"
        return decision, evidence

    return _noisy_judge


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(HERE, "tasks.json"), encoding="utf-8") as handle:
        tasks = json.load(handle)
    rng = random.Random(7)
    panel = [_strict_judge, _noisy_judge_factory(rng)]
    pairs = []
    started = time.time()
    for agent_name, agent in AGENTS.items():
        for task_def in tasks:
            tools = {
                name: TOOL_BUILDERS[name]
                for name in task_def["tools_order"]
            }
            result = agent(task_def["text"], tools)
            value = result.get("result", "") if isinstance(result, dict) else ""
            expect = task_def["expect"]
            expected = (
                "pass" if isinstance(value, str) and expect in value else "fail"
            )
            pairs.append({
                "id": "%s__%s" % (agent_name, task_def["id"]),
                "claim": {
                    "id": "answer",
                    "statement": "the output answers the task",
                    "kind": "judge",
                },
                "value": value,
                "output": {"result": value, "expect": expect},
                "expected": expected,
            })
    report = calibrate_judge(pairs, trials=11, judges=panel, seed=0)
    summary = {
        "n_pairs": report["n"],
        "agents": sorted(AGENTS),
        "tasks": [t["id"] for t in tasks],
        "trials": 11,
        "panel": ["strict_contains", "noisy_flip_p0.10"],
        "agreement": report["agreement"],
        "agreement_decided": report["agreement_decided"],
        "mean_flip_rate": report["mean_flip_rate"],
        "kappa": report["kappa"],
        "pairs": report["pairs"],
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w",
              encoding="utf-8") as handle:
        json.dump(summary, handle, indent=1)
    print(
        "contract target: %d pairs, agreement %.3f, "
        "mean flip %.3f, kappa %s (%.1fs)"
        % (
            report["n"],
            report["agreement"],
            report["mean_flip_rate"],
            ("%.3f" % report["kappa"]) if report["kappa"] is not None else "None",
            time.time() - started,
        )
    )


if __name__ == "__main__":
    main()
