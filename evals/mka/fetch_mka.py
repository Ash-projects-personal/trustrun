"""Fetch the 10 public MKA showcase tasks and vendor them as tasks.json.

Source: Hugging Face dataset google/multimodal-knowledge-agent
(Google DeepMind + Artificial Analysis, Multimodal Knowledge Agent
benchmark, Nov 10, 2026; Apache 2.0). The 200-task set stays private
(anti-leakage); only the 10 public showcase tasks ship here.

Usage: python3 fetch_mka.py
Writes evals/mka/tasks.json next to this script. Only metadata.json
and rubrics.json are vendored: the input files (images, CAD, rasters,
spreadsheets) are load-bearing visual artifacts the text-only
pipeline cannot read, so they are listed by name only and the runner
records them as unprocessed. Re-running the script re-fetches from
the same dataset revision and must produce the same task count and
criterion count (10 tasks, 835 criteria); the script asserts both.
"""

import json
import os
import urllib.request

DATASET = "google/multimodal-knowledge-agent"
REVISION = "46bce7ab8768f661750bd1016ec8cbdc517740b5"
API_URL = "https://huggingface.co/api/datasets/" + DATASET
RAW_URL = (
    "https://huggingface.co/datasets/" + DATASET
    + "/raw/" + REVISION + "/tasks/%s/%s"
)

EXPECTED_TASKS = 10
EXPECTED_CRITERIA = 835

HERE = os.path.dirname(os.path.abspath(__file__))


def _get_json(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def fetch_tasks():
    """Download the task list plus metadata and rubrics per task."""
    info = _get_json(API_URL)
    if info.get("sha") != REVISION:
        raise ValueError(
            "dataset revision moved: API reports %r, pinned %r"
            % (info.get("sha"), REVISION)
        )
    task_ids = sorted(
        {
            s["rfilename"].split("/")[1]
            for s in info.get("siblings", [])
            if s["rfilename"].startswith("tasks/")
        }
    )
    tasks = []
    total_criteria = 0
    for task_id in task_ids:
        meta = _get_json(RAW_URL % (task_id, "metadata.json"))
        rubrics = _get_json(RAW_URL % (task_id, "rubrics.json"))
        criteria = []
        for key in sorted(
            rubrics, key=lambda k: int(k.split()[-1]) if k.split()[-1].isdigit() else 0
        ):
            entry = rubrics[key]
            criteria.append(
                {
                    "id": key,
                    "description": entry.get("description", ""),
                    "weight": entry.get("criterion_weight", 1),
                    "grading_target": entry.get("grading_target", ""),
                }
            )
        total_criteria += len(criteria)
        tasks.append(
            {
                "task_id": task_id,
                "vertical": meta.get("Vertical", ""),
                "domain": meta.get("Domain", ""),
                "role": meta.get("Role", ""),
                "goal": meta.get("Task Goal", ""),
                "prompt": meta.get("Prompt", ""),
                "input_files": meta.get("Input_files", ""),
                "criteria": criteria,
            }
        )
    return tasks, total_criteria


def main():
    tasks, total_criteria = fetch_tasks()
    if len(tasks) != EXPECTED_TASKS:
        raise ValueError(
            "expected %d tasks, got %d" % (EXPECTED_TASKS, len(tasks))
        )
    if total_criteria != EXPECTED_CRITERIA:
        raise ValueError(
            "expected %d criteria, got %d"
            % (EXPECTED_CRITERIA, total_criteria)
        )
    out = {
        "source": "https://huggingface.co/datasets/" + DATASET,
        "revision": REVISION,
        "license": "Apache-2.0",
        "tasks": tasks,
        "criterion_count": total_criteria,
    }
    path = os.path.join(HERE, "tasks.json")
    with open(path, "w") as handle:
        json.dump(out, handle, indent=1, sort_keys=True)
    print(
        "vendored %d tasks, %d criteria -> %s"
        % (len(tasks), total_criteria, path)
    )


if __name__ == "__main__":
    main()
