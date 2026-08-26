"""Tests for SparkyFitness config and reauthentication flows."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sparkyfitness.const import (
    CONF_ACCOUNT_NAME,
    CONF_API_KEY,
    CONF_ENABLE_CHECKIN,
    CONF_ENABLE_ENGAGEMENT,
    CONF_ENABLE_EXERCISE,
    CONF_ENABLE_GOALS,
    CONF_ENABLE_HABITS,
    CONF_ENABLE_NUTRITION,
    CONF_ENABLE_TRENDS,
    CONF_UPDATE_INTERVAL,
    CONF_VERIFY_SSL,
    DOMAIN,
)
from custom_components.sparkyfitness.exceptions import (
    SparkyFitnessAuthenticationError,
    SparkyFitnessConnectionError,
    SparkyFitnessMcpError,
    SparkyFitnessSslError,
)


async def test_successful_config_flow(hass) -> None:
    """A verified MCP endpoint creates an entry with a normalized URL."""

    with (
        patch(
            "custom_components.sparkyfitness.config_flow.SparkyFitnessMcpClient.async_test_connection",
            new=AsyncMock(return_value={"sparky_manage_checkin": object()}),
        ),
        patch(
            "custom_components.sparkyfitness.config_flow.SparkyFitnessMcpClient.async_disconnect",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_URL: "https://sparky.example.com/",
                CONF_API_KEY: "private-key",
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "sparky.example.com"
    assert result["data"] == {
        CONF_URL: "https://sparky.example.com/mcp",
        CONF_API_KEY: "private-key",
        CONF_VERIFY_SSL: True,
    }


@pytest.mark.parametrize(
    ("error", "error_key"),
    [
        (SparkyFitnessAuthenticationError(), "invalid_auth"),
        (SparkyFitnessConnectionError(), "cannot_connect"),
        (SparkyFitnessMcpError(), "invalid_mcp_server"),
        (SparkyFitnessSslError(), "ssl_error"),
    ],
)
async def test_config_flow_errors(hass, error: Exception, error_key: str) -> None:
    """Connection, auth, non-MCP, and TLS failures remain distinguishable."""

    with (
        patch(
            "custom_components.sparkyfitness.config_flow.SparkyFitnessMcpClient.async_test_connection",
            new=AsyncMock(side_effect=error),
        ),
        patch(
            "custom_components.sparkyfitness.config_flow.SparkyFitnessMcpClient.async_disconnect",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_URL: "https://sparky.example.com",
                CONF_API_KEY: "bad-key",
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_key}


async def test_account_name_distinguishes_shared_server_entries(hass) -> None:
    """An optional account label is reflected in the config-entry title."""

    with (
        patch(
            "custom_components.sparkyfitness.config_flow.SparkyFitnessMcpClient.async_test_connection",
            new=AsyncMock(return_value={"sparky_manage_checkin": object()}),
        ),
        patch(
            "custom_components.sparkyfitness.config_flow.SparkyFitnessMcpClient.async_disconnect",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_URL: "https://sparky.example.com",
                CONF_ACCOUNT_NAME: "Jens",
                CONF_API_KEY: "private-key",
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Jens · sparky.example.com"
    assert result["data"][CONF_ACCOUNT_NAME] == "Jens"


async def test_non_url_is_rejected_before_network(hass) -> None:
    """Malformed connection data never reaches the MCP client."""

    test_connection = AsyncMock()
    with patch(
        "custom_components.sparkyfitness.config_flow.SparkyFitnessMcpClient.async_test_connection",
        new=test_connection,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_URL: "not-a-url",
                CONF_API_KEY: "key",
                CONF_VERIFY_SSL: True,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}
    test_connection.assert_not_awaited()


async def test_reauthentication_updates_only_the_api_key(hass) -> None:
    """A revoked key can be replaced without deleting connection metadata."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://sparky.example.com/mcp",
            CONF_API_KEY: "old-key",
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.sparkyfitness.config_flow.SparkyFitnessMcpClient.async_test_connection",
            new=AsyncMock(return_value={"sparky_manage_checkin": object()}),
        ),
        patch(
            "custom_components.sparkyfitness.config_flow.SparkyFitnessMcpClient.async_disconnect",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "new-key"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "new-key"
    assert entry.data[CONF_URL] == "https://sparky.example.com/mcp"


async def test_options_flow(hass) -> None:
    """Polling, TLS, and feature groups are saved as config-entry options."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: "https://sparky.example.com/mcp",
            CONF_API_KEY: "key",
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    options = {
        CONF_ACCOUNT_NAME: "Jens",
        CONF_UPDATE_INTERVAL: 10,
        CONF_VERIFY_SSL: False,
        CONF_ENABLE_NUTRITION: True,
        CONF_ENABLE_EXERCISE: False,
        CONF_ENABLE_CHECKIN: True,
        CONF_ENABLE_ENGAGEMENT: False,
        CONF_ENABLE_GOALS: True,
        CONF_ENABLE_TRENDS: False,
        CONF_ENABLE_HABITS: True,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], options
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == options
    assert entry.title == "Jens · sparky.example.com"


async def test_reconfigure_updates_endpoint_tls_and_title(hass) -> None:
    """The supported reconfigure flow retains credentials and reloads the entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Jens · old.example.com",
        data={
            CONF_URL: "https://old.example.com/mcp",
            CONF_API_KEY: "private-key",
            CONF_VERIFY_SSL: True,
        },
        options={CONF_ACCOUNT_NAME: "Jens", CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.sparkyfitness.config_flow.SparkyFitnessMcpClient.async_test_connection",
            new=AsyncMock(return_value={"sparky_manage_checkin": object()}),
        ),
        patch(
            "custom_components.sparkyfitness.config_flow.SparkyFitnessMcpClient.async_disconnect",
            new=AsyncMock(),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: "https://new.example.com/", CONF_VERIFY_SSL: False},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_URL] == "https://new.example.com/mcp"
    assert entry.data[CONF_API_KEY] == "private-key"
    assert entry.options[CONF_VERIFY_SSL] is False
    assert entry.title == "Jens · new.example.com"
