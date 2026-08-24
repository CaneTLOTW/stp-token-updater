"""Manual controls using the same coordinator paths as automation."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .entity import EvccEntity


ITEMS = (
    ("check_trial_token", "Check Trial Token", "async_check_now"),
    ("apply_trial_token_now", "Apply Trial Token Now", "async_apply_now"),
    ("verify_active_token", "Verify Active Token", "async_verify_now"),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = hass.data["evcc_token_updater"][entry.entry_id]["coordinator"]
    async_add_entities([EvccButton(coordinator, *item) for item in ITEMS])


class EvccButton(EvccEntity, ButtonEntity):
    def __init__(self, coordinator, key, name, method) -> None:
        super().__init__(coordinator, key)
        self._attr_name = name
        self._method = method

    async def async_press(self) -> None:
        await getattr(self.coordinator, self._method)()
