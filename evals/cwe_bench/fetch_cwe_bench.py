"""Fetch the CWE-bench v2 public task files into evals/cwe_bench/snapshot/.

The dataset (collinear-ai/cwe-bench) is GATED: accept the access
conditions on the dataset page first (automatic approval), then run
this script with an HF token that can read gated repos:

    export HF_TOKEN=<token>
    python3 evals/cwe_bench/fetch_cwe_bench.py

The token is read from the environment only and is never printed or
written to disk by this script. Without it the Hub answers 401 on
every task file (the dataset README is public, the task files are
not); the script then exits non-zero with the access step named.

What it downloads: LICENSE, NOTICE, README.md, registry.json, and
per task (100 public tasks) task.toml, instruction.md,
solution/solve.sh, tests/test.sh, tests/verify_programmatic.py, and
tests/probe_map.json when listed. It SKIPS environment/ by default:
the repo tarballs (environment/repo.tar.gz) are large and only
needed to actually run the Harbor verifier; pass --include-env to
also fetch the small environment files (Dockerfile,
docker-compose.yaml, env.json), still skipping the tarballs. Harbor
itself can resolve the dataset from the repo when the token is
configured, so the tarballs never need to live in this checkout.

It writes evals/cwe_bench/snapshot/manifest.json (dataset id,
fetch time, file list with sizes and sha256, task count) next to the
downloaded files, which trustrun.audit_repair.load_snapshot reads.

Do NOT republish the solutions (solution/solve.sh): the dataset
terms forbid it, and the snapshot directory is local working state,
not shipped content. Keep the LICENSE and NOTICE files with any
redistribution, as Apache 2.0 requires.
"""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

DATASET_ID = "collinear-ai/cwe-bench"
API_BASE = "https://huggingface.co/api/datasets/" + DATASET_ID
RESOLVE_BASE = "https://huggingface.co/datasets/" + DATASET_ID + "/resolve/main/"
DATASET_PAGE = "https://huggingface.co/datasets/" + DATASET_ID

HERE = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_DIR = os.path.join(HERE, "snapshot")

ROOT_FILES = ("LICENSE", "NOTICE", "README.md", "registry.json")
TASK_FILES = (
    "task.toml",
    "instruction.md",
    "solution/solve.sh",
    "tests/test.sh",
    "tests/verify_programmatic.py",
    "tests/probe_map.json",
)
ENV_FILES = ("Dockerfile", "docker-compose.yaml", "env.json")


def _headers(token):
    headers = {"User-Agent": "trustrun-fetch-cwe-bench/1.0"}
    if token:
        headers["Authorization"] = "Bearer " + token
    return headers


def _get_json(url, token):
    request = urllib.request.Request(url, headers=_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise SystemExit(
                "401 from the Hub: %s is gated. Accept the access "
                "conditions at %s (Ash's ashishrs account), then "
                "re-run with HF_TOKEN set to a token that can read "
                "gated repos." % (DATASET_ID, DATASET_PAGE)
            )
        raise


def _download(rel_path, token, dest_path):
    request = urllib.request.Request(
        RESOLVE_BASE + rel_path, headers=_headers(token)
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise SystemExit(
                "401 downloading %s: %s is gated. Accept the access "
                "conditions at %s, then re-run with HF_TOKEN set."
                % (rel_path, DATASET_ID, DATASET_PAGE)
            )
        raise
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as handle:
        handle.write(data)
    return {
        "path": rel_path,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _list_task_dirs(token):
    """Task directory names under tasks/ from the Hub tree API."""
    entries = _get_json(API_BASE + "/tree/main/tasks?recursive=false", token)
    names = []
    for entry in entries:
        if entry.get("type") == "directory":
            names.append(entry["path"].split("/")[-1])
    return sorted(names)


def _list_task_files(task_name, token):
    entries = _get_json(
        API_BASE + "/tree/main/tasks/" + task_name + "?recursive=true",
        token,
    )
    return sorted(
        entry["path"]
        for entry in entries
        if entry.get("type") == "file"
    )


def main(argv):
    include_env = "--include-env" in argv
    token = os.environ.get("HF_TOKEN") or os.environ.get(
        "HUGGING_FACE_HUB_TOKEN"
    )
    if not token:
        print(
            "No HF_TOKEN in the environment. %s is gated; set "
            "HF_TOKEN to a token that can read gated repos (accept "
            "the conditions at %s first)."
            % (DATASET_ID, DATASET_PAGE)
        )
        return 2
    task_names = _list_task_dirs(token)
    print("found %d task directories" % len(task_names))
    manifest_files = []
    for rel_path in ROOT_FILES:
        dest = os.path.join(SNAPSHOT_DIR, rel_path)
        manifest_files.append(_download(rel_path, token, dest))
        print("downloaded %s" % rel_path)
    for task_name in task_names:
        listed = _list_task_files(task_name, token)
        wanted = set()
        for rel in TASK_FILES:
            if ("tasks/%s/%s" % (task_name, rel)) in listed:
                wanted.add(rel)
        if include_env:
            for rel in ENV_FILES:
                path = "environment/" + rel
                if ("tasks/%s/%s" % (task_name, path)) in listed:
                    wanted.add(path)
        for rel in sorted(wanted):
            full = "tasks/%s/%s" % (task_name, rel)
            dest = os.path.join(SNAPSHOT_DIR, full)
            manifest_files.append(_download(full, token, dest))
        print("downloaded tasks/%s (%d files)" % (task_name, len(wanted)))
    manifest = {
        "dataset": DATASET_ID,
        "task_count": len(task_names),
        "include_env": include_env,
        "files": manifest_files,
    }
    with open(os.path.join(SNAPSHOT_DIR, "manifest.json"), "w") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
    print(
        "snapshot complete: %d tasks, %d files in %s"
        % (len(task_names), len(manifest_files), SNAPSHOT_DIR)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
