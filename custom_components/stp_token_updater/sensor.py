"""STP Token Updater sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime

from . import StpConfigEntry
from .entity import StpEntity
from .models import UpdaterStatus
from .token import short_fingerprint

_STATUS_OPTIONS = [status.value for status in UpdaterStatus]

DESCRIPTIONS = (
    SensorEntityDescription(
        key="token_status",
        translation_key="token_status",
        device_class=SensorDeviceClass.ENUM,
        options=_STATUS_OPTIONS,
    ),
    SensorEntityDescription(
        key="token_expires_at",
        translation_key="token_expires_at",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="token_remaining_hours",
        translation_key="token_remaining_hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="token_type",
        translation_key="token_type",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="trial_candidate_expires_at",
        translation_key="trial_candidate_expires_at",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="trial_candidate_remaining_hours",
        translation_key="trial_candidate_remaining_hours",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="token_next_attempt",
        translation_key="token_next_attempt",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="token_last_check",
        translation_key="token_last_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="token_last_source_check",
        translation_key="token_last_source_check",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="token_last_update",
        translation_key="token_last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="token_last_success",
        translation_key="token_last_success",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="token_last_error",
        translation_key="token_last_error",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="token_update_attempts",
        translation_key="token_update_attempts",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


def _value(state, key: str):
    if key == "token_status":
        return state.updater_status.value
    if key == "token_expires_at":
        return state.active_expiry
    if key == "token_remaining_hours":
        return state.remaining.total_seconds() / 3600 if state.remaining is not None else None
    if key == "token_type":
        return state.sponsor.name if state.sponsor and state.sponsor.name else "unknown"
    if key == "trial_candidate_expires_at":
        return state.candidate.expires_at if state.candidate else None
    if key == "trial_candidate_remaining_hours":
        if not state.candidate:
            return None
        return (
            state.candidate.expires_at
            - datetime.now(state.candidate.expires_at.tzinfo)
        ).total_seconds() / 3600
    if key == "token_next_attempt":
        return state.next_attempt
    if key == "token_last_check":
        return state.last_check
    if key == "token_last_source_check":
        return state.last_source_check
    if key == "token_last_update":
        return state.last_update_attempt
    if key == "token_last_success":
        return state.last_success
    if key == "token_last_error":
        return state.last_error
    if key == "token_update_attempts":
        return state.update_attempts
    return None


async def async_setup_entry(hass, entry: StpConfigEntry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([StpSensor(coordinator, description) for description in DESCRIPTIONS])


class StpSensor(StpEntity, SensorEntity):
    """One translated STP lifecycle sensor."""

    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return _value(self.coordinator.state, self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict:
        attrs = super().extra_state_attributes
        state = self.coordinator.state
        if state.sponsor:
            attrs.update(
                sponsor_name=state.sponsor.name,
                sponsor_expires_soon=state.sponsor.expires_soon,
                sponsor_yaml_source=state.sponsor.yaml_source,
            )
        active_fingerprint = self.coordinator.store.data.get("active_token_fingerprint")
        if isinstance(active_fingerprint, str):
            attrs["active_token_fingerprint"] = short_fingerprint(active_fingerprint)
        if state.candidate:
            attrs.update(
                candidate_fingerprint=short_fingerprint(state.candidate.fingerprint),
                candidate_is_newer=state.candidate_is_newer,
            )
        attrs.update(
            consecutive_failures=state.consecutive_failures,
            last_error_class=state.last_error_class,
            retry_not_before=(
                state.retry_not_before.isoformat() if state.retry_not_before else None
            ),
        )
        return attrs
