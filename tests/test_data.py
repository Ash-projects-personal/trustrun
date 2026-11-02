"""Smoke test for the data module stub."""

import pytest

from trustrun.data import audit_dataset


def test_audit_dataset_stub_raises():
    with pytest.raises(NotImplementedError):
        audit_dataset("/nonexistent/path")
