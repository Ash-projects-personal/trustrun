"""Smoke test for the contract module stub."""

import pytest

from trustrun.contract import verify_delivery


def test_verify_delivery_stub_raises():
    with pytest.raises(NotImplementedError):
        verify_delivery({}, {})
