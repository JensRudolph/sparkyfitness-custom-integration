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
    CONF_ENABLE_NUTRITION,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    TOOL_CHECKIN,
    TOOL_HEALTH_SUMMARY,
    TOOL_STREAK,
)
from .exceptions import (
    SparkyFitnessAuthenticationError,
    SparkyFitnessConnectionError,
    SparkyFitnessError,
)
from .extract import (
    parse_checkin_diary,
    parse_fasting_status,
    parse_health_summary,
    parse_logging_streak,
)
from .models import SparkyFitnessData

_LOGGER = logging.getLogger(__name__)


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

    async def _async_update_data(self) -> SparkyFitnessData:
        """Fetch enabled sections while isolating optional failures."""

        calls: dict[str, Any] = {}
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

        previous = self.data or SparkyFitnessData()
        values = dict(previous.values)
        fasting = previous.fasting
        section_errors: dict[str, str] = {}

        if not calls:
            self.last_successful_refresh = datetime.now(UTC)
            self.last_error_class = None
            return SparkyFitnessData(values=values, fasting=fasting)

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
                elif section == "checkin":
                    checkin = parse_checkin_diary(str(result))
                    self._normalize_weight(checkin)
                    values.update(checkin)
                elif section == "fasting":
                    fasting = parse_fasting_status(str(result))
                elif section == "streak":
                    values["logging_streak"] = parse_logging_streak(str(result))
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

        self.last_successful_refresh = datetime.now(UTC)
        if not section_errors:
            self.last_error_class = None
        return SparkyFitnessData(
            values=values,
            fasting=fasting,
            section_errors=section_errors,
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
