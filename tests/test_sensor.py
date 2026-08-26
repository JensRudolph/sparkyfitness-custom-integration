"""Tests for capability-gated sensor descriptions."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.sparkyfitness.const import (
    CONF_ENABLE_GOALS,
    CONF_ENABLE_TRENDS,
    TOOL_30_DAY_TRENDS,
    TOOL_GOAL_SNAPSHOT,
    TOOL_HEALTH_SUMMARY,
    TOOL_NUTRITION_SUMMARY,
)
from custom_components.sparkyfitness.models import SparkyFitnessData
from custom_components.sparkyfitness.sensor import (
    HABIT_ANALYTICS_SENSORS,
    SENSORS,
    SparkyFitnessFailedSectionsSensor,
    SparkyFitnessHabitAnalyticsSensor,
    SparkyFitnessLastSuccessfulRefreshSensor,
)

HABIT_ID = "11111111-1111-1111-1111-111111111111"


def test_goal_and_trend_sensors_are_capability_gated() -> None:
    """Aggregate entities require both their tool and feature option."""

    descriptions = {description.key: description for description in SENSORS}
    for key in (
        "calorie_goal",
        "protein_goal",
        "carbs_goal",
        "fat_goal",
        "water_goal",
    ):
        assert descriptions[key].required_tools == frozenset({TOOL_GOAL_SNAPSHOT})
        assert descriptions[key].feature_option == CONF_ENABLE_GOALS

    for key in (
        "food_days_logged_30d",
        "avg_daily_calories_30d",
        "avg_daily_protein_30d",
        "workouts_30d",
        "active_days_30d",
        "exercise_calories_30d",
        "avg_mood_30d",
        "avg_sleep_duration_30d",
        "avg_sleep_score_30d",
        "weight_entries_30d",
    ):
        assert descriptions[key].required_tools == frozenset({TOOL_30_DAY_TRENDS})
        assert descriptions[key].feature_option == CONF_ENABLE_TRENDS


def test_goal_progress_sensors_require_both_source_tools() -> None:
    """Derived progress is opt-in and never created from a partial source set."""

    descriptions = {description.key: description for description in SENSORS}
    progress = descriptions["calories_progress"]
    remaining = descriptions["water_remaining"]
    assert progress.required_tools == frozenset(
        {TOOL_NUTRITION_SUMMARY, TOOL_GOAL_SNAPSHOT}
    )
    assert remaining.required_tools == frozenset(
        {TOOL_HEALTH_SUMMARY, TOOL_GOAL_SNAPSHOT}
    )
    assert progress.require_all_tools is True
    assert progress.entity_registry_enabled_default is False
    assert progress.value_fn({"calories_today": 1800, "calorie_goal": 2000}) == 90
    assert remaining.value_fn({"water_today": 1750, "water_goal": 2500}) == 750
    assert remaining.value_fn({"water_today": 3000, "water_goal": 2500}) == 0


def test_optional_micronutrient_sensors_are_disabled_by_default() -> None:
    """Detailed nutrition sensors remain available without cluttering new setups."""

    descriptions = {description.key: description for description in SENSORS}
    for key in ("fiber_today", "sugar_today", "sodium_today", "potassium_today"):
        description = descriptions[key]
        assert description.required_tools == frozenset({TOOL_NUTRITION_SUMMARY})
        assert description.entity_registry_enabled_default is False


def test_habit_analytics_are_optional_named_and_auditable() -> None:
    """Dynamic metrics expose their tracked-day denominator and follow renames."""

    coordinator = MagicMock()
    coordinator.config_entry = SimpleNamespace(entry_id="entry-1", options={}, data={})
    coordinator.client.server_version = "1.6.3"
    coordinator.client.endpoint = "https://sparky.example.com/mcp"
    coordinator.last_update_success = True
    coordinator.data = SparkyFitnessData(
        habits={
            HABIT_ID: {
                "name": "Walk",
                "completion_rate_7d": 75.0,
                "completed_days_7d": 3,
                "tracked_days_7d": 4,
                "analytics_available": True,
            }
        }
    )
    description = next(
        item for item in HABIT_ANALYTICS_SENSORS if item.key == "completion_7d"
    )
    entity = SparkyFitnessHabitAnalyticsSensor(coordinator, HABIT_ID, description)

    assert description.entity_registry_enabled_default is False
    assert entity.translation_placeholders == {"habit_name": "Walk"}
    assert entity.native_value == 75.0
    assert entity.extra_state_attributes == {
        "habit_id": HABIT_ID,
        "completed_days": 3,
        "tracked_days": 4,
    }


def test_optional_diagnostic_sensors_keep_technical_state_auditable() -> None:
    """Diagnostics expose timestamps and section errors without health values."""

    coordinator = MagicMock()
    coordinator.config_entry = SimpleNamespace(entry_id="entry-1", options={}, data={})
    coordinator.client.server_version = "1.6.3"
    coordinator.client.endpoint = "https://sparky.example.com/mcp"
    coordinator.last_update_success = False
    coordinator.last_successful_refresh = datetime(2026, 8, 26, tzinfo=UTC)
    coordinator.data = SparkyFitnessData(
        section_errors={"nutrition": "SparkyFitnessConnectionError"}
    )

    refresh = SparkyFitnessLastSuccessfulRefreshSensor(coordinator)
    failures = SparkyFitnessFailedSectionsSensor(coordinator)

    assert refresh.available is True
    assert refresh.native_value == coordinator.last_successful_refresh
    assert failures.native_value == 1
    assert failures.extra_state_attributes == {
        "sections": {"nutrition": "SparkyFitnessConnectionError"}
    }
