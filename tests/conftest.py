"""Shared Home Assistant test fixtures."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading the integration from custom_components."""

    yield
