"""Actionable Home Assistant repair issues for SparkyFitness compatibility."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
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

    missing_options = _missing_feature_options(entry, client)
    missing_tools = {
        tool
        for option, tools in _FEATURE_TOOLS
        if option in missing_options
        for tool in tools - client.tools.keys()
    }

    missing_issue_id = f"missing_tools_{entry.entry_id}"
    if missing_tools:
        ir.async_create_issue(
            hass,
            DOMAIN,
            missing_issue_id,
            is_fixable=True,
            data={
                "entry_id": entry.entry_id,
                "options": ",".join(sorted(missing_options)),
            },
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


def async_create_authentication_issue(hass: HomeAssistant, entry: ConfigEntry) -> None:
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


def _missing_feature_options(
    entry: ConfigEntry, client: SparkyFitnessMcpClient
) -> set[str]:
    """Return enabled feature switches whose required tools are incomplete."""

    return {
        option
        for option, tools in _FEATURE_TOOLS
        if entry.options.get(option, True) and not tools.issubset(client.tools)
    }


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a flow that disables only feature groups missing MCP tools."""

    entry_id = str((data or {}).get("entry_id") or "")
    options = {
        option for option in str((data or {}).get("options") or "").split(",") if option
    }
    return MissingToolsRepairFlow(entry_id, options)


class MissingToolsRepairFlow(RepairsFlow):
    """Confirm and apply the safe local fix for unavailable feature groups."""

    def __init__(self, entry_id: str, options: set[str]) -> None:
        """Initialize the repair flow from issue-owned technical data."""

        self._entry_id = entry_id
        self._options = options

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Start the confirmation flow."""

        return await self.async_step_confirm(user_input)

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Disable only affected feature groups after explicit confirmation."""

        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return self.async_abort(reason="entry_not_found")
        feature_names = ", ".join(
            sorted(option.removeprefix("enable_") for option in self._options)
        )
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                description_placeholders={"features": feature_names},
            )

        options = {**entry.options}
        options.update(dict.fromkeys(self._options, False))
        self.hass.config_entries.async_update_entry(entry, options=options)
        self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_create_entry(data={})
