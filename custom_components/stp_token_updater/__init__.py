"""STP Token Updater Home Assistant integration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import ProviderClient
from .const import (
    CONF_API_KEY,
    CONF_AUTH_METHOD,
    CONF_PASSWORD,
    CONF_PROVIDER_URL,
    VERSION,
)
from .coordinator import StpTokenCoordinator
from .models import AuthMethod
from .storage import MetadataStore
from .trial_source import TrialTokenSource

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

_FRONTEND_FILE = Path(__file__).parent / "frontend" / "token-renewal-card.js"
_FRONTEND_URL = "/stp_token_updater/token-renewal-card.js"


@dataclass(slots=True)
class StpRuntimeData:
    """Objects that exist only while one config entry is loaded."""

    client: ProviderClient
    source: TrialTokenSource
    store: MetadataStore
    coordinator: StpTokenCoordinator


StpConfigEntry = ConfigEntry[StpRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the bundled dashboard card once when the integration loads."""
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                _FRONTEND_URL,
                str(_FRONTEND_FILE),
                cache_headers=True,
            )
        ]
    )
    add_extra_js_url(hass, f"{_FRONTEND_URL}?v={VERSION}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: StpConfigEntry) -> bool:
    """Set up one STP provider connection."""
    auth_method = AuthMethod(entry.data[CONF_AUTH_METHOD])
    session = async_get_clientsession(hass)
    client = ProviderClient(
        base_url=entry.data[CONF_PROVIDER_URL],
        session=session,
        auth_method=auth_method,
        api_key=entry.data.get(CONF_API_KEY),
        password=entry.data.get(CONF_PASSWORD),
    )
    store = MetadataStore(hass, entry.entry_id)
    await store.async_load()
    source = TrialTokenSource(session=session)
    coordinator = StpTokenCoordinator(
        hass,
        entry=entry,
        client=client,
        source=source,
        store=store,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = StpRuntimeData(client, source, store, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StpConfigEntry) -> bool:
    """Unload one STP config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
