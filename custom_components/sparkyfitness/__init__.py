"""SparkyFitness Home Assistant integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SparkyFitnessMcpClient
from .const import (
    CONF_API_KEY,
    CONF_VERIFY_SSL,
    DEFAULT_VERIFY_SSL,
    PLATFORMS,
)
from .coordinator import SparkyFitnessCoordinator
from .exceptions import (
    SparkyFitnessAuthenticationError,
    SparkyFitnessConnectionError,
    SparkyFitnessMcpError,
)
from .models import SparkyFitnessRuntimeData
from .services import async_register_services

type SparkyFitnessConfigEntry = ConfigEntry[SparkyFitnessRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register integration-wide actions."""

    async_register_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: SparkyFitnessConfigEntry
) -> bool:
    """Set up one independently scoped SparkyFitness connection."""

    verify_ssl = bool(
        entry.options.get(
            CONF_VERIFY_SSL, entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
        )
    )
    client = SparkyFitnessMcpClient(
        async_get_clientsession(hass, verify_ssl=verify_ssl),
        entry.data[CONF_URL],
        entry.data[CONF_API_KEY],
        verify_ssl=verify_ssl,
    )
    try:
        await client.async_test_connection()
    except SparkyFitnessAuthenticationError as err:
        raise ConfigEntryAuthFailed from err
    except (SparkyFitnessConnectionError, SparkyFitnessMcpError) as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = SparkyFitnessCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.async_disconnect()
        raise
    entry.runtime_data = SparkyFitnessRuntimeData(
        client=client,
        coordinator=coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SparkyFitnessConfigEntry
) -> bool:
    """Unload platforms and protocol state for one entry."""

    unloaded = await hass.config_entries.async_unload_platforms(
        entry, [Platform(platform) for platform in PLATFORMS]
    )
    if unloaded:
        await entry.runtime_data.client.async_disconnect()
    return unloaded
