"""Binary status entities."""

from __future__ import annotations

from datetime import UTC, datetime

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import EvccEntity
from .models import UpdaterStatus


ITEMS = (
    ("token_valid", "Token Valid", None),
    ("new_trial_token_available", "New Trial Token Available", None),
    ("token_update_required", "Token Update Required", None),
    ("token_updater_problem", "Token Updater Problem", BinarySensorDeviceClass.PROBLEM),
    ("api_reachable", "Provider API Reachable", BinarySensorDeviceClass.CONNECTIVITY),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([EvccBinarySensor(coordinator, *item) for item in ITEMS])


class EvccBinarySensor(EvccEntity, BinarySensorEntity):
    def __init__(self, coordinator, key, name, device_class) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool:
        state = self.coordinator.state
        if self.entity_description_key == "token_valid":
            # yamlSource=file is a configuration/update conflict, not proof that
            # the currently active token is invalid.
            return bool(
                state.active_expiry
                and state.active_expiry > datetime.now(UTC)
                and state.sponsor
                and state.sponsor.name
            )
        if self.entity_description_key == "new_trial_token_available":
            return state.candidate_is_newer
        if self.entity_description_key == "token_update_required":
            return state.updater_status in {
                UpdaterStatus.UPDATE_DUE,
                UpdaterStatus.WARNING,
                UpdaterStatus.CRITICAL,
                UpdaterStatus.EXPIRED,
            }
        if self.entity_description_key == "api_reachable":
            return state.reachable
        return state.updater_status in {
            UpdaterStatus.WARNING,
            UpdaterStatus.CRITICAL,
            UpdaterStatus.EXPIRED,
            UpdaterStatus.SOURCE_ERROR,
            UpdaterStatus.EVCC_ERROR,
            UpdaterStatus.AUTH_ERROR,
            UpdaterStatus.CONFIGURATION_ERROR,
        }
