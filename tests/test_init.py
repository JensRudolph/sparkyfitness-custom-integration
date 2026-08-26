"""Tests for config-entry lifecycle wiring."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_URL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sparkyfitness import async_setup_entry, async_unload_entry
from custom_components.sparkyfitness.const import (
    CONF_API_KEY,
    CONF_VERIFY_SSL,
    DOMAIN,
    TOOL_CHECKIN,
)


async def test_setup_and_unload_entry(hass) -> None:
    """Each entry owns an independent client/coordinator and releases protocol state."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://sparky.example.com/mcp",
            CONF_API_KEY: "key",
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    async def discover(client):
        client.tools = {TOOL_CHECKIN: object()}
        client.server_info = {"version": "1.6.3"}
        return client.tools

    with (
        patch(
            "custom_components.sparkyfitness.SparkyFitnessMcpClient.async_test_connection",
            new=discover,
        ),
        patch(
            "custom_components.sparkyfitness.SparkyFitnessCoordinator.async_config_entry_first_refresh",
            new=AsyncMock(),
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ) as forward,
    ):
        assert await async_setup_entry(hass, entry) is True

    assert entry.runtime_data.client.server_version == "1.6.3"
    assert entry.runtime_data.coordinator.client is entry.runtime_data.client
    forward.assert_awaited_once()

    with (
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new=AsyncMock(return_value=True),
        ),
        patch.object(
            entry.runtime_data.client,
            "async_disconnect",
            new=AsyncMock(),
        ) as disconnect,
    ):
        assert await async_unload_entry(hass, entry) is True
    disconnect.assert_awaited_once()
