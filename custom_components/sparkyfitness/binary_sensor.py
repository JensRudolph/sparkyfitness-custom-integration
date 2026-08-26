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
from homeassistant.helpers import entity_registry as er
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

    habit_entities: dict[str, SparkyFitnessHabitBinarySensor] = {}

    async def async_remove_habit(
        habit_id: str, entity: SparkyFitnessHabitBinarySensor
    ) -> None:
        """Remove an entity after an authoritative catalog deletion."""

        entity_id = entity.entity_id
        await entity.async_remove()
        if entity_id:
            registry = er.async_get(hass)
            if registry.async_get(entity_id):
                registry.async_remove(entity_id)

    @callback
    def async_add_new_habits() -> None:
        """Add newly discovered habits without persisting their history."""

        current_ids = set(coordinator.data.habits)
        new_ids = current_ids - set(habit_entities)
        entities = [
            SparkyFitnessHabitBinarySensor(
                coordinator,
                habit_id,
            )
            for habit_id in sorted(new_ids)
        ]
        if entities:
            habit_entities.update(
                {entity.habit_id: entity for entity in entities}
            )
            async_add_entities(entities)
        for habit_id in set(habit_entities) - current_ids:
            entity = habit_entities.pop(habit_id)
            hass.async_create_task(
                async_remove_habit(habit_id, entity),
                f"Remove deleted SparkyFitness habit {habit_id}",
            )

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

    def __init__(self, coordinator, habit_id: str) -> None:
        """Initialize one dynamically discovered habit."""

        super().__init__(coordinator, f"habit_{habit_id}")
        self._habit_id = habit_id

    @property
    def habit_id(self) -> str:
        """Return the stable source identifier."""

        return self._habit_id

    @property
    def name(self) -> str:
        """Follow upstream habit renames without recreating the entity."""

        habit = self.coordinator.data.habits.get(self._habit_id) or {}
        return str(habit.get("name") or "Habit")

    @property
    def available(self) -> bool:
        """Mark removed habits unavailable while retaining registry identity."""

        habit = self.coordinator.data.habits.get(self._habit_id)
        return (
            super().available
            and habit is not None
            and habit.get("history_available", True)
        )

    @property
    def is_on(self) -> bool | None:
        """Return true only for an explicit completion today."""

        habit = self.coordinator.data.habits.get(self._habit_id) or {}
        completed = habit.get("completed")
        if habit.get("history_available", True) is False and not isinstance(
            completed, bool
        ):
            return None
        return completed is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the stable ID required by the existing log action."""

        habit = self.coordinator.data.habits.get(self._habit_id) or {}
        return {
            "habit_id": self._habit_id,
            "logged_today": habit.get("completed") is not None,
        }
