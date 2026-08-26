"""Tests for the read-only SparkyFitness workout calendar."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.components.calendar import CalendarEvent
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sparkyfitness.calendar import (
    SparkyFitnessWorkoutCalendar,
    async_setup_entry,
    parse_workout_events,
)
from custom_components.sparkyfitness.const import DOMAIN, TOOL_EXERCISE_DIARY
from custom_components.sparkyfitness.exceptions import (
    SparkyFitnessAuthenticationError,
    SparkyFitnessConnectionError,
)


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

    start = datetime(2026, 8, 26, tzinfo=zone)
    end = datetime(2026, 8, 27, tzinfo=zone)
    events = await entity.async_get_events(
        hass,
        start,
        end,
    )

    assert len(events) == 1
    local_zone = ZoneInfo(hass.config.time_zone)
    client.async_list_exercise_diary.assert_awaited_once_with(
        start_date=start.astimezone(local_zone).date().isoformat(),
        end_date=end.astimezone(local_zone).date().isoformat(),
    )


def test_calendar_parser_accepts_reviewed_variants_and_rejects_bad_shape() -> None:
    """Structured/text results and safe timestamp fallbacks remain deterministic."""

    zone = ZoneInfo("UTC")
    events = parse_workout_events(
        "MCP result\n"
        '{"data":[{"id":"nested","exercise":{"name":"Bike"},'
        '"entry_date":"2026-08-26","start_time":"2026-08-26T10:00:00+00:00",'
        '"end_time":"2026-08-26T09:00:00+00:00"}]}',
        zone=zone,
        range_start=datetime(2026, 8, 26, tzinfo=zone),
        range_end=datetime(2026, 8, 27, tzinfo=zone),
    )
    assert events[0].summary == "Bike"
    assert events[0].end == events[0].start + timedelta(minutes=1)

    events = parse_workout_events(
        [
            None,
            {
                "id": "native-values",
                "entry_date": date(2026, 8, 26),
                "entry_time": time(12, 0),
                "end_time": time(12, 30),
            },
            {
                "id": "fallback-duration",
                "entry_date": "2026-08-26",
                "entry_time": "14:00",
                "duration_minutes": "invalid",
            },
        ],
        zone=zone,
        range_start=datetime(2026, 8, 26, tzinfo=zone),
        range_end=datetime(2026, 8, 27, tzinfo=zone),
    )
    assert events[0].end - events[0].start == timedelta(minutes=30)
    assert events[1].end - events[1].start == timedelta(minutes=60)

    with pytest.raises(HomeAssistantError, match="entry list"):
        parse_workout_events(
            {"data": {}},
            zone=zone,
            range_start=datetime(2026, 8, 26, tzinfo=zone),
            range_end=datetime(2026, 8, 27, tzinfo=zone),
        )


async def test_calendar_setup_update_and_error_mapping(hass) -> None:
    """The platform adds one calendar, selects the next event, and maps MCP errors."""

    client = MagicMock()
    client.tools = {TOOL_EXERCISE_DIARY: object()}
    client.server_version = "1.6.3"
    client.endpoint = "https://sparky.example.com/mcp"
    coordinator = SimpleNamespace(
        client=client,
        feature_enabled=MagicMock(return_value=True),
    )
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.runtime_data = SimpleNamespace(client=client, coordinator=coordinator)
    add_entities = MagicMock()

    await async_setup_entry(hass, entry, add_entities)
    entity = add_entities.call_args.args[0][0]
    entity.hass = hass
    now = datetime(2026, 8, 26, 10, tzinfo=ZoneInfo("UTC"))
    next_event = CalendarEvent(
        start=now + timedelta(hours=1),
        end=now + timedelta(hours=2),
        summary="Walk",
    )
    with (
        patch(
            "custom_components.sparkyfitness.calendar.dt_util.now",
            return_value=now,
        ),
        patch.object(
            entity,
            "_async_fetch_events",
            AsyncMock(return_value=[next_event]),
        ),
    ):
        await entity.async_update()
    assert entity.event is next_event

    client.async_list_exercise_diary = AsyncMock(
        side_effect=SparkyFitnessAuthenticationError()
    )
    with (
        patch.object(entry, "async_start_reauth") as start_reauth,
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_get_events(
            hass,
            now,
            now + timedelta(days=1),
        )
    start_reauth.assert_called_once_with(hass)

    client.async_list_exercise_diary.side_effect = SparkyFitnessConnectionError("down")
    with pytest.raises(HomeAssistantError):
        await entity.async_get_events(hass, now, now + timedelta(days=1))
