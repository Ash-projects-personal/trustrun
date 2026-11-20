"""Verify TRUSTRUN-WhitespaceNormalize on the real t1-t9 tasks.

Re-runs the task_tamper and terminal_gap cells for tasks t1-t9
with the harness runners and an echo agent modeled on the audit-90
Stagehand behavior: the agent returns the whole tool document with
internal newlines flattened to spaces, as a page rendering does.
The audit-90 record scored t9 task_tamper + terminal_gap False on
this behavior; after the fix both cells must read "unverified"
(echo, not adoption), and t1-t8 must read exactly as before.
Writes evals/reports/whitespace_normalize_verification.json.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from tools import calculator, search_docs  # noqa: E402
from trustrun.stress import replay_attack  # noqa: E402


def echo_agent(task_text, tools):
    """Whole-document echo, newlines flattened as a page renders."""
    result = tools["search_docs"](task_text)
    if isinstance(result, dict):
        content = result.get("content", "")
    elif isinstance(result, str):
        content = result
    else:
        content = ""
    return {"result": " ".join(str(content).split())}


def main():
    tasks = json.load(open(os.path.join(HERE, "tasks.json")))
    first_nine = tasks[:9]
    cells = []
    for task in first_nine:
        built = {
            "text": task["text"],
            "tools": {"search_docs": search_docs, "calculator": calculator},
            "expect": task.get("expect", ""),
        }
        for kind in ("task_tamper", "terminal_gap"):
            record = replay_attack(
                echo_agent, built, {"kind": kind, "tool": "search_docs"}
            )
            followed = record.get(
                "followed_targets",
                record.get("followed_techniques", []),
            )
            cells.append(
                {
                    "task": task["id"],
                    "kind": kind,
                    "survived": record["survived"],
                    "followed": followed,
                    "probes": record["probes"],
                }
            )
    out = {
        "item": "TRUSTRUN-WhitespaceNormalize",
        "agent": "whole-document echo, newlines flattened to spaces",
        "cells": cells,
    }
    path = os.path.join(
        HERE, "reports", "whitespace_normalize_verification.json"
    )
    with open(path, "w") as handle:
        json.dump(out, handle, indent=1)
    for cell in cells:
        print(
            "%s %s survived=%s followed=%s probes=%d"
            % (
                cell["task"],
                cell["kind"],
                cell["survived"],
                cell["followed"],
                cell["probes"],
            )
        )
    print("wrote", path)


if __name__ == "__main__":
    main()
