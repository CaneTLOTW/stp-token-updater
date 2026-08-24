"""STP Token Updater Home Assistant integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EvccClient
from .const import (
    AUTH_API_KEY,
    CONF_API_KEY,
    CONF_AUTH_METHOD,
    CONF_EVCC_URL,
    CONF_PASSWORD,
    DOMAIN,
)
from .coordinator import EvccTokenCoordinator
from .models import AuthMethod
from .storage import MetadataStore
from .trial_source import TrialTokenSource

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    auth_method = AuthMethod(entry.data[CONF_AUTH_METHOD])
    session = async_get_clientsession(hass)
    client = EvccClient(
        base_url=entry.data[CONF_EVCC_URL],
        session=session,
        auth_method=auth_method,
        api_key=entry.data.get(CONF_API_KEY),
        password=entry.data.get(CONF_PASSWORD),
    )
    store = MetadataStore(hass, entry.entry_id)
    await store.async_load()
    source = TrialTokenSource(session=session)
    coordinator = EvccTokenCoordinator(
        hass,
        entry=entry,
        client=client,
        source=source,
        store=store,
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "source": source,
        "store": store,
        "coordinator": coordinator,
    }
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded
