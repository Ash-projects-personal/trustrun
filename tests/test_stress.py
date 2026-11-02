"""Smoke test for the stress module stub."""

import pytest

from trustrun.stress import replay_attack


def test_replay_attack_stub_raises():
    with pytest.raises(NotImplementedError):
        replay_attack(None, None, None)
