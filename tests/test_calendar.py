"""Tests for the read-only SparkyFitness workout calendar."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sparkyfitness.calendar import (
    SparkyFitnessWorkoutCalendar,
    parse_workout_events,
)
from custom_components.sparkyfitness.const import DOMAIN


def test_parse_timed_and_all_day_workouts_with_range_filtering() -> None:
    """Diary rows become stable events and out-of-range data is discarded."""

    zone = ZoneInfo("Europe/Berlin")
    events = parse_workout_events(
        {
            "entries": [
                {
                    "id": "timed",
                    "exercise_name": "Morning walk",
                    "entry_date": "2026-08-26",
                    "entry_time": "08:30:00",
                    "duration_minutes": 45,
                    "notes": "Easy pace",
                },
                {
                    "entry_id": "all-day",
                    "exercise": "Strength",
                    "entry_date": "2026-08-27",
                },
                {"id": "old", "name": "Old", "entry_date": "2026-07-01"},
                {"id": "invalid", "name": "Missing date"},
            ]
        },
        zone=zone,
        range_start=datetime(2026, 8, 26, tzinfo=zone),
        range_end=datetime(2026, 8, 28, tzinfo=zone),
    )

    assert [event.uid for event in events] == ["timed", "all-day"]
    assert events[0].summary == "Morning walk"
    assert events[0].description == "Easy pace"
    assert events[0].start == datetime(2026, 8, 26, 8, 30, tzinfo=zone)
    assert events[0].end == datetime(2026, 8, 26, 9, 15, tzinfo=zone)
    assert events[1].all_day is True


async def test_calendar_fetches_only_requested_diary_range(hass) -> None:
    """Calendar browsing uses the existing bounded exercise diary action."""

    client = MagicMock()
    client.server_version = "1.6.3"
    client.endpoint = "https://sparky.example.com/mcp"
    client.async_list_exercise_diary = AsyncMock(
        return_value={
            "entries": [
                {
                    "id": "workout",
                    "exercise_name": "Walk",
                    "entry_date": "2026-08-26",
                    "entry_time": "10:00:00",
                    "duration_minutes": 30,
                }
            ]
        }
    )
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(client=client)
    entity = SparkyFitnessWorkoutCalendar(entry)
    entity.hass = hass
    zone = ZoneInfo("UTC")

    events = await entity.async_get_events(
        hass,
        datetime(2026, 8, 26, tzinfo=zone),
        datetime(2026, 8, 27, tzinfo=zone),
    )

    assert len(events) == 1
    client.async_list_exercise_diary.assert_awaited_once_with(
        start_date="2026-08-26", end_date="2026-08-27"
    )
