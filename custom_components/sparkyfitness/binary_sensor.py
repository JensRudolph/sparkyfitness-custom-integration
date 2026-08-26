"""Binary sensor platform for SparkyFitness."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_ENABLE_CHECKIN, TOOL_CHECKIN
from .entity import SparkyFitnessEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up fasting state when the check-in tool is available."""

    coordinator = entry.runtime_data.coordinator
    if TOOL_CHECKIN in coordinator.client.tools and coordinator.feature_enabled(
        CONF_ENABLE_CHECKIN
    ):
        async_add_entities([SparkyFitnessFastingBinarySensor(coordinator)])


class SparkyFitnessFastingBinarySensor(SparkyFitnessEntity, BinarySensorEntity):
    """Whether SparkyFitness reports an active fasting session."""

    entity_description = BinarySensorEntityDescription(
        key="fasting",
        translation_key="fasting",
        icon="mdi:timer-sand",
    )

    def __init__(self, coordinator) -> None:
        """Initialize the binary sensor."""

        super().__init__(coordinator, self.entity_description.key)

    @property
    def is_on(self) -> bool:
        """Return true only for the server's current active fast."""

        fasting = self.coordinator.data.fasting
        return (
            fasting is not None and fasting.get("fasting_status", "ACTIVE") == "ACTIVE"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose only compact, non-health-history session metadata."""

        fasting = self.coordinator.data.fasting or {}
        attributes = {
            key: value
            for key, value in {
                "start_time": fasting.get("start_time"),
                "end_time": fasting.get("end_time"),
                "fasting_type": fasting.get("fasting_type"),
            }.items()
            if value is not None
        }
        if start := dt_util.parse_datetime(str(fasting.get("start_time") or "")):
            end = dt_util.parse_datetime(str(fasting.get("end_time") or ""))
            elapsed = (
                dt_util.as_utc(end) if end else datetime.now(UTC)
            ) - dt_util.as_utc(start)
            attributes["duration"] = max(0, round(elapsed.total_seconds()))
        return attributes
