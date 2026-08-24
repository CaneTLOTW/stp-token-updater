"""STP Token Updater sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime

from .const import DOMAIN
from .entity import EvccEntity


DESCRIPTIONS = (
    SensorEntityDescription(key="token_status", name="Token Status"),
    SensorEntityDescription(
        key="token_expires_at",
        name="Token Expires",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="token_remaining_hours",
        name="Token Remaining",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(key="token_type", name="Token Type"),
    SensorEntityDescription(
        key="trial_candidate_expires_at",
        name="Trial Candidate Expires",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="trial_candidate_remaining_hours",
        name="Trial Candidate Remaining",
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="token_next_attempt",
        name="Token Next Attempt",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="token_last_check",
        name="Token Last Check",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="token_last_source_check",
        name="Token Last Source Check",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="token_last_update",
        name="Token Last Update Attempt",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="token_last_success",
        name="Token Last Success",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(key="token_last_error", name="Token Last Error"),
    SensorEntityDescription(
        key="token_update_attempts",
        name="Token Update Attempts",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


def _value(state, key: str):
    if key == "token_status":
        return state.updater_status.value
    if key == "token_expires_at":
        return state.active_expiry
    if key == "token_remaining_hours":
        return state.remaining.total_seconds() / 3600 if state.remaining else None
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


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([EvccSensor(coordinator, description) for description in DESCRIPTIONS])


class EvccSensor(EvccEntity, SensorEntity):
    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_name = description.name

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
                active_token_fingerprint=(state.sponsor.redacted_token or "REDACTED"),
            )
        if state.candidate:
            attrs.update(
                candidate_fingerprint=state.candidate.fingerprint,
                candidate_is_newer=state.candidate_is_newer,
                candidate_issuer=state.candidate.issuer,
                candidate_subject=state.candidate.subject,
            )
        attrs.update(
            consecutive_failures=state.consecutive_failures,
            last_error_class=state.last_error_class,
        )
        return attrs
