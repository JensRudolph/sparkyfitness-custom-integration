"""Tests for actionable compatibility and authentication repairs."""

from unittest.mock import MagicMock

from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sparkyfitness.const import (
    CONF_ENABLE_CHECKIN,
    CONF_ENABLE_ENGAGEMENT,
    CONF_ENABLE_EXERCISE,
    CONF_ENABLE_GOALS,
    CONF_ENABLE_HABITS,
    CONF_ENABLE_NUTRITION,
    CONF_ENABLE_TRENDS,
    DOMAIN,
    TOOL_HEALTH_SUMMARY,
    TOOL_NUTRITION_SUMMARY,
)
from custom_components.sparkyfitness.repairs import (
    async_create_authentication_issue,
    async_update_connection_issues,
)


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_ENABLE_NUTRITION: True,
            CONF_ENABLE_EXERCISE: False,
            CONF_ENABLE_CHECKIN: False,
            CONF_ENABLE_ENGAGEMENT: False,
            CONF_ENABLE_GOALS: False,
            CONF_ENABLE_TRENDS: False,
            CONF_ENABLE_HABITS: False,
        },
    )


def test_missing_tools_and_protocol_repairs_are_created_and_cleared(hass) -> None:
    """Discovery issues follow the current endpoint capabilities."""

    entry = _entry()
    client = MagicMock()
    client.tools = {TOOL_HEALTH_SUMMARY: object()}
    client.protocol_version = "future-version"
    async_update_connection_issues(hass, entry, client)
    registry = ir.async_get(hass)
    assert registry.async_get_issue(
        DOMAIN, f"missing_tools_{entry.entry_id}"
    ) is not None
    assert registry.async_get_issue(
        DOMAIN, f"unsupported_protocol_{entry.entry_id}"
    ) is not None

    client.tools[TOOL_NUTRITION_SUMMARY] = object()
    client.protocol_version = "2025-11-25"
    async_update_connection_issues(hass, entry, client)
    assert registry.async_get_issue(DOMAIN, f"missing_tools_{entry.entry_id}") is None
    assert (
        registry.async_get_issue(DOMAIN, f"unsupported_protocol_{entry.entry_id}")
        is None
    )


def test_authentication_repair_is_cleared_after_success(hass) -> None:
    """A reauthenticated entry no longer leaves an obsolete repair behind."""

    entry = _entry()
    async_create_authentication_issue(hass, entry)
    registry = ir.async_get(hass)
    assert registry.async_get_issue(
        DOMAIN, f"authentication_{entry.entry_id}"
    ) is not None

    client = MagicMock()
    client.tools = {TOOL_HEALTH_SUMMARY: object(), TOOL_NUTRITION_SUMMARY: object()}
    client.protocol_version = "2025-11-25"
    async_update_connection_issues(hass, entry, client)
    assert registry.async_get_issue(DOMAIN, f"authentication_{entry.entry_id}") is None
