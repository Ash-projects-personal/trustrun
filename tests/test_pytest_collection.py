"""Regression test: pytest must never collect vendored third-party
source trees.

Audit 73 (Continue) cloned the framework source into
evals/reports/real_agents/continue/continue-src/, whose
continue-sdk package ships test_*.py files that error at collection
(the generated SDK deps are absent), breaking the whole suite with
16 collection errors. The fix is the norecursedirs setting in
pyproject.toml ([tool.pytest.ini_options]); this test guards it:
it re-runs collection over the repo root and asserts it succeeds
with no collected item under a *-src tree.
"""

import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_collection_ignores_vendored_source_trees():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", REPO_ROOT],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        "collection failed (vendored source tree collected?):\n"
        + result.stdout[-2000:] + result.stderr[-2000:]
    )
    assert "-src/" not in result.stdout, (
        "a *-src vendored tree was collected:\n"
        + "\n".join(
            line for line in result.stdout.splitlines() if "-src/" in line
        )[:10]
    )
