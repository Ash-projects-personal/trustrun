"""Smoke test for the consistency module stub."""

import pytest

from trustrun.consistency import score_repeated_runs


def test_score_repeated_runs_stub_raises():
    with pytest.raises(NotImplementedError):
        score_repeated_runs(None, None, 1)
