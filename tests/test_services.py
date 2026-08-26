"""Tests for explicit Home Assistant write actions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.service import async_get_all_descriptions

from custom_components.sparkyfitness import async_setup
from custom_components.sparkyfitness.const import (
    DOMAIN,
    SERVICE_DELETE_EXERCISE_ENTRY,
    SERVICE_DELETE_FOOD_ENTRY,
    SERVICE_GET_HABIT_HISTORY,
    SERVICE_LIST_EXERCISE_DIARY,
    SERVICE_LIST_FOOD_DIARY,
    SERVICE_LIST_HABITS,
    SERVICE_LIST_WORKOUT_PRESETS,
    SERVICE_LOG_CUSTOM_METRIC,
    SERVICE_LOG_EXERCISE,
    SERVICE_LOG_FASTING_WINDOW,
    SERVICE_LOG_MOOD,
    SERVICE_LOG_WATER,
    SERVICE_LOG_WEIGHT,
    SERVICE_SEARCH_EXERCISE,
    SERVICE_SEARCH_FOOD,
    SERVICE_START_FASTING,
    SERVICE_UPDATE_EXERCISE_ENTRY,
    SERVICE_UPDATE_FOOD_ENTRY,
)

ENTRY_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
async def service_runtime(hass):
    """Register services and return an isolated mocked config-entry runtime."""

    await async_setup(hass, {})
    client = MagicMock()
    client.async_log_weight = AsyncMock(return_value="weight logged")
    client.async_log_water = AsyncMock(return_value="water logged")
    client.async_log_mood = AsyncMock(return_value="mood logged")
    client.async_log_custom_metric = AsyncMock(return_value="metric logged")
    client.async_log_exercise = AsyncMock(return_value="exercise logged")
    client.async_update_food_entry = AsyncMock(return_value="food updated")
    client.async_delete_food_entry = AsyncMock(return_value="food deleted")
    client.async_update_exercise_entry = AsyncMock(return_value="exercise updated")
    client.async_delete_exercise_entry = AsyncMock(return_value="exercise deleted")
    client.async_log_fasting = AsyncMock(return_value="fasting logged")
    client.async_list_food_diary = AsyncMock(
        return_value='{"entries":[{"id":"food-entry"}]}'
    )
    client.async_search_food = AsyncMock(return_value='{"items":[]}')
    client.async_list_exercise_diary = AsyncMock(return_value='{"entries":[]}')
    client.async_search_exercise = AsyncMock(return_value='{"items":[]}')
    client.async_list_workout_presets = AsyncMock(
        return_value="# Workout Presets\n\nNo results found."
    )
    client.async_list_habits = AsyncMock(
        return_value=f"# Available Habits\n\n**Walk**\n  ID: {ENTRY_ID}"
    )
    client.async_get_habit_history = AsyncMock(
        return_value="# Habit History\n\n2026-08-26: ✅ Completed"
    )
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    coordinator.invalidate_sections = MagicMock()
    entry = MagicMock()
    entry.runtime_data = SimpleNamespace(client=client, coordinator=coordinator)
    with patch(
        "custom_components.sparkyfitness.services._resolve_entry",
        return_value=entry,
    ):
        yield client, coordinator


async def _call(hass, service: str, data: dict) -> dict:
    return await hass.services.async_call(
        DOMAIN,
        service,
        data,
        blocking=True,
        return_response=True,
    )


async def test_all_registered_actions_have_valid_descriptions(hass) -> None:
    """Home Assistant can parse services.yaml and every registered action is documented."""

    await async_setup(hass, {})
    descriptions = await async_get_all_descriptions(hass)
    assert set(descriptions[DOMAIN]) == set(hass.services.async_services()[DOMAIN])


async def test_read_actions_return_results_without_refreshing(
    hass, service_runtime
) -> None:
    """Read-only mappings expose IDs transiently and never mutate coordinator data."""

    client, coordinator = service_runtime
    food_diary = await _call(hass, SERVICE_LIST_FOOD_DIARY, {"date": "2026-08-26"})
    await _call(hass, SERVICE_SEARCH_FOOD, {"query": "Oats", "limit": 10})
    await _call(
        hass,
        SERVICE_LIST_EXERCISE_DIARY,
        {"start_date": "2026-08-25", "end_date": "2026-08-26"},
    )
    await _call(
        hass,
        SERVICE_SEARCH_EXERCISE,
        {"query": "Press", "muscle_group": "Chest"},
    )
    await _call(hass, SERVICE_LIST_WORKOUT_PRESETS, {})
    habits = await _call(hass, SERVICE_LIST_HABITS, {})
    await _call(
        hass,
        SERVICE_GET_HABIT_HISTORY,
        {
            "habit_id": ENTRY_ID,
            "start_date": "2026-08-01",
            "end_date": "2026-08-26",
        },
    )

    assert food_diary == {"result": {"entries": [{"id": "food-entry"}]}}
    assert habits["result"].startswith("# Available Habits")
    client.async_list_food_diary.assert_awaited_once_with(date="2026-08-26")
    client.async_search_food.assert_awaited_once_with("Oats", limit=10, offset=0)
    client.async_list_exercise_diary.assert_awaited_once_with(
        start_date="2026-08-25", end_date="2026-08-26"
    )
    client.async_search_exercise.assert_awaited_once_with(
        "Press",
        muscle_group="Chest",
        equipment=None,
        limit=20,
        offset=0,
    )
    client.async_get_habit_history.assert_awaited_once_with(
        ENTRY_ID, start_date="2026-08-01", end_date="2026-08-26"
    )
    coordinator.async_request_refresh.assert_not_awaited()


async def test_log_weight(hass, service_runtime) -> None:
    """log_weight maps to log_biometrics with the exact MCP unit field."""

    client, coordinator = service_runtime
    response = await _call(
        hass,
        SERVICE_LOG_WEIGHT,
        {"weight": 84.7, "unit": "kg", "entry_date": "2026-08-26"},
    )
    client.async_log_weight.assert_awaited_once_with(84.7, "kg", "2026-08-26")
    coordinator.async_request_refresh.assert_awaited_once()
    assert response == {"result": "weight logged"}


async def test_log_water_converts_liters(hass, service_runtime) -> None:
    """The user-facing water unit is converted to MCP amount_ml."""

    client, coordinator = service_runtime
    await _call(
        hass,
        SERVICE_LOG_WATER,
        {"amount": 0.5, "unit": "l", "entry_date": "2026-08-26"},
    )
    client.async_log_water.assert_awaited_once_with(500.0, "2026-08-26")
    coordinator.async_request_refresh.assert_awaited_once()


async def test_log_mood(hass, service_runtime) -> None:
    """Mood uses current MCP names mood_value, notes, and mood_tags via wrapper."""

    client, coordinator = service_runtime
    await _call(
        hass,
        SERVICE_LOG_MOOD,
        {
            "mood": 8,
            "notes": "Very good day",
            "mood_tags": ["happy"],
            "entry_date": "2026-08-26",
        },
    )
    client.async_log_mood.assert_awaited_once_with(
        8,
        "2026-08-26",
        notes="Very good day",
        mood_tags=["happy"],
    )
    coordinator.async_request_refresh.assert_awaited_once()


async def test_log_custom_metric(hass, service_runtime) -> None:
    """Custom metrics preserve category, value, unit, and notes."""

    client, coordinator = service_runtime
    await _call(
        hass,
        SERVICE_LOG_CUSTOM_METRIC,
        {
            "name": "Resting Heart Rate",
            "value": 58,
            "unit": "bpm",
            "entry_date": "2026-08-26",
        },
    )
    client.async_log_custom_metric.assert_awaited_once_with(
        "Resting Heart Rate",
        58.0,
        "2026-08-26",
        unit="bpm",
        notes=None,
    )
    coordinator.async_request_refresh.assert_awaited_once()


async def test_log_exercise_with_structured_sets(hass, service_runtime) -> None:
    """Complex set objects are sent as an array, not serialized or invented."""

    client, coordinator = service_runtime
    sets = [
        {"reps": 10, "weight": 80, "set_type": "Working Set", "rpe": 8},
        {"reps": 9, "weight": 80, "set_type": "Working Set", "rpe": 9},
    ]
    await _call(
        hass,
        SERVICE_LOG_EXERCISE,
        {
            "exercise": "Bench Press",
            "notes": "Good session",
            "sets": sets,
            "entry_date": "2026-08-26",
        },
    )
    client.async_log_exercise.assert_awaited_once_with(
        exercise_name="Bench Press",
        entry_date="2026-08-26",
        notes="Good session",
        sets=sets,
    )
    coordinator.async_request_refresh.assert_awaited_once()


async def test_update_and_delete_food_entry_by_id(hass, service_runtime) -> None:
    """Food mutations require and preserve one exact diary entry UUID."""

    client, coordinator = service_runtime
    await _call(
        hass,
        SERVICE_UPDATE_FOOD_ENTRY,
        {"entry_id": ENTRY_ID, "quantity": 1.5, "meal_type": "dinner"},
    )
    client.async_update_food_entry.assert_awaited_once_with(
        ENTRY_ID,
        entry_type="food_entry",
        quantity=1.5,
        meal_type="dinner",
    )

    await _call(
        hass,
        SERVICE_DELETE_FOOD_ENTRY,
        {"entry_id": ENTRY_ID, "entry_type": "food_entry", "confirm": True},
    )
    client.async_delete_food_entry.assert_awaited_once_with(ENTRY_ID, "food_entry")
    assert coordinator.invalidate_sections.call_args_list[-1].args == ("trends",)


async def test_update_and_delete_exercise_entry_by_id(hass, service_runtime) -> None:
    """Exercise updates forward only supplied fields and deletes require confirmation."""

    client, coordinator = service_runtime
    replacement_sets = [{"reps": 8, "weight": 82.5, "rpe": 9}]
    await _call(
        hass,
        SERVICE_UPDATE_EXERCISE_ENTRY,
        {"entry_id": ENTRY_ID, "notes": "Corrected", "sets": replacement_sets},
    )
    client.async_update_exercise_entry.assert_awaited_once_with(
        ENTRY_ID,
        notes="Corrected",
        sets=[
            {
                "reps": 8,
                "weight": 82.5,
                "rpe": 9.0,
                "set_type": "Working Set",
            }
        ],
    )

    await _call(
        hass,
        SERVICE_DELETE_EXERCISE_ENTRY,
        {"entry_id": ENTRY_ID, "confirm": True},
    )
    client.async_delete_exercise_entry.assert_awaited_once_with(ENTRY_ID)
    assert coordinator.invalidate_sections.call_args_list[-1].args == ("trends",)


async def test_start_and_log_completed_fasting_window(hass, service_runtime) -> None:
    """Fasting actions map only to the current MCP log_fasting operation."""

    client, coordinator = service_runtime
    await _call(
        hass,
        SERVICE_START_FASTING,
        {
            "start_time": "2026-08-26T18:00:00+00:00",
            "fasting_type": "16:8",
        },
    )
    client.async_log_fasting.assert_awaited_with(
        "2026-08-26T18:00:00+00:00",
        fasting_status="ACTIVE",
        fasting_type="16:8",
    )

    await _call(
        hass,
        SERVICE_LOG_FASTING_WINDOW,
        {
            "start_time": "2026-08-25T18:00:00+00:00",
            "end_time": "2026-08-26T10:00:00+00:00",
            "fasting_status": "COMPLETED",
        },
    )
    client.async_log_fasting.assert_awaited_with(
        "2026-08-25T18:00:00+00:00",
        end_time="2026-08-26T10:00:00+00:00",
        fasting_status="COMPLETED",
        fasting_type=None,
    )
    assert coordinator.async_request_refresh.await_count == 2
