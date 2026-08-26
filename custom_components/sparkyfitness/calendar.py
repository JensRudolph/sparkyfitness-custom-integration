"""Read-only workout calendar for SparkyFitness exercise diary entries."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, tzinfo
from typing import Any

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityDescription,
    CalendarEvent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACCOUNT_NAME,
    CONF_ENABLE_EXERCISE,
    DOMAIN,
    NAME,
    TOOL_EXERCISE_DIARY,
)
from .exceptions import SparkyFitnessAuthenticationError, SparkyFitnessError
from .extract import extract_json

SCAN_INTERVAL = timedelta(minutes=15)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the workout calendar when the diary tool is available."""

    coordinator = entry.runtime_data.coordinator
    if (
        TOOL_EXERCISE_DIARY not in coordinator.client.tools
        or not coordinator.feature_enabled(CONF_ENABLE_EXERCISE)
    ):
        return
    async_add_entities([SparkyFitnessWorkoutCalendar(entry)])


class SparkyFitnessWorkoutCalendar(CalendarEntity):
    """Display existing SparkyFitness exercise entries as calendar events."""

    _attr_has_entity_name = True
    entity_description = CalendarEntityDescription(
        key="workouts",
        translation_key="workouts",
        icon="mdi:dumbbell",
    )

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize one account-scoped read-only calendar."""

        self._entry = entry
        self._client = entry.runtime_data.client
        self._event: CalendarEvent | None = None
        self._attr_unique_id = f"{entry.entry_id}_workouts"
        account_name = str(
            entry.options.get(CONF_ACCOUNT_NAME, entry.data.get(CONF_ACCOUNT_NAME, ""))
        ).strip()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=NAME,
            model="MCP",
            name=f"{NAME} {account_name}" if account_name else NAME,
            sw_version=self._client.server_version,
            configuration_url=self._client.endpoint,
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Return the active or next upcoming workout."""

        return self._event

    async def async_update(self) -> None:
        """Refresh the next workout without loading full diary history."""

        now = dt_util.now()
        events = await self._async_fetch_events(
            now - timedelta(days=1), now + timedelta(days=30)
        )
        self._event = next(
            (event for event in events if event.end_datetime_local > now), None
        )

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return workouts overlapping the requested Home Assistant range."""

        return await self._async_fetch_events(start_date, end_date)

    async def _async_fetch_events(
        self, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Read and parse one bounded diary range through the existing MCP tool."""

        zone = dt_util.get_time_zone(self.hass.config.time_zone)
        local_start = start_date.astimezone(zone)
        local_end = end_date.astimezone(zone)
        try:
            payload = await self._client.async_list_exercise_diary(
                start_date=local_start.date().isoformat(),
                end_date=local_end.date().isoformat(),
            )
        except SparkyFitnessAuthenticationError as err:
            self._entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="authentication_failed",
            ) from err
        except SparkyFitnessError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return parse_workout_events(
            payload,
            zone=zone,
            range_start=start_date,
            range_end=end_date,
        )


def parse_workout_events(
    payload: Any,
    *,
    zone: tzinfo,
    range_start: datetime,
    range_end: datetime,
) -> list[CalendarEvent]:
    """Convert stable exercise-diary fields into bounded calendar events."""

    if isinstance(payload, str):
        payload = extract_json(payload)
    if isinstance(payload, dict):
        entries = payload.get("entries", payload.get("data"))
    else:
        entries = payload
    if not isinstance(entries, list):
        raise HomeAssistantError("Exercise diary did not contain an entry list")

    events: list[CalendarEvent] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        event = _workout_event(entry, zone)
        if event is None:
            continue
        event_start = _event_datetime(event.start, zone)
        event_end = _event_datetime(event.end, zone)
        if event_end > range_start and event_start < range_end:
            events.append(event)
    return sorted(events, key=lambda event: event.start_datetime_local)


def _workout_event(entry: dict[str, Any], zone: tzinfo) -> CalendarEvent | None:
    """Build one timed or all-day event from an exercise diary row."""

    entry_date = _parse_date(entry.get("entry_date") or entry.get("date"))
    raw_start = entry.get("start_time")
    start = _parse_datetime(raw_start, zone)
    entry_time = entry.get("entry_time") or entry.get("time") or raw_start
    if start is None and entry_date is not None and entry_time:
        parsed_time = _parse_time(entry_time)
        if parsed_time is not None:
            start = datetime.combine(entry_date, parsed_time, zone)

    exercise = entry.get("exercise")
    if isinstance(exercise, dict):
        exercise = exercise.get("name")
    summary = str(
        entry.get("exercise_name") or exercise or entry.get("name") or "Workout"
    )
    notes = entry.get("notes")
    description = str(notes) if notes not in (None, "") else None
    uid_value = entry.get("id") or entry.get("entry_id")
    uid = str(uid_value) if uid_value is not None else None

    if start is None:
        if entry_date is None:
            return None
        return CalendarEvent(
            start=entry_date,
            end=entry_date + timedelta(days=1),
            summary=summary,
            description=description,
            uid=uid,
        )

    end = _parse_datetime(entry.get("end_time"), zone)
    if end is None and entry_date is not None:
        parsed_end_time = _parse_time(entry.get("end_time"))
        if parsed_end_time is not None:
            end = datetime.combine(entry_date, parsed_end_time, zone)
    if end is None:
        duration = _positive_float(entry.get("duration_minutes")) or 60.0
        end = start + timedelta(minutes=duration)
    if end <= start:
        end = start + timedelta(minutes=1)
    return CalendarEvent(
        start=start,
        end=end,
        summary=summary,
        description=description,
        uid=uid,
    )


def _parse_date(value: Any) -> date | None:
    """Return a strict ISO date when supplied."""

    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_datetime(value: Any, zone: tzinfo) -> datetime | None:
    """Return an aware datetime while treating naive values as HA-local."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = dt_util.parse_datetime(value)
    else:
        return None
    if parsed is None:
        return None
    return parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed


def _parse_time(value: Any) -> time | None:
    """Return a time from common diary formats."""

    if isinstance(value, time):
        return value
    if not isinstance(value, str):
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


def _positive_float(value: Any) -> float | None:
    """Return a positive numeric duration or None."""

    try:
        result = float(value)
    except TypeError, ValueError:
        return None
    return result if result > 0 else None


def _event_datetime(value: date | datetime, zone: tzinfo) -> datetime:
    """Normalize timed and all-day boundaries for overlap filtering."""

    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min, zone)
