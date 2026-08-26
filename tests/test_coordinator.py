"""Tests for independent coordinator sections and recovery."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sparkyfitness.const import (
    DOMAIN,
    TOOL_30_DAY_TRENDS,
    TOOL_CHECKIN,
    TOOL_GOAL_SNAPSHOT,
    TOOL_HEALTH_SUMMARY,
    TOOL_STREAK,
)
from custom_components.sparkyfitness.coordinator import SparkyFitnessCoordinator
from custom_components.sparkyfitness.exceptions import SparkyFitnessConnectionError

SUMMARY = (
    '# Health Summary\n\n{"nutrition":{"total_calories":1800,"avg_protein":120,'
    '"avg_carbs":200,"avg_fat":60},"fitness":{"workout_count":2},'
    '"vitals":{"latest_weight":{"weight":84.7,"date":"2026-08-26"}},'
    '"hydration":{"total_water_ml":2500}}'
)
CHECKIN = """### Check-in Diary: today

#### Biometrics
- **Weight:** 180 lbs
- **Steps:** 10000
- **Body Fat:** 18%

## Mood
- 8/10

## Sleep
- 7h 30m | score: 90/100
"""


def _client() -> MagicMock:
    client = MagicMock()
    client.tools = {
        TOOL_HEALTH_SUMMARY: object(),
        TOOL_CHECKIN: object(),
        TOOL_STREAK: object(),
    }
    client.async_get_today_summary = AsyncMock(return_value=SUMMARY)
    client.async_get_checkin = AsyncMock(return_value=CHECKIN)
    client.async_get_fasting_status = AsyncMock(
        return_value="No active fasting session."
    )
    client.async_get_logging_streak = AsyncMock(
        return_value='{"current_streak":4,"last_logged":"2026-08-26"}'
    )
    return client


def _entry(hass) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    return entry


async def test_successful_refresh(hass) -> None:
    """All stable priority values are projected and preferred lbs become kg."""

    coordinator = SparkyFitnessCoordinator(hass, _entry(hass), _client())
    data = await coordinator._async_update_data()
    assert data.values["calories_today"] == 1800
    assert data.values["steps_today"] == 10000
    assert data.values["sleep_duration"] == 7.5
    assert data.values["logging_streak"] == 4
    assert data.values["weight"] == pytest.approx(81.647, abs=0.001)
    assert data.fasting is None
    assert data.section_errors == {}


async def test_partial_failure_keeps_other_sections(hass) -> None:
    """One optional domain error does not make unrelated data unavailable."""

    client = _client()
    client.async_get_checkin.side_effect = SparkyFitnessConnectionError()
    coordinator = SparkyFitnessCoordinator(hass, _entry(hass), client)
    data = await coordinator._async_update_data()
    assert data.values["calories_today"] == 1800
    assert data.values["logging_streak"] == 4
    assert data.section_errors == {"checkin": "SparkyFitnessConnectionError"}


async def test_complete_communication_failure(hass) -> None:
    """A total outage raises UpdateFailed instead of publishing zero values."""

    client = _client()
    error = SparkyFitnessConnectionError()
    client.async_get_today_summary.side_effect = error
    client.async_get_checkin.side_effect = error
    client.async_get_fasting_status.side_effect = error
    client.async_get_logging_streak.side_effect = error
    coordinator = SparkyFitnessCoordinator(hass, _entry(hass), client)
    with pytest.raises(UpdateFailed, match="Unable to communicate"):
        await coordinator._async_update_data()


async def test_recovery_after_failure(hass) -> None:
    """A later successful refresh clears the technical error marker."""

    client = _client()
    client.async_get_today_summary.side_effect = [
        SparkyFitnessConnectionError(),
        SUMMARY,
    ]
    client.async_get_checkin.side_effect = [SparkyFitnessConnectionError(), CHECKIN]
    client.async_get_fasting_status.side_effect = [
        SparkyFitnessConnectionError(),
        "No active fasting session.",
    ]
    client.async_get_logging_streak.side_effect = [
        SparkyFitnessConnectionError(),
        '{"current_streak":4}',
    ]
    coordinator = SparkyFitnessCoordinator(hass, _entry(hass), client)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.last_error_class == "SparkyFitnessConnectionError"
    recovered = await coordinator._async_update_data()
    assert recovered.values["logging_streak"] == 4
    assert coordinator.last_error_class is None


async def test_goal_and_trend_sections_are_parsed_and_throttled(hass) -> None:
    """Slow aggregate tools are cached between normal five-minute updates."""

    client = _client()
    client.tools.update(
        {
            TOOL_GOAL_SNAPSHOT: object(),
            TOOL_30_DAY_TRENDS: object(),
        }
    )
    client.async_get_goal_snapshot = AsyncMock(
        return_value='{"calories":2100,"protein":150,"carbs":220,"fat":70,'
        '"water_goal_ml":2500}'
    )
    client.async_get_30_day_trends = AsyncMock(
        return_value='{"food":{"days_logged":28,"avg_daily_calories":1950,'
        '"avg_daily_protein":135},"exercise":{"total_workouts":14,'
        '"active_days":12,"total_calories_burned":4200},'
        '"mood":{"avg_mood":7.8},"sleep":{"avg_duration_hours":7.4,'
        '"avg_sleep_score":88},"biometrics":{"weight_entries":9}}'
    )
    coordinator = SparkyFitnessCoordinator(hass, _entry(hass), client)

    first = await coordinator._async_update_data()
    coordinator.data = first
    assert first.values["calorie_goal"] == 2100
    assert first.values["workouts_30d"] == 14
    assert first.values["avg_sleep_duration_30d"] == 7.4

    await coordinator._async_update_data()
    client.async_get_goal_snapshot.assert_awaited_once()
    client.async_get_30_day_trends.assert_awaited_once()

    coordinator.invalidate_sections("goals")
    await coordinator._async_update_data()
    assert client.async_get_goal_snapshot.await_count == 2
    client.async_get_30_day_trends.assert_awaited_once()
