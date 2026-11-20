"""Planted-error judge round 1: demo detecting agent over the full
Skepthical corpus (TRUSTRUN-PlantedErrorJudge).

Runs trustrun.planted_error_judge.demo_detecting_agent over all 447
tasks (357 planted + 90 clean) at k=4 and writes the target report
to evals/reports/planted_error_judge/summary.json. The agent is a
deterministic stub: it quotes the passage it was given as one
finding with a generic issue line. Its numbers describe the stub
and the quoting proxy, not a real reviewer: detection passes
whenever the injected span sits inside the first 400 characters
(the stub quotes passage[:400]); characterisation needs the issue
text to name the planted fault, which the stub's generic line never
does. This round proves the harness end to end on the real corpus
and banks the first labeled planted-error rows. It is NOT a
measurement of any real model.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from trustrun.planted_error_judge import (  # noqa: E402
    build_tasks,
    demo_detecting_agent,
    load_corpus,
    run_judge_target,
)

CORPUS = os.path.join(
    ROOT, "trustrun-venvs", "skepthical-venv", "skepthical-repo"
)
OUT_DIR = os.path.join(HERE, "reports", "planted_error_judge")
OUT_PATH = os.path.join(OUT_DIR, "summary.json")
K = 4


def main():
    corpus = load_corpus(CORPUS)
    assert corpus["paper_count"] == 30, corpus["paper_count"]
    assert corpus["error_count"] == 357, corpus["error_count"]
    tasks = build_tasks(corpus)
    assert len(tasks) == 447, len(tasks)
    report = run_judge_target(demo_detecting_agent, tasks, k=K, seed=0)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("tasks: %d planted + %d clean" % (
        report["planted_count"], report["clean_count"]))
    print("detection_rate: %s" % report["detection_rate"])
    print("characterisation_rate: %s" % report["characterisation_rate"])
    print("false_positive_rate: %s" % report["false_positive_rate"])
    print("detection_by_module: %s" % report["detection_by_module"])
    print("detection_by_severity: %s" % report["detection_by_severity"])
    print("check_level_judgments: %d" % report["check_level_judgments"])
    print("wrote %s" % OUT_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
