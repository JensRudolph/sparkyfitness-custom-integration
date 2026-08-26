"""Shared entity base for SparkyFitness."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ACCOUNT_NAME, DOMAIN, NAME
from .coordinator import SparkyFitnessCoordinator


class SparkyFitnessEntity(CoordinatorEntity[SparkyFitnessCoordinator]):
    """Base class for entities belonging to one SparkyFitness entry."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SparkyFitnessCoordinator, key: str) -> None:
        """Initialize an entity."""

        super().__init__(coordinator)
        entry = coordinator.config_entry
        account_name = str(
            entry.options.get(CONF_ACCOUNT_NAME, entry.data.get(CONF_ACCOUNT_NAME, ""))
        ).strip()
        device_name = f"{NAME} {account_name}" if account_name else NAME
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=NAME,
            model="MCP",
            name=device_name,
            sw_version=coordinator.client.server_version,
            configuration_url=coordinator.client.endpoint,
        )
