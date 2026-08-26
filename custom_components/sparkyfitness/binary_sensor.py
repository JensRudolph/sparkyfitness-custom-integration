"""Binary sensor platform for SparkyFitness."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENABLE_CHECKIN,
    CONF_ENABLE_HABITS,
    TOOL_CHECKIN,
    TOOL_HABITS,
)
from .entity import SparkyFitnessEntity
from .fasting import fasting_metrics


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
        async_add_entities(
            [
                SparkyFitnessFastingBinarySensor(coordinator),
                SparkyFitnessFastingGoalBinarySensor(coordinator),
            ]
        )

    if TOOL_HABITS not in coordinator.client.tools or not coordinator.feature_enabled(
        CONF_ENABLE_HABITS
    ):
        return

    known_habit_ids: set[str] = set()

    @callback
    def async_add_new_habits() -> None:
        """Add newly discovered habits without persisting their history."""

        new_ids = set(coordinator.data.habits) - known_habit_ids
        if not new_ids:
            return
        async_add_entities(
            SparkyFitnessHabitBinarySensor(
                coordinator,
                habit_id,
                str(coordinator.data.habits[habit_id].get("name") or "Habit"),
            )
            for habit_id in sorted(new_ids)
        )
        known_habit_ids.update(new_ids)

    async_add_new_habits()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_habits))


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


class SparkyFitnessFastingGoalBinarySensor(SparkyFitnessEntity, BinarySensorEntity):
    """Whether a parseable active fasting protocol has reached its target."""

    entity_description = BinarySensorEntityDescription(
        key="fasting_goal_reached",
        translation_key="fasting_goal_reached",
        icon="mdi:timer-check-outline",
    )

    def __init__(self, coordinator) -> None:
        """Initialize the fasting target sensor."""

        super().__init__(coordinator, self.entity_description.key)

    @property
    def is_on(self) -> bool | None:
        """Return target state only for a protocol such as 16:8."""

        return fasting_metrics(self.coordinator.data.fasting).get("goal_reached")


class SparkyFitnessHabitBinarySensor(SparkyFitnessEntity, BinarySensorEntity):
    """Whether one SparkyFitness habit is completed today."""

    _attr_icon = "mdi:checkbox-marked-circle-outline"

    def __init__(self, coordinator, habit_id: str, name: str) -> None:
        """Initialize one dynamically discovered habit."""

        super().__init__(coordinator, f"habit_{habit_id}")
        self._habit_id = habit_id
        self._attr_name = name

    @property
    def available(self) -> bool:
        """Mark removed habits unavailable while retaining registry identity."""

        return super().available and self._habit_id in self.coordinator.data.habits

    @property
    def is_on(self) -> bool:
        """Return true only for an explicit completion today."""

        habit = self.coordinator.data.habits.get(self._habit_id) or {}
        return habit.get("completed") is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the stable ID required by the existing log action."""

        habit = self.coordinator.data.habits.get(self._habit_id) or {}
        return {
            "habit_id": self._habit_id,
            "logged_today": habit.get("completed") is not None,
        }
