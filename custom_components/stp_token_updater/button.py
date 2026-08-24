"""Manual controls using the same coordinator paths as automation."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory

from . import StpConfigEntry
from .entity import StpEntity

DESCRIPTIONS = (
    ButtonEntityDescription(
        key="check_trial_token",
        translation_key="check_trial_token",
        icon="mdi:refresh",
        entity_category=EntityCategory.CONFIG,
    ),
    ButtonEntityDescription(
        key="apply_trial_token_now",
        translation_key="apply_trial_token_now",
        icon="mdi:key-change",
        entity_category=EntityCategory.CONFIG,
    ),
    ButtonEntityDescription(
        key="verify_active_token",
        translation_key="verify_active_token",
        icon="mdi:check-decagram",
        entity_category=EntityCategory.CONFIG,
    ),
)

_METHODS = {
    "check_trial_token": "async_check_now",
    "apply_trial_token_now": "async_apply_now",
    "verify_active_token": "async_verify_now",
}


async def async_setup_entry(hass, entry: StpConfigEntry, async_add_entities) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities([StpButton(coordinator, description) for description in DESCRIPTIONS])


class StpButton(StpEntity, ButtonEntity):
    """One translated STP action button."""

    def __init__(self, coordinator, description: ButtonEntityDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        await getattr(self.coordinator, _METHODS[self.entity_description.key])()
