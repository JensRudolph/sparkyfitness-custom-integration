"""Sensor platform for SparkyFitness."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_ENABLE_CHECKIN,
    CONF_ENABLE_ENGAGEMENT,
    CONF_ENABLE_EXERCISE,
    CONF_ENABLE_GOALS,
    CONF_ENABLE_HABITS,
    CONF_ENABLE_NUTRITION,
    CONF_ENABLE_TRENDS,
    DOMAIN,
    TOOL_30_DAY_TRENDS,
    TOOL_CHECKIN,
    TOOL_GOAL_SNAPSHOT,
    TOOL_HABITS,
    TOOL_HEALTH_SUMMARY,
    TOOL_NUTRITION_SUMMARY,
    TOOL_STREAK,
)
from .entity import SparkyFitnessEntity
from .fasting import fasting_metrics


@dataclass(frozen=True, kw_only=True)
class SparkyFitnessSensorDescription(SensorEntityDescription):
    """Describe a conditional SparkyFitness sensor."""

    required_tools: frozenset[str]
    feature_option: str
    value_fn: Callable[[dict[str, Any]], Any]
    require_all_tools: bool = False
    additional_feature_options: frozenset[str] = frozenset()


@dataclass(frozen=True, kw_only=True)
class SparkyFitnessFastingSensorDescription(SensorEntityDescription):
    """Describe a value calculated from the active fasting status."""

    metric_key: str


@dataclass(frozen=True, kw_only=True)
class SparkyFitnessHabitAnalyticsDescription(SensorEntityDescription):
    """Describe one optional analytical value for every habit."""

    metric_key: str


_TOOL_SECTIONS = {
    TOOL_HEALTH_SUMMARY: "summary",
    TOOL_NUTRITION_SUMMARY: "nutrition",
    TOOL_CHECKIN: "checkin",
    TOOL_STREAK: "streak",
    TOOL_GOAL_SNAPSHOT: "goals",
    TOOL_30_DAY_TRENDS: "trends",
}


def _remaining(data: dict[str, Any], current_key: str, goal_key: str) -> Any:
    """Return a non-negative remaining amount when both inputs exist."""

    current = data.get(current_key)
    goal = data.get(goal_key)
    if current is None or goal is None:
        return None
    return round(max(0.0, float(goal) - float(current)), 2)


def _progress(data: dict[str, Any], current_key: str, goal_key: str) -> Any:
    """Return goal progress without capping values above 100 percent."""

    current = data.get(current_key)
    goal = data.get(goal_key)
    if current is None or goal is None or float(goal) <= 0:
        return None
    return round(float(current) / float(goal) * 100, 1)


SENSORS: tuple[SparkyFitnessSensorDescription, ...] = (
    SparkyFitnessSensorDescription(
        key="weight",
        translation_key="weight",
        icon="mdi:scale-bathroom",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_HEALTH_SUMMARY, TOOL_CHECKIN}),
        feature_option=CONF_ENABLE_CHECKIN,
        value_fn=lambda data: data.get("weight"),
    ),
    SparkyFitnessSensorDescription(
        key="steps_today",
        translation_key="steps_today",
        icon="mdi:walk",
        state_class=SensorStateClass.TOTAL,
        required_tools=frozenset({TOOL_CHECKIN}),
        feature_option=CONF_ENABLE_CHECKIN,
        value_fn=lambda data: data.get("steps_today"),
    ),
    SparkyFitnessSensorDescription(
        key="calories_today",
        translation_key="calories_today",
        icon="mdi:fire",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        state_class=SensorStateClass.TOTAL,
        required_tools=frozenset({TOOL_NUTRITION_SUMMARY}),
        feature_option=CONF_ENABLE_NUTRITION,
        value_fn=lambda data: data.get("calories_today"),
    ),
    *(
        SparkyFitnessSensorDescription(
            key=key,
            translation_key=key,
            icon=icon,
            native_unit_of_measurement=UnitOfMass.GRAMS,
            state_class=SensorStateClass.TOTAL,
            required_tools=frozenset({TOOL_NUTRITION_SUMMARY}),
            feature_option=CONF_ENABLE_NUTRITION,
            value_fn=lambda data, value_key=key: data.get(value_key),
        )
        for key, icon in (
            ("protein_today", "mdi:food-drumstick"),
            ("carbs_today", "mdi:barley"),
            ("fat_today", "mdi:oil"),
        )
    ),
    *(
        SparkyFitnessSensorDescription(
            key=key,
            translation_key=key,
            icon=icon,
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.TOTAL,
            entity_registry_enabled_default=False,
            required_tools=frozenset({TOOL_NUTRITION_SUMMARY}),
            feature_option=CONF_ENABLE_NUTRITION,
            value_fn=lambda data, value_key=key: data.get(value_key),
        )
        for key, icon, unit in (
            ("fiber_today", "mdi:grain", UnitOfMass.GRAMS),
            ("sugar_today", "mdi:cube-outline", UnitOfMass.GRAMS),
            ("sodium_today", "mdi:shaker-outline", UnitOfMass.MILLIGRAMS),
            ("potassium_today", "mdi:food-apple-outline", UnitOfMass.MILLIGRAMS),
        )
    ),
    SparkyFitnessSensorDescription(
        key="water_today",
        translation_key="water_today",
        icon="mdi:cup-water",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.TOTAL,
        required_tools=frozenset({TOOL_HEALTH_SUMMARY}),
        feature_option=CONF_ENABLE_NUTRITION,
        value_fn=lambda data: data.get("water_today"),
    ),
    SparkyFitnessSensorDescription(
        key="sleep_duration",
        translation_key="sleep_duration",
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_CHECKIN}),
        feature_option=CONF_ENABLE_CHECKIN,
        value_fn=lambda data: data.get("sleep_duration"),
    ),
    SparkyFitnessSensorDescription(
        key="sleep_score",
        translation_key="sleep_score",
        icon="mdi:sleep",
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_CHECKIN}),
        feature_option=CONF_ENABLE_CHECKIN,
        value_fn=lambda data: data.get("sleep_score"),
    ),
    SparkyFitnessSensorDescription(
        key="mood",
        translation_key="mood",
        icon="mdi:emoticon-happy-outline",
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_CHECKIN}),
        feature_option=CONF_ENABLE_CHECKIN,
        value_fn=lambda data: data.get("mood"),
    ),
    SparkyFitnessSensorDescription(
        key="body_fat",
        translation_key="body_fat",
        icon="mdi:human",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_CHECKIN}),
        feature_option=CONF_ENABLE_CHECKIN,
        value_fn=lambda data: data.get("body_fat"),
    ),
    SparkyFitnessSensorDescription(
        key="exercise_count_today",
        translation_key="exercise_count_today",
        icon="mdi:dumbbell",
        state_class=SensorStateClass.TOTAL,
        required_tools=frozenset({TOOL_HEALTH_SUMMARY}),
        feature_option=CONF_ENABLE_EXERCISE,
        value_fn=lambda data: data.get("exercise_count_today"),
    ),
    SparkyFitnessSensorDescription(
        key="logging_streak",
        translation_key="logging_streak",
        icon="mdi:calendar-check",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_STREAK}),
        feature_option=CONF_ENABLE_ENGAGEMENT,
        value_fn=lambda data: data.get("logging_streak"),
    ),
    SparkyFitnessSensorDescription(
        key="calorie_goal",
        translation_key="calorie_goal",
        icon="mdi:target",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_GOAL_SNAPSHOT}),
        feature_option=CONF_ENABLE_GOALS,
        value_fn=lambda data: data.get("calorie_goal"),
    ),
    *(
        SparkyFitnessSensorDescription(
            key=key,
            translation_key=key,
            icon="mdi:target",
            native_unit_of_measurement=UnitOfMass.GRAMS,
            state_class=SensorStateClass.MEASUREMENT,
            required_tools=frozenset({TOOL_GOAL_SNAPSHOT}),
            feature_option=CONF_ENABLE_GOALS,
            value_fn=lambda data, value_key=key: data.get(value_key),
        )
        for key in ("protein_goal", "carbs_goal", "fat_goal")
    ),
    SparkyFitnessSensorDescription(
        key="water_goal",
        translation_key="water_goal",
        icon="mdi:cup-water",
        native_unit_of_measurement=UnitOfVolume.MILLILITERS,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_GOAL_SNAPSHOT}),
        feature_option=CONF_ENABLE_GOALS,
        value_fn=lambda data: data.get("water_goal"),
    ),
    *(
        SparkyFitnessSensorDescription(
            key=f"{key}_remaining",
            translation_key=f"{key}_remaining",
            icon=icon,
            device_class=device_class,
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            required_tools=frozenset({current_tool, TOOL_GOAL_SNAPSHOT}),
            feature_option=CONF_ENABLE_GOALS,
            additional_feature_options=frozenset({CONF_ENABLE_NUTRITION}),
            require_all_tools=True,
            value_fn=lambda data, current_key=current_key, goal_key=goal_key: (
                _remaining(data, current_key, goal_key)
            ),
        )
        for key, current_key, goal_key, icon, unit, device_class, current_tool in (
            (
                "calories",
                "calories_today",
                "calorie_goal",
                "mdi:fire",
                UnitOfEnergy.KILO_CALORIE,
                None,
                TOOL_NUTRITION_SUMMARY,
            ),
            (
                "protein",
                "protein_today",
                "protein_goal",
                "mdi:food-drumstick",
                UnitOfMass.GRAMS,
                None,
                TOOL_NUTRITION_SUMMARY,
            ),
            (
                "carbs",
                "carbs_today",
                "carbs_goal",
                "mdi:barley",
                UnitOfMass.GRAMS,
                None,
                TOOL_NUTRITION_SUMMARY,
            ),
            (
                "fat",
                "fat_today",
                "fat_goal",
                "mdi:oil",
                UnitOfMass.GRAMS,
                None,
                TOOL_NUTRITION_SUMMARY,
            ),
            (
                "water",
                "water_today",
                "water_goal",
                "mdi:cup-water",
                UnitOfVolume.MILLILITERS,
                None,
                TOOL_HEALTH_SUMMARY,
            ),
        )
    ),
    *(
        SparkyFitnessSensorDescription(
            key=f"{key}_progress",
            translation_key=f"{key}_progress",
            icon="mdi:progress-check",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
            required_tools=frozenset({current_tool, TOOL_GOAL_SNAPSHOT}),
            feature_option=CONF_ENABLE_GOALS,
            additional_feature_options=frozenset({CONF_ENABLE_NUTRITION}),
            require_all_tools=True,
            value_fn=lambda data, current_key=current_key, goal_key=goal_key: _progress(
                data, current_key, goal_key
            ),
        )
        for key, current_key, goal_key, current_tool in (
            ("calories", "calories_today", "calorie_goal", TOOL_NUTRITION_SUMMARY),
            ("protein", "protein_today", "protein_goal", TOOL_NUTRITION_SUMMARY),
            ("carbs", "carbs_today", "carbs_goal", TOOL_NUTRITION_SUMMARY),
            ("fat", "fat_today", "fat_goal", TOOL_NUTRITION_SUMMARY),
            ("water", "water_today", "water_goal", TOOL_HEALTH_SUMMARY),
        )
    ),
    SparkyFitnessSensorDescription(
        key="food_days_logged_30d",
        translation_key="food_days_logged_30d",
        icon="mdi:calendar-check",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_30_DAY_TRENDS}),
        feature_option=CONF_ENABLE_TRENDS,
        value_fn=lambda data: data.get("food_days_logged_30d"),
    ),
    SparkyFitnessSensorDescription(
        key="avg_daily_calories_30d",
        translation_key="avg_daily_calories_30d",
        icon="mdi:chart-line",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_30_DAY_TRENDS}),
        feature_option=CONF_ENABLE_TRENDS,
        value_fn=lambda data: data.get("avg_daily_calories_30d"),
    ),
    SparkyFitnessSensorDescription(
        key="avg_daily_protein_30d",
        translation_key="avg_daily_protein_30d",
        icon="mdi:chart-line",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_30_DAY_TRENDS}),
        feature_option=CONF_ENABLE_TRENDS,
        value_fn=lambda data: data.get("avg_daily_protein_30d"),
    ),
    *(
        SparkyFitnessSensorDescription(
            key=key,
            translation_key=key,
            icon=icon,
            state_class=SensorStateClass.MEASUREMENT,
            required_tools=frozenset({TOOL_30_DAY_TRENDS}),
            feature_option=CONF_ENABLE_TRENDS,
            value_fn=lambda data, value_key=key: data.get(value_key),
        )
        for key, icon in (
            ("workouts_30d", "mdi:dumbbell"),
            ("avg_mood_30d", "mdi:emoticon-happy-outline"),
            ("avg_sleep_score_30d", "mdi:sleep"),
            ("weight_entries_30d", "mdi:scale-bathroom"),
        )
    ),
    SparkyFitnessSensorDescription(
        key="active_days_30d",
        translation_key="active_days_30d",
        icon="mdi:calendar-check",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_30_DAY_TRENDS}),
        feature_option=CONF_ENABLE_TRENDS,
        value_fn=lambda data: data.get("active_days_30d"),
    ),
    SparkyFitnessSensorDescription(
        key="exercise_calories_30d",
        translation_key="exercise_calories_30d",
        icon="mdi:fire",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_30_DAY_TRENDS}),
        feature_option=CONF_ENABLE_TRENDS,
        value_fn=lambda data: data.get("exercise_calories_30d"),
    ),
    SparkyFitnessSensorDescription(
        key="avg_sleep_duration_30d",
        translation_key="avg_sleep_duration_30d",
        icon="mdi:sleep",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        required_tools=frozenset({TOOL_30_DAY_TRENDS}),
        feature_option=CONF_ENABLE_TRENDS,
        value_fn=lambda data: data.get("avg_sleep_duration_30d"),
    ),
)

FASTING_SENSORS: tuple[SparkyFitnessFastingSensorDescription, ...] = (
    SparkyFitnessFastingSensorDescription(
        key="fasting_elapsed",
        translation_key="fasting_elapsed",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        metric_key="elapsed_seconds",
    ),
    SparkyFitnessFastingSensorDescription(
        key="fasting_target_end",
        translation_key="fasting_target_end",
        icon="mdi:timer-check-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        metric_key="target_end",
    ),
    SparkyFitnessFastingSensorDescription(
        key="fasting_remaining",
        translation_key="fasting_remaining",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        metric_key="remaining_seconds",
    ),
    SparkyFitnessFastingSensorDescription(
        key="fasting_progress",
        translation_key="fasting_progress",
        icon="mdi:progress-clock",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        metric_key="progress",
    ),
)

HABIT_ANALYTICS_SENSORS: tuple[SparkyFitnessHabitAnalyticsDescription, ...] = (
    SparkyFitnessHabitAnalyticsDescription(
        key="completion_7d",
        translation_key="habit_completion_7d",
        icon="mdi:calendar-week",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        metric_key="completion_rate_7d",
    ),
    SparkyFitnessHabitAnalyticsDescription(
        key="completion_30d",
        translation_key="habit_completion_30d",
        icon="mdi:calendar-month",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        metric_key="completion_rate_30d",
    ),
    SparkyFitnessHabitAnalyticsDescription(
        key="streak",
        translation_key="habit_streak",
        icon="mdi:calendar-check",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        metric_key="habit_streak",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up dynamically supported sensors."""

    coordinator = entry.runtime_data.coordinator
    available_tools = coordinator.client.tools.keys()
    supported_sensors = [
        SparkyFitnessSensor(coordinator, description)
        for description in SENSORS
        if (
            description.required_tools.issubset(available_tools)
            if description.require_all_tools
            else bool(description.required_tools.intersection(available_tools))
        )
        and coordinator.feature_enabled(description.feature_option)
        and all(
            coordinator.feature_enabled(option)
            for option in description.additional_feature_options
        )
    ]
    async_add_entities(supported_sensors)
    if TOOL_CHECKIN in available_tools and coordinator.feature_enabled(
        CONF_ENABLE_CHECKIN
    ):
        async_add_entities(
            SparkyFitnessFastingSensor(coordinator, description)
            for description in FASTING_SENSORS
        )

    diagnostic_entities: list[SensorEntity] = [
        SparkyFitnessLastSuccessfulRefreshSensor(coordinator),
        SparkyFitnessFailedSectionsSensor(coordinator),
    ]
    async_add_entities(diagnostic_entities)

    if TOOL_HABITS not in available_tools or not coordinator.feature_enabled(
        CONF_ENABLE_HABITS
    ):
        return

    habit_entities: dict[tuple[str, str], SparkyFitnessHabitAnalyticsSensor] = {}

    async def async_remove_habit_analytics(
        entity: SparkyFitnessHabitAnalyticsSensor,
    ) -> None:
        """Remove disabled or enabled analytics after a catalog deletion."""

        if entity.hass is not None and entity.entity_id:
            await entity.async_remove()
        registry = er.async_get(hass)
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, entity.unique_id)
        if entity_id:
            registry.async_remove(entity_id)

    @callback
    def async_sync_habit_analytics() -> None:
        """Create optional analytics for new habits and remove deleted ones."""

        current_ids = set(coordinator.data.habits)
        wanted = {
            (habit_id, description.key)
            for habit_id in current_ids
            for description in HABIT_ANALYTICS_SENSORS
        }
        new_entities = [
            SparkyFitnessHabitAnalyticsSensor(coordinator, habit_id, description)
            for habit_id, metric_key in sorted(wanted - set(habit_entities))
            for description in HABIT_ANALYTICS_SENSORS
            if description.key == metric_key
        ]
        if new_entities:
            habit_entities.update(
                {
                    (entity.habit_id, entity.entity_description.key): entity
                    for entity in new_entities
                }
            )
            async_add_entities(new_entities)
        for key in set(habit_entities) - wanted:
            entity = habit_entities.pop(key)
            hass.async_create_task(
                async_remove_habit_analytics(entity),
                f"Remove deleted SparkyFitness habit analytics {key[0]}",
            )

    async_sync_habit_analytics()
    entry.async_on_unload(coordinator.async_add_listener(async_sync_habit_analytics))


class SparkyFitnessSensor(SparkyFitnessEntity, SensorEntity):
    """A coordinator-backed SparkyFitness sensor."""

    entity_description: SparkyFitnessSensorDescription

    def __init__(
        self, coordinator, description: SparkyFitnessSensorDescription
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, description.key)
        self.entity_description = description
        coordinator.register_poll_demand(
            "sensor",
            description.key,
            frozenset(
                _TOOL_SECTIONS[tool]
                for tool in description.required_tools
                if tool in _TOOL_SECTIONS
            ),
            enabled_default=description.entity_registry_enabled_default,
        )

    @property
    def native_value(self) -> Any:
        """Return the latest value without converting missing data to zero."""

        return self.entity_description.value_fn(self.coordinator.data.values)


class SparkyFitnessFastingSensor(SparkyFitnessEntity, SensorEntity):
    """Expose locally calculated metrics for the active fast."""

    entity_description: SparkyFitnessFastingSensorDescription

    def __init__(
        self, coordinator, description: SparkyFitnessFastingSensorDescription
    ) -> None:
        """Initialize a fasting metric sensor."""

        super().__init__(coordinator, description.key)
        self.entity_description = description
        coordinator.register_poll_demand(
            "sensor",
            description.key,
            frozenset({"fasting"}),
            enabled_default=description.entity_registry_enabled_default,
        )

    @property
    def native_value(self) -> Any:
        """Return a value only when it follows from the existing MCP status."""

        return fasting_metrics(self.coordinator.data.fasting).get(
            self.entity_description.metric_key
        )


class SparkyFitnessHabitAnalyticsSensor(SparkyFitnessEntity, SensorEntity):
    """Expose an optional cached completion metric for one habit."""

    entity_description: SparkyFitnessHabitAnalyticsDescription

    def __init__(self, coordinator, habit_id: str, description) -> None:
        """Initialize a disabled-by-default habit analytics sensor."""

        super().__init__(coordinator, f"habit_{habit_id}_{description.key}")
        self._habit_id = habit_id
        self.entity_description = description

    @property
    def habit_id(self) -> str:
        """Return the stable source habit ID."""

        return self._habit_id

    @property
    def translation_placeholders(self) -> dict[str, str]:
        """Keep the translated entity name synchronized with habit renames."""

        habit = self.coordinator.data.habits.get(self._habit_id) or {}
        return {"habit_name": str(habit.get("name") or "Habit")}

    @property
    def available(self) -> bool:
        """Expose analytics failures without affecting today's binary state."""

        habit = self.coordinator.data.habits.get(self._habit_id)
        return (
            super().available
            and habit is not None
            and habit.get("analytics_available", True)
        )

    @property
    def native_value(self) -> Any:
        """Return the cached transparent habit metric."""

        habit = self.coordinator.data.habits.get(self._habit_id) or {}
        return habit.get(self.entity_description.metric_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose denominators so completion rates remain auditable."""

        habit = self.coordinator.data.habits.get(self._habit_id) or {}
        attributes: dict[str, Any] = {"habit_id": self._habit_id}
        if self.entity_description.key == "completion_7d":
            attributes.update(
                completed_days=habit.get("completed_days_7d"),
                tracked_days=habit.get("tracked_days_7d"),
            )
        elif self.entity_description.key == "completion_30d":
            attributes.update(
                completed_days=habit.get("completed_days_30d"),
                tracked_days=habit.get("tracked_days_30d"),
            )
        else:
            attributes["latest_tracked_date"] = habit.get("latest_tracked_date")
        return attributes


class SparkyFitnessLastSuccessfulRefreshSensor(SparkyFitnessEntity, SensorEntity):
    """Expose the last successful MCP refresh as an optional diagnostic."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "last_successful_refresh"
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator) -> None:
        """Initialize the diagnostic sensor."""

        super().__init__(coordinator, "last_successful_refresh")

    @property
    def available(self) -> bool:
        """Keep the last known success visible during an outage."""

        return True

    @property
    def native_value(self) -> Any:
        """Return the technical refresh timestamp without health data."""

        return self.coordinator.last_successful_refresh


class SparkyFitnessFailedSectionsSensor(SparkyFitnessEntity, SensorEntity):
    """Expose the number and names of currently degraded polling sections."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "failed_polling_sections"
    _attr_icon = "mdi:alert-circle-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        """Initialize the diagnostic sensor."""

        super().__init__(coordinator, "failed_polling_sections")

    @property
    def native_value(self) -> int:
        """Return the number of partial failures."""

        return len(self.coordinator.data.section_errors)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose only technical section and exception class names."""

        return {"sections": dict(self.coordinator.data.section_errors)}
