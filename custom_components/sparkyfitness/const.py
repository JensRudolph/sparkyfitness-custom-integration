"""Constants for the SparkyFitness integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "sparkyfitness"
NAME: Final = "SparkyFitness"
INTEGRATION_VERSION: Final = "0.2.0"

PLATFORMS: Final = ["sensor", "binary_sensor"]

CONF_API_KEY: Final = "api_key"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_UPDATE_INTERVAL: Final = "update_interval"
CONF_ENABLE_NUTRITION: Final = "enable_nutrition"
CONF_ENABLE_EXERCISE: Final = "enable_exercise"
CONF_ENABLE_CHECKIN: Final = "enable_checkin"
CONF_ENABLE_ENGAGEMENT: Final = "enable_engagement"
CONF_ENABLE_GOALS: Final = "enable_goals"
CONF_ENABLE_TRENDS: Final = "enable_trends"
CONF_CONFIG_ENTRY_ID: Final = "config_entry_id"

DEFAULT_VERIFY_SSL: Final = True
DEFAULT_UPDATE_INTERVAL: Final = 5
MIN_UPDATE_INTERVAL: Final = 1
MAX_UPDATE_INTERVAL: Final = 60
DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=DEFAULT_UPDATE_INTERVAL)
REQUEST_TIMEOUT_SECONDS: Final = 30
MCP_PROTOCOL_VERSION: Final = "2025-11-25"

EXPECTED_TOOLS: Final = frozenset(
    {
        "sparky_manage_food",
        "sparky_manage_exercise",
        "sparky_manage_checkin",
    }
)

TOOL_HEALTH_SUMMARY: Final = "sparky_get_health_summary"
TOOL_DAILY_REPORT: Final = "sparky_get_daily_report"
TOOL_CHECKIN: Final = "sparky_manage_checkin"
TOOL_FOOD: Final = "sparky_manage_food"
TOOL_EXERCISE: Final = "sparky_manage_exercise"
TOOL_STREAK: Final = "sparky_get_logging_streak"
TOOL_GOAL_SNAPSHOT: Final = "sparky_get_goal_snapshot"
TOOL_30_DAY_TRENDS: Final = "sparky_get_30_day_trends"
TOOL_PROFILE: Final = "sparky_manage_profile"
TOOL_GOALS: Final = "sparky_manage_goals"
TOOL_HABITS: Final = "sparky_manage_habits"

SERVICE_REFRESH: Final = "refresh"
SERVICE_LOG_WEIGHT: Final = "log_weight"
SERVICE_LOG_BIOMETRICS: Final = "log_biometrics"
SERVICE_LOG_WATER: Final = "log_water"
SERVICE_LOG_MOOD: Final = "log_mood"
SERVICE_LOG_SLEEP: Final = "log_sleep"
SERVICE_LOG_CUSTOM_METRIC: Final = "log_custom_metric"
SERVICE_LOG_FOOD: Final = "log_food"
SERVICE_LOG_EXERCISE: Final = "log_exercise"
SERVICE_CREATE_EXERCISE: Final = "create_exercise"
SERVICE_CREATE_WORKOUT_PRESET: Final = "create_workout_preset"
SERVICE_LOG_WORKOUT_PRESET: Final = "log_workout_preset"
SERVICE_SET_GOALS: Final = "set_goals"
SERVICE_LOG_HABIT: Final = "log_habit"
SERVICE_UPDATE_FOOD_ENTRY: Final = "update_food_entry"
SERVICE_DELETE_FOOD_ENTRY: Final = "delete_food_entry"
SERVICE_UPDATE_EXERCISE_ENTRY: Final = "update_exercise_entry"
SERVICE_DELETE_EXERCISE_ENTRY: Final = "delete_exercise_entry"
SERVICE_START_FASTING: Final = "start_fasting"
SERVICE_LOG_FASTING_WINDOW: Final = "log_fasting_window"

SET_TYPES: Final = ("Working Set", "Warmup", "Drop Set", "Failure")
MEAL_TYPES: Final = ("breakfast", "lunch", "dinner", "snacks")

ATTRIBUTION: Final = "Data provided by SparkyFitness"
