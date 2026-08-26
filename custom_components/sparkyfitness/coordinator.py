"""Data update coordinator for SparkyFitness."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SparkyFitnessMcpClient
from .const import (
    CONF_ENABLE_CHECKIN,
    CONF_ENABLE_ENGAGEMENT,
    CONF_ENABLE_EXERCISE,
    CONF_ENABLE_GOALS,
    CONF_ENABLE_HABITS,
    CONF_ENABLE_NUTRITION,
    CONF_ENABLE_TRENDS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    TOOL_30_DAY_TRENDS,
    TOOL_CHECKIN,
    TOOL_GOAL_SNAPSHOT,
    TOOL_HABITS,
    TOOL_HEALTH_SUMMARY,
    TOOL_NUTRITION_SUMMARY,
    TOOL_STREAK,
)
from .exceptions import (
    SparkyFitnessAuthenticationError,
    SparkyFitnessConnectionError,
    SparkyFitnessError,
)
from .extract import (
    parse_30_day_trends,
    parse_checkin_diary,
    parse_fasting_status,
    parse_goal_snapshot,
    parse_habit_completion,
    parse_habit_list,
    parse_health_summary,
    parse_logging_streak,
    parse_nutrition_summary,
)
from .models import HabitPollResult, SparkyFitnessData

_LOGGER = logging.getLogger(__name__)
_GOAL_REFRESH_INTERVAL = timedelta(minutes=30)
_TRENDS_REFRESH_INTERVAL = timedelta(hours=1)
_HABIT_CATALOG_REFRESH_INTERVAL = timedelta(hours=1)
_HABIT_HISTORY_CONCURRENCY = 4


class SparkyFitnessCoordinator(DataUpdateCoordinator[SparkyFitnessData]):
    """Poll supported SparkyFitness MCP data domains independently."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: SparkyFitnessMcpClient,
    ) -> None:
        """Initialize the coordinator."""

        self.client = client
        self.config_entry = entry
        self.last_successful_refresh: datetime | None = None
        self.last_error_class: str | None = None
        self._section_updated_at: dict[str, datetime] = {}
        self._habit_catalog: dict[str, dict[str, Any]] = {}
        self._habit_catalog_updated_at: datetime | None = None
        self._reported_section_errors: set[str] = set()
        interval = int(entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval),
            always_update=False,
        )

    def feature_enabled(self, option: str) -> bool:
        """Return whether an optional feature group is enabled."""

        return bool(self.config_entry.options.get(option, True))

    def invalidate_sections(self, *sections: str) -> None:
        """Force slow-changing sections to refresh on the next update."""

        for section in sections:
            self._section_updated_at.pop(section, None)

    def _section_due(self, section: str, interval: timedelta, now: datetime) -> bool:
        """Return whether a deliberately throttled section should run."""

        last_update = self._section_updated_at.get(section)
        return last_update is None or now - last_update >= interval

    async def _async_update_data(self) -> SparkyFitnessData:
        """Fetch enabled sections while isolating optional failures."""

        calls: dict[str, Any] = {}
        now = datetime.now(UTC)
        if TOOL_HEALTH_SUMMARY in self.client.tools and any(
            self.feature_enabled(option)
            for option in (
                CONF_ENABLE_NUTRITION,
                CONF_ENABLE_EXERCISE,
                CONF_ENABLE_CHECKIN,
            )
        ):
            calls["summary"] = self.client.async_get_today_summary()
        if (
            self.feature_enabled(CONF_ENABLE_NUTRITION)
            and TOOL_NUTRITION_SUMMARY in self.client.tools
        ):
            calls["nutrition"] = self.client.async_get_nutrition_summary()
        if (
            self.feature_enabled(CONF_ENABLE_CHECKIN)
            and TOOL_CHECKIN in self.client.tools
        ):
            calls["checkin"] = self.client.async_get_checkin()
            calls["fasting"] = self.client.async_get_fasting_status()
        if (
            self.feature_enabled(CONF_ENABLE_ENGAGEMENT)
            and TOOL_STREAK in self.client.tools
        ):
            calls["streak"] = self.client.async_get_logging_streak()
        if (
            self.feature_enabled(CONF_ENABLE_GOALS)
            and TOOL_GOAL_SNAPSHOT in self.client.tools
            and self._section_due("goals", _GOAL_REFRESH_INTERVAL, now)
        ):
            calls["goals"] = self.client.async_get_goal_snapshot()
        if (
            self.feature_enabled(CONF_ENABLE_TRENDS)
            and TOOL_30_DAY_TRENDS in self.client.tools
            and self._section_due("trends", _TRENDS_REFRESH_INTERVAL, now)
        ):
            calls["trends"] = self.client.async_get_30_day_trends()
        if (
            self.feature_enabled(CONF_ENABLE_HABITS)
            and TOOL_HABITS in self.client.tools
        ):
            calls["habits"] = self._async_get_habits("today")

        previous = self.data or SparkyFitnessData()
        values = dict(previous.values)
        fasting = previous.fasting
        habits = dict(previous.habits)
        section_errors: dict[str, str] = {}

        if not calls:
            self.last_successful_refresh = now
            self.last_error_class = None
            self._log_section_transitions({})
            return SparkyFitnessData(values=values, fasting=fasting, habits=habits)

        results = await asyncio.gather(*calls.values(), return_exceptions=True)
        successful = 0
        connection_errors = 0

        for section, result in zip(calls, results, strict=True):
            if isinstance(result, SparkyFitnessAuthenticationError):
                self.last_error_class = type(result).__name__
                raise ConfigEntryAuthFailed from result
            if isinstance(result, BaseException):
                error_name = type(result).__name__
                section_errors[section] = error_name
                self.last_error_class = error_name
                if isinstance(result, SparkyFitnessConnectionError):
                    connection_errors += 1
                _LOGGER.debug("SparkyFitness %s update failed: %s", section, error_name)
                continue

            try:
                if section == "summary":
                    values.update(parse_health_summary(str(result)))
                elif section == "nutrition":
                    values.update(parse_nutrition_summary(str(result)))
                elif section == "checkin":
                    checkin = parse_checkin_diary(str(result))
                    self._normalize_weight(checkin)
                    values.update(checkin)
                elif section == "fasting":
                    fasting = parse_fasting_status(str(result))
                elif section == "streak":
                    values["logging_streak"] = parse_logging_streak(str(result))
                elif section == "goals":
                    values.update(parse_goal_snapshot(str(result)))
                    self._section_updated_at["goals"] = now
                elif section == "trends":
                    values.update(parse_30_day_trends(str(result)))
                    self._section_updated_at["trends"] = now
                elif section == "habits":
                    habits = result.habits
                    if result.failed_ids or result.catalog_failed:
                        section_errors[section] = "PartialHabitPollingError"
                        self.last_error_class = "PartialHabitPollingError"
            except SparkyFitnessError as err:
                section_errors[section] = type(err).__name__
                self.last_error_class = type(err).__name__
                continue
            successful += 1

        if successful == 0:
            error = "All enabled SparkyFitness MCP data requests failed"
            if connection_errors == len(calls):
                error = "Unable to communicate with SparkyFitness MCP"
            raise UpdateFailed(error)

        self.last_successful_refresh = now
        if not section_errors:
            self.last_error_class = None
        self._log_section_transitions(section_errors)
        return SparkyFitnessData(
            values=values,
            fasting=fasting,
            habits=habits,
            section_errors=section_errors,
        )

    def _log_section_transitions(self, section_errors: dict[str, str]) -> None:
        """Log each partial outage and recovery once, without health values."""

        failed_sections = set(section_errors)
        for section in sorted(failed_sections - self._reported_section_errors):
            _LOGGER.warning(
                "SparkyFitness polling section %s became unavailable (%s)",
                section,
                section_errors[section],
            )
        for section in sorted(self._reported_section_errors - failed_sections):
            _LOGGER.info("SparkyFitness polling section %s recovered", section)
        self._reported_section_errors = failed_sections

    async def _async_get_habits(self, entry_date: str) -> HabitPollResult:
        """Fetch today's state for every habit through reviewed MCP actions."""

        now = datetime.now(UTC)
        catalog_failed = False
        catalog_due = (
            self._habit_catalog_updated_at is None
            or now - self._habit_catalog_updated_at >= _HABIT_CATALOG_REFRESH_INTERVAL
        )
        if catalog_due:
            try:
                catalog = parse_habit_list(str(await self.client.async_list_habits()))
            except SparkyFitnessAuthenticationError:
                raise
            except SparkyFitnessError:
                if not self._habit_catalog:
                    raise
                catalog_failed = True
            else:
                self._habit_catalog = catalog
                self._habit_catalog_updated_at = now

        habits = {
            habit_id: dict(habit) for habit_id, habit in self._habit_catalog.items()
        }
        if not habits:
            return HabitPollResult(habits={}, catalog_failed=catalog_failed)

        semaphore = asyncio.Semaphore(_HABIT_HISTORY_CONCURRENCY)

        async def async_get_history(habit_id: str) -> Any:
            async with semaphore:
                return await self.client.async_get_habit_history(
                    habit_id, start_date=entry_date, end_date=entry_date
                )

        results = await asyncio.gather(
            *(async_get_history(habit_id) for habit_id in habits),
            return_exceptions=True,
        )
        failed_ids: set[str] = set()
        previous_habits = self.data.habits if self.data else {}
        for habit_id, result in zip(habits, results, strict=True):
            habit = habits[habit_id]
            if isinstance(result, SparkyFitnessAuthenticationError):
                raise result
            if isinstance(result, BaseException):
                failed_ids.add(habit_id)
                previous = previous_habits.get(habit_id) or {}
                habit["completed"] = previous.get("completed")
                habit["history_available"] = False
                continue
            habit["completed"] = parse_habit_completion(str(result), entry_date)
            habit["history_available"] = True
        return HabitPollResult(
            habits=habits,
            failed_ids=failed_ids,
            catalog_failed=catalog_failed,
        )

    @staticmethod
    def _normalize_weight(values: dict[str, Any]) -> None:
        """Convert preferred-unit check-in weight to the integration's kg unit."""

        weight = values.get("weight")
        unit = str(values.pop("weight_unit", "kg")).lower()
        if weight is None:
            return
        numeric = float(weight)
        if unit in {"lb", "lbs"}:
            numeric *= 0.45359237
        elif unit == "g":
            numeric /= 1000
        values["weight"] = round(numeric, 3)
