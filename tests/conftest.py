"""Shared pytest fixtures.

Legacy API tests were written when workbench read endpoints were anonymous.
Since the share-reader hardening (正文接口要求登录), those endpoints enforce
auth in jwt/casdoor modes. Default the legacy suite to ``disabled`` mode
(require_auth passes everyone through); test_publish_share.py explicitly
re-enables jwt mode to test the real permission matrix.
"""

from __future__ import annotations

import pytest

from novel_creator.config import settings


@pytest.fixture(autouse=True)
def _default_disabled_auth(monkeypatch):
    # Module-local autouse fixtures (e.g. test_publish_share._isolate) run after
    # this one and may re-enable jwt mode to exercise real permissions.
    monkeypatch.setattr(settings, "auth_mode", "disabled")
    yield
