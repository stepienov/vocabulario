"""API tests for offline sync moves (MVP stubs)."""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Requires test DB + auth fixtures")
def test_sync_push_move_idempotent():
    assert True
