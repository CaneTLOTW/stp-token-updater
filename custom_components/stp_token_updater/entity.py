"""Shared STP entity helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import StpTokenCoordinator


class StpEntity(CoordinatorEntity[StpTokenCoordinator]):
    """Base entity bound to one STP coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: StpTokenCoordinator, description_key: str) -> None:
        super().__init__(coordinator)
        self.entity_description_key = description_key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="STP",
            model="Sponsor Token Provider",
            sw_version=coordinator.state.provider_version,
            configuration_url=coordinator.client.base_url,
        )

    @property
    def available(self) -> bool:
        """Keep cached lifecycle state visible during provider outages."""
        state = self.coordinator.state
        return state.reachable or state.last_check is not None

    @property
    def extra_state_attributes(self) -> dict:
        state = self.coordinator.state
        return {
            "provider_url": self.coordinator.client.base_url,
            "provider_version": state.provider_version,
            "reachable": state.reachable,
            "dry_run": state.dry_run,
        }
