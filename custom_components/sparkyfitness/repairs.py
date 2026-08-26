"""Actionable Home Assistant repair issues for SparkyFitness compatibility."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .api import SparkyFitnessMcpClient
from .const import (
    CONF_ENABLE_CHECKIN,
    CONF_ENABLE_ENGAGEMENT,
    CONF_ENABLE_EXERCISE,
    CONF_ENABLE_GOALS,
    CONF_ENABLE_HABITS,
    CONF_ENABLE_NUTRITION,
    CONF_ENABLE_TRENDS,
    DOMAIN,
    SUPPORTED_MCP_PROTOCOL_VERSIONS,
    TOOL_30_DAY_TRENDS,
    TOOL_CHECKIN,
    TOOL_GOAL_SNAPSHOT,
    TOOL_HABITS,
    TOOL_HEALTH_SUMMARY,
    TOOL_NUTRITION_SUMMARY,
    TOOL_STREAK,
)

_DOCUMENTATION_URL = (
    "https://github.com/JensRudolph/sparkyfitness-custom-integration#requirements"
)
_FEATURE_TOOLS: tuple[tuple[str, frozenset[str]], ...] = (
    (
        CONF_ENABLE_NUTRITION,
        frozenset({TOOL_HEALTH_SUMMARY, TOOL_NUTRITION_SUMMARY}),
    ),
    (CONF_ENABLE_EXERCISE, frozenset({TOOL_HEALTH_SUMMARY})),
    (CONF_ENABLE_CHECKIN, frozenset({TOOL_CHECKIN})),
    (CONF_ENABLE_ENGAGEMENT, frozenset({TOOL_STREAK})),
    (CONF_ENABLE_GOALS, frozenset({TOOL_GOAL_SNAPSHOT})),
    (CONF_ENABLE_TRENDS, frozenset({TOOL_30_DAY_TRENDS})),
    (CONF_ENABLE_HABITS, frozenset({TOOL_HABITS})),
)


def async_update_connection_issues(
    hass: HomeAssistant,
    entry: ConfigEntry,
    client: SparkyFitnessMcpClient,
) -> None:
    """Create or clear compatibility issues after successful discovery."""

    missing_tools: set[str] = set()
    for option, tools in _FEATURE_TOOLS:
        if entry.options.get(option, True):
            missing_tools.update(tools - client.tools.keys())

    missing_issue_id = f"missing_tools_{entry.entry_id}"
    if missing_tools:
        ir.async_create_issue(
            hass,
            DOMAIN,
            missing_issue_id,
            is_fixable=False,
            learn_more_url=_DOCUMENTATION_URL,
            severity=ir.IssueSeverity.WARNING,
            translation_key="missing_tools",
            translation_placeholders={"tools": ", ".join(sorted(missing_tools))},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, missing_issue_id)

    protocol_issue_id = f"unsupported_protocol_{entry.entry_id}"
    if client.protocol_version not in SUPPORTED_MCP_PROTOCOL_VERSIONS:
        ir.async_create_issue(
            hass,
            DOMAIN,
            protocol_issue_id,
            is_fixable=False,
            learn_more_url=_DOCUMENTATION_URL,
            severity=ir.IssueSeverity.WARNING,
            translation_key="unsupported_protocol",
            translation_placeholders={"version": client.protocol_version},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, protocol_issue_id)

    ir.async_delete_issue(hass, DOMAIN, f"authentication_{entry.entry_id}")


def async_create_authentication_issue(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Expose rejected credentials alongside Home Assistant's reauth flow."""

    ir.async_create_issue(
        hass,
        DOMAIN,
        f"authentication_{entry.entry_id}",
        is_fixable=False,
        learn_more_url=_DOCUMENTATION_URL,
        severity=ir.IssueSeverity.ERROR,
        translation_key="authentication_failed",
    )
