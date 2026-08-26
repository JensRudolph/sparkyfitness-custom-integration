"""Tests for capability-gated sensor descriptions."""

from custom_components.sparkyfitness.const import (
    CONF_ENABLE_GOALS,
    CONF_ENABLE_TRENDS,
    TOOL_30_DAY_TRENDS,
    TOOL_GOAL_SNAPSHOT,
)
from custom_components.sparkyfitness.sensor import SENSORS


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
    assert progress.require_all_tools is True
    assert progress.entity_registry_enabled_default is False
    assert progress.value_fn({"calories_today": 1800, "calorie_goal": 2000}) == 90
    assert remaining.value_fn({"water_today": 1750, "water_goal": 2500}) == 750
    assert remaining.value_fn({"water_today": 3000, "water_goal": 2500}) == 0
