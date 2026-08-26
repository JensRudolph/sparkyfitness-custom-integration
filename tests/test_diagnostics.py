"""Tests that diagnostics never expose credentials or health values."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.sparkyfitness.diagnostics import (
    async_get_config_entry_diagnostics,
)


async def test_diagnostics_are_metadata_only(hass) -> None:
    """API keys and coordinator health payloads are not reachable in output."""

    client = MagicMock()
    client.endpoint = "https://sparky.example.com/mcp"
    client.server_version = "1.6.3"
    client.tools = {"sparky_manage_checkin": object()}
    coordinator = MagicMock()
    coordinator.feature_enabled.return_value = True
    coordinator.last_successful_refresh = datetime(2026, 8, 26, tzinfo=UTC)
    coordinator.last_error_class = None
    coordinator.data.values = {"weight": 84.7, "mood": 8}
    entry = MagicMock()
    entry.data = {"api_key": "super-secret", "verify_ssl": True}
    entry.options = {}
    entry.runtime_data = SimpleNamespace(client=client, coordinator=coordinator)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(diagnostics)
    assert "super-secret" not in serialized
    assert "84.7" not in serialized
    assert '"mood"' not in serialized
    assert diagnostics["detected_mcp_tools"] == ["sparky_manage_checkin"]
