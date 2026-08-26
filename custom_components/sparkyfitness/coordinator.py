"""Data update coordinator for SparkyFitness."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
    habit_history_metrics,
    parse_30_day_trends,
    parse_checkin_diary,
    parse_fasting_status,
    parse_goal_snapshot,
    parse_habit_completion,
    parse_habit_history,
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
_HABIT_ANALYTICS_REFRESH_INTERVAL = timedelta(hours=1)
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
        self._habit_analytics_cache: dict[str, dict[str, Any]] = {}
        self._habit_analytics_updated_at: dict[str, datetime] = {}
        self._reported_section_errors: set[str] = set()
        self._poll_demands: dict[tuple[str, str], tuple[frozenset[str], bool]] = {}
        self._entity_demand_active = False
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

    def register_poll_demand(
        self,
        entity_domain: str,
        key: str,
        sections: frozenset[str],
        *,
        enabled_default: bool = True,
    ) -> None:
        """Register which coordinator sections feed one entity."""

        self._poll_demands[(entity_domain, key)] = (sections, enabled_default)

    def activate_entity_demand(self) -> None:
        """Use the entity registry after all platforms completed setup."""

        self._entity_demand_active = True

    def _entity_enabled(
        self, entity_domain: str, key: str, *, enabled_default: bool
    ) -> bool:
        """Return whether a stable integration entity is actually enabled."""

        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id(
            entity_domain,
            DOMAIN,
            f"{self.config_entry.entry_id}_{key}",
        )
        if entity_id is None:
            return enabled_default
        registry_entry = registry.async_get(entity_id)
        return registry_entry is not None and registry_entry.disabled_by is None

    def _section_requested(self, section: str) -> bool:
        """Return whether at least one enabled entity consumes a section."""

        if not self._entity_demand_active:
            return True
        return any(
            section in sections
            and self._entity_enabled(
                entity_domain, key, enabled_default=enabled_default
            )
            for (entity_domain, key), (
                sections,
                enabled_default,
            ) in self._poll_demands.items()
        )

    def invalidate_habit_analytics(self, habit_id: str | None = None) -> None:
        """Force habit analytics to refresh after a related write."""

        if habit_id is None:
            self._habit_analytics_updated_at.clear()
            return
        self._habit_analytics_updated_at.pop(habit_id, None)

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
        if (
            TOOL_HEALTH_SUMMARY in self.client.tools
            and self._section_requested("summary")
            and any(
                self.feature_enabled(option)
                for option in (
                    CONF_ENABLE_NUTRITION,
                    CONF_ENABLE_EXERCISE,
                    CONF_ENABLE_CHECKIN,
                )
            )
        ):
            calls["summary"] = self.client.async_get_today_summary()
        if (
            self.feature_enabled(CONF_ENABLE_NUTRITION)
            and TOOL_NUTRITION_SUMMARY in self.client.tools
            and self._section_requested("nutrition")
        ):
            calls["nutrition"] = self.client.async_get_nutrition_summary()
        if (
            self.feature_enabled(CONF_ENABLE_CHECKIN)
            and TOOL_CHECKIN in self.client.tools
        ):
            if self._section_requested("checkin"):
                calls["checkin"] = self.client.async_get_checkin()
            if self._section_requested("fasting"):
                calls["fasting"] = self.client.async_get_fasting_status()
        if (
            self.feature_enabled(CONF_ENABLE_ENGAGEMENT)
            and TOOL_STREAK in self.client.tools
            and self._section_requested("streak")
        ):
            calls["streak"] = self.client.async_get_logging_streak()
        if (
            self.feature_enabled(CONF_ENABLE_GOALS)
            and TOOL_GOAL_SNAPSHOT in self.client.tools
            and self._section_requested("goals")
            and self._section_due("goals", _GOAL_REFRESH_INTERVAL, now)
        ):
            calls["goals"] = self.client.async_get_goal_snapshot()
        if (
            self.feature_enabled(CONF_ENABLE_TRENDS)
            and TOOL_30_DAY_TRENDS in self.client.tools
            and self._section_requested("trends")
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
        """Fetch demanded current and analytical habit state with bounded calls."""

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

        async def async_get_history(
            habit_id: str, start_date: str, end_date: str
        ) -> Any:
            async with semaphore:
                return await self.client.async_get_habit_history(
                    habit_id, start_date=start_date, end_date=end_date
                )

        analytics_end = dt_util.now().date()
        analytics_start = analytics_end - timedelta(days=29)
        requests: list[tuple[str, str, Any]] = []
        for habit_id, habit in habits.items():
            previous = (self.data.habits if self.data else {}).get(habit_id) or {}
            habit["completed"] = previous.get("completed")
            habit["history_available"] = previous.get("history_available", True)

            current_enabled = self._entity_enabled(
                "binary_sensor", f"habit_{habit_id}", enabled_default=True
            )
            analytics_enabled = any(
                self._entity_enabled(
                    "sensor",
                    f"habit_{habit_id}_{metric}",
                    enabled_default=False,
                )
                for metric in ("completion_7d", "completion_30d", "streak")
            )
            if current_enabled:
                requests.append(
                    (
                        habit_id,
                        "current",
                        async_get_history(habit_id, entry_date, entry_date),
                    )
                )
            cached_analytics = self._habit_analytics_cache.get(habit_id)
            if analytics_enabled and cached_analytics:
                habit.update(cached_analytics)
                habit["analytics_available"] = True
            analytics_updated_at = self._habit_analytics_updated_at.get(habit_id)
            analytics_due = analytics_enabled and (
                analytics_updated_at is None
                or now - analytics_updated_at >= _HABIT_ANALYTICS_REFRESH_INTERVAL
            )
            if analytics_due:
                requests.append(
                    (
                        habit_id,
                        "analytics",
                        async_get_history(
                            habit_id, analytics_start.isoformat(), "today"
                        ),
                    )
                )

        results = await asyncio.gather(
            *(request[2] for request in requests), return_exceptions=True
        )
        failed_ids: set[str] = set()
        for (habit_id, request_type, _), result in zip(requests, results, strict=True):
            habit = habits[habit_id]
            if isinstance(result, SparkyFitnessAuthenticationError):
                raise result
            if isinstance(result, BaseException):
                failed_ids.add(habit_id)
                if request_type == "current":
                    habit["history_available"] = False
                else:
                    habit["analytics_available"] = False
                continue
            if request_type == "current":
                habit["completed"] = parse_habit_completion(str(result), entry_date)
                habit["history_available"] = True
            else:
                analytics = habit_history_metrics(
                    parse_habit_history(str(result)), analytics_end
                )
                self._habit_analytics_cache[habit_id] = analytics
                self._habit_analytics_updated_at[habit_id] = now
                habit.update(analytics)
                habit["analytics_available"] = True
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
