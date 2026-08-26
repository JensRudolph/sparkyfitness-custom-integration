"""Tests for explicit Home Assistant write actions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.service import async_get_all_descriptions

from custom_components.sparkyfitness import async_setup
from custom_components.sparkyfitness.const import (
    DOMAIN,
    SERVICE_LOG_CUSTOM_METRIC,
    SERVICE_LOG_EXERCISE,
    SERVICE_LOG_MOOD,
    SERVICE_LOG_WATER,
    SERVICE_LOG_WEIGHT,
)


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
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
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
