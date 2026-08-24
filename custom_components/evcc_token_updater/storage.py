"""Persistent non-secret lifecycle metadata."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION


class MetadataStore:
    def __init__(self, hass, entry_id: str) -> None:
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")
        self.data: dict[str, Any] = {}

    async def async_load(self) -> dict[str, Any]:
        loaded = await self._store.async_load()
        self.data = loaded if isinstance(loaded, dict) else {}
        return self.data

    async def async_save(self, data: dict[str, Any] | None = None) -> None:
        if data is not None:
            self.data = data
        await self._store.async_save(self.data)


StoreMetadata = MetadataStore
