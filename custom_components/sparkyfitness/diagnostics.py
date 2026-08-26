"""Privacy-preserving diagnostics for SparkyFitness."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from homeassistant.core import HomeAssistant

from . import SparkyFitnessConfigEntry
from .const import (
    CONF_ENABLE_CHECKIN,
    CONF_ENABLE_ENGAGEMENT,
    CONF_ENABLE_EXERCISE,
    CONF_ENABLE_NUTRITION,
    CONF_UPDATE_INTERVAL,
    CONF_VERIFY_SSL,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_VERIFY_SSL,
    INTEGRATION_VERSION,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SparkyFitnessConfigEntry
) -> dict[str, Any]:
    """Return technical metadata without credentials or health data."""

    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    endpoint = runtime.client.endpoint
    return {
        "hostname": urlsplit(endpoint).hostname,
        "mcp_endpoint": endpoint,
        "integration_version": INTEGRATION_VERSION,
        "sparkyfitness_version": runtime.client.server_version,
        "detected_mcp_tools": sorted(runtime.client.tools),
        "feature_groups": {
            "nutrition": coordinator.feature_enabled(CONF_ENABLE_NUTRITION),
            "exercise": coordinator.feature_enabled(CONF_ENABLE_EXERCISE),
            "checkin": coordinator.feature_enabled(CONF_ENABLE_CHECKIN),
            "engagement": coordinator.feature_enabled(CONF_ENABLE_ENGAGEMENT),
        },
        "update_interval_minutes": entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        ),
        "verify_ssl": entry.options.get(
            CONF_VERIFY_SSL,
            entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        ),
        "last_successful_coordinator_refresh": (
            coordinator.last_successful_refresh.isoformat()
            if coordinator.last_successful_refresh
            else None
        ),
        "last_technical_error_class": coordinator.last_error_class,
    }
