"""STP binary status entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from . import StpConfigEntry
from .entity import StpEntity
from .models import UpdaterStatus

DESCRIPTIONS = (
    BinarySensorEntityDescription(
        key="token_valid",
        translation_key="token_valid",
    ),
    BinarySensorEntityDescription(
        key="new_trial_token_available",
        translation_key="new_trial_token_available",
    ),
    BinarySensorEntityDescription(
        key="token_update_required",
        translation_key="token_update_required",
    ),
    BinarySensorEntityDescription(
        key="token_updater_problem",
        translation_key="token_updater_problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorEntityDescription(
        key="api_reachable",
        translation_key="api_reachable",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(hass, entry: StpConfigEntry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [StpBinarySensor(coordinator, description) for description in DESCRIPTIONS]
    )


class StpBinarySensor(StpEntity, BinarySensorEntity):
    """One translated STP binary sensor."""

    def __init__(self, coordinator, description: BinarySensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        state = self.coordinator.state
        key = self.entity_description.key
        if key == "token_valid":
            return bool(
                state.active_expiry
                and state.active_expiry > datetime.now(UTC)
                and state.sponsor is not None
                and state.sponsor.name
            )
        if key == "new_trial_token_available":
            return state.candidate_is_newer
        if key == "token_update_required":
            return bool(
                state.active_expiry
                and state.active_expiry - datetime.now(UTC)
                <= timedelta(hours=self.coordinator.renewal_window_hours)
            )
        if key == "api_reachable":
            return state.reachable
        return state.updater_status in {
            UpdaterStatus.WARNING,
            UpdaterStatus.CRITICAL,
            UpdaterStatus.EXPIRED,
            UpdaterStatus.SOURCE_ERROR,
            UpdaterStatus.PROVIDER_ERROR,
            UpdaterStatus.AUTH_ERROR,
            UpdaterStatus.RATE_LIMITED,
            UpdaterStatus.CONFIGURATION_CONFLICT,
        }
