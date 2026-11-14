"""The deterministic stub is vendored in the repo.

The stub's canonical copy lives in the audit venv tree
(trustrun-venvs/n8n-venv/n8n-stub.py), which is not part of the
repo. A byte-identical copy is vendored at
evals/real_agents/n8n_stub.py so a fresh clone can import every
adapter and run the pure tests; the adapters prefer the venv copy
when it exists and fall back to the vendored one. These tests pin
that arrangement: the vendored copy must load and expose the stub
API, and when both copies exist they must stay byte-identical.
"""

import importlib.util
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_STUB = os.path.normpath(os.path.join(
    HERE, "..", "evals", "real_agents", "n8n_stub.py"))
VENV_STUB = os.path.normpath(os.path.join(
    HERE, "..", "..", "trustrun-venvs", "n8n-venv", "n8n-stub.py"))


def _load(path):
    spec = importlib.util.spec_from_file_location("vendored_stub", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_vendored_stub_loads_and_exposes_api():
    mod = _load(REPO_STUB)
    assert hasattr(mod, "DeterministicStub")
    assert hasattr(mod, "decide_for_request")


@pytest.mark.skipif(
    not os.path.exists(VENV_STUB),
    reason="audit venv stub not present on this machine")
def test_vendored_copy_matches_venv_copy():
    with open(REPO_STUB, "rb") as fh:
        repo_bytes = fh.read()
    with open(VENV_STUB, "rb") as fh:
        venv_bytes = fh.read()
    assert repo_bytes == venv_bytes, (
        "evals/real_agents/n8n_stub.py has drifted from "
        "trustrun-venvs/n8n-venv/n8n-stub.py; re-copy the venv "
        "stub over the vendored one (or the other way, on purpose)")
