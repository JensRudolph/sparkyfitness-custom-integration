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
    UnitOfEnergy,
    UnitOfMass,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_ENABLE_CHECKIN,
    CONF_ENABLE_ENGAGEMENT,
    CONF_ENABLE_EXERCISE,
    CONF_ENABLE_GOALS,
    CONF_ENABLE_NUTRITION,
    CONF_ENABLE_TRENDS,
    TOOL_30_DAY_TRENDS,
    TOOL_CHECKIN,
    TOOL_GOAL_SNAPSHOT,
    TOOL_HEALTH_SUMMARY,
    TOOL_STREAK,
)
from .entity import SparkyFitnessEntity


@dataclass(frozen=True, kw_only=True)
class SparkyFitnessSensorDescription(SensorEntityDescription):
    """Describe a conditional SparkyFitness sensor."""

    required_tools: frozenset[str]
    feature_option: str
    value_fn: Callable[[dict[str, Any]], Any]


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
        required_tools=frozenset({TOOL_HEALTH_SUMMARY}),
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
            required_tools=frozenset({TOOL_HEALTH_SUMMARY}),
            feature_option=CONF_ENABLE_NUTRITION,
            value_fn=lambda data, value_key=key: data.get(value_key),
        )
        for key, icon in (
            ("protein_today", "mdi:food-drumstick"),
            ("carbs_today", "mdi:barley"),
            ("fat_today", "mdi:oil"),
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
        device_class=SensorDeviceClass.ENERGY,
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
        device_class=SensorDeviceClass.ENERGY,
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
        device_class=SensorDeviceClass.ENERGY,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up dynamically supported sensors."""

    coordinator = entry.runtime_data.coordinator
    available_tools = coordinator.client.tools.keys()
    async_add_entities(
        SparkyFitnessSensor(coordinator, description)
        for description in SENSORS
        if description.required_tools.intersection(available_tools)
        and coordinator.feature_enabled(description.feature_option)
    )


class SparkyFitnessSensor(SparkyFitnessEntity, SensorEntity):
    """A coordinator-backed SparkyFitness sensor."""

    entity_description: SparkyFitnessSensorDescription

    def __init__(
        self, coordinator, description: SparkyFitnessSensorDescription
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        """Return the latest value without converting missing data to zero."""

        return self.entity_description.value_fn(self.coordinator.data.values)
