"""UI configuration, reconfiguration, reauthentication and options."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse, urlunparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    ProviderAuthenticationError,
    ProviderClient,
    ProviderConnectionError,
    ProviderError,
)
from .const import (
    AUTH_API_KEY,
    AUTH_PASSWORD,
    CONF_API_KEY,
    CONF_AUTH_METHOD,
    CONF_AUTOMATIC_UPDATES,
    CONF_DRY_RUN,
    CONF_PASSWORD,
    CONF_PROVIDER_URL,
    CONF_RENEWAL_WINDOW_HOURS,
    CONF_STATUS_REFRESH_MINUTES,
    CONF_VERIFICATION_DELAY_SECONDS,
    CONF_WARNING_HOURS,
    DEFAULT_AUTOMATIC_UPDATES,
    DEFAULT_DRY_RUN,
    DEFAULT_PROVIDER_PORT,
    DEFAULT_RENEWAL_WINDOW_HOURS,
    DEFAULT_STATUS_REFRESH_MINUTES,
    DEFAULT_VERIFICATION_DELAY_SECONDS,
    DEFAULT_WARNING_HOURS,
    DOMAIN,
)
from .models import AuthMethod

_LOGGER = logging.getLogger(__name__)


def normalize_url(value: str) -> str:
    """Normalize a direct provider base URL and reject ambiguous URL forms."""
    value = value.strip()
    if "://" not in value:
        value = f"http://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("invalid URL")
    if parsed.username or parsed.password:
        raise ValueError("userinfo is not allowed in provider URL")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("provider URL must not contain path, query or fragment")
    try:
        port = parsed.port or DEFAULT_PROVIDER_PORT
    except ValueError as exc:
        raise ValueError("invalid port") from exc
    hostname = parsed.hostname
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    return urlunparse((parsed.scheme, f"{hostname}:{port}", "", "", "", ""))


def _auth_selector() -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[AUTH_API_KEY, AUTH_PASSWORD],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key=CONF_AUTH_METHOD,
        )
    )


def _credential_selector() -> TextSelector:
    return TextSelector(
        TextSelectorConfig(
            type=TextSelectorType.PASSWORD,
            autocomplete="current-password",
        )
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up one direct token-provider connection."""

    VERSION = 1

    def __init__(self) -> None:
        self._input: dict[str, Any] = {}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                provider_url = normalize_url(user_input[CONF_PROVIDER_URL])
                self._abort_if_url_configured(provider_url)
                self._input = {
                    CONF_PROVIDER_URL: provider_url,
                    CONF_AUTH_METHOD: user_input[CONF_AUTH_METHOD],
                }
                return await self.async_step_credential()
            except ValueError:
                errors[CONF_PROVIDER_URL] = "invalid_url"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROVIDER_URL, default="http://"): str,
                    vol.Required(CONF_AUTH_METHOD, default=AUTH_API_KEY): _auth_selector(),
                }
            ),
            errors=errors,
        )

    async def async_step_credential(self, user_input=None) -> ConfigFlowResult:
        credential_key = self._credential_key()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._input, credential_key: user_input.get(credential_key, "")}
            error = await self._async_validate_data(data)
            if error is None:
                return self.async_create_entry(title="STP Token Updater", data=data)
            errors[credential_key if error == "invalid_auth" else "base"] = error
        return self.async_show_form(
            step_id="credential",
            data_schema=vol.Schema({vol.Required(credential_key): _credential_selector()}),
            errors=errors,
            description_placeholders={"auth_method": self._input[CONF_AUTH_METHOD]},
        )

    async def async_step_reconfigure(self, user_input=None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                provider_url = normalize_url(user_input[CONF_PROVIDER_URL])
                self._abort_if_url_configured(provider_url, exclude_entry_id=entry.entry_id)
                self._input = {
                    CONF_PROVIDER_URL: provider_url,
                    CONF_AUTH_METHOD: user_input[CONF_AUTH_METHOD],
                }
                return await self.async_step_reconfigure_credential()
            except ValueError:
                errors[CONF_PROVIDER_URL] = "invalid_url"
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PROVIDER_URL,
                        default=entry.data[CONF_PROVIDER_URL],
                    ): str,
                    vol.Required(
                        CONF_AUTH_METHOD,
                        default=entry.data[CONF_AUTH_METHOD],
                    ): _auth_selector(),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_credential(self, user_input=None) -> ConfigFlowResult:
        credential_key = self._credential_key()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._input, credential_key: user_input.get(credential_key, "")}
            error = await self._async_validate_data(data)
            if error is None:
                entry = self._get_reconfigure_entry()
                # Reconfiguration may switch auth methods, so remove the stale secret.
                clean_data = {
                    key: value
                    for key, value in data.items()
                    if key not in {CONF_API_KEY, CONF_PASSWORD} or key == credential_key
                }
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=clean_data,
                    reason="reconfigure_successful",
                )
            errors[credential_key if error == "invalid_auth" else "base"] = error
        return self.async_show_form(
            step_id="reconfigure_credential",
            data_schema=vol.Schema({vol.Required(credential_key): _credential_selector()}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data) -> ConfigFlowResult:
        """Start a Home Assistant linked reauthentication flow."""
        entry = self._get_reauth_entry()
        self._input = {CONF_PROVIDER_URL: entry.data[CONF_PROVIDER_URL]}
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        if user_input is not None:
            self._input[CONF_AUTH_METHOD] = user_input[CONF_AUTH_METHOD]
            return await self.async_step_reauth_credential()
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AUTH_METHOD,
                        default=entry.data[CONF_AUTH_METHOD],
                    ): _auth_selector()
                }
            ),
        )

    async def async_step_reauth_credential(self, user_input=None) -> ConfigFlowResult:
        credential_key = self._credential_key()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**self._input, credential_key: user_input.get(credential_key, "")}
            error = await self._async_validate_data(data)
            if error is None:
                entry = self._get_reauth_entry()
                clean_data = {
                    **entry.data,
                    CONF_AUTH_METHOD: data[CONF_AUTH_METHOD],
                    credential_key: data[credential_key],
                }
                stale_key = CONF_PASSWORD if credential_key == CONF_API_KEY else CONF_API_KEY
                clean_data.pop(stale_key, None)
                return self.async_update_reload_and_abort(
                    entry,
                    data=clean_data,
                    reason="reauth_successful",
                )
            errors[credential_key if error == "invalid_auth" else "base"] = error
        return self.async_show_form(
            step_id="reauth_credential",
            data_schema=vol.Schema({vol.Required(credential_key): _credential_selector()}),
            errors=errors,
        )

    def _credential_key(self) -> str:
        return (
            CONF_API_KEY
            if self._input[CONF_AUTH_METHOD] == AUTH_API_KEY
            else CONF_PASSWORD
        )

    def _abort_if_url_configured(
        self,
        provider_url: str,
        *,
        exclude_entry_id: str | None = None,
    ) -> None:
        for entry in self._async_current_entries():
            if entry.entry_id == exclude_entry_id:
                continue
            if entry.data.get(CONF_PROVIDER_URL) == provider_url:
                self.async_abort(reason="already_configured")
                raise config_entries.AbortFlow("already_configured")

    async def _async_validate_data(self, data: dict[str, Any]) -> str | None:
        credential_key = (
            CONF_API_KEY if data[CONF_AUTH_METHOD] == AUTH_API_KEY else CONF_PASSWORD
        )
        if not data.get(credential_key):
            return "invalid_auth"
        try:
            await _validate(hass=self.hass, data=data)
        except ProviderAuthenticationError:
            return "invalid_auth"
        except ProviderConnectionError:
            return "cannot_connect"
        except ProviderError:
            return "unsupported_provider"
        except Exception:  # pragma: no cover - defensive UI boundary
            _LOGGER.exception("Unexpected STP config-flow validation error")
            return "unknown"
        return None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()


class OptionsFlow(OptionsFlowWithReload):
    """Runtime-tuning options that automatically reload the config entry."""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_AUTOMATIC_UPDATES,
                    default=options.get(
                        CONF_AUTOMATIC_UPDATES,
                        DEFAULT_AUTOMATIC_UPDATES,
                    ),
                ): bool,
                vol.Optional(
                    CONF_DRY_RUN,
                    default=options.get(CONF_DRY_RUN, DEFAULT_DRY_RUN),
                ): bool,
                vol.Optional(
                    CONF_WARNING_HOURS,
                    default=options.get(CONF_WARNING_HOURS, DEFAULT_WARNING_HOURS),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=12)),
                vol.Optional(
                    CONF_RENEWAL_WINDOW_HOURS,
                    default=options.get(
                        CONF_RENEWAL_WINDOW_HOURS,
                        DEFAULT_RENEWAL_WINDOW_HOURS,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=12, max=168)),
                vol.Optional(
                    CONF_VERIFICATION_DELAY_SECONDS,
                    default=options.get(
                        CONF_VERIFICATION_DELAY_SECONDS,
                        DEFAULT_VERIFICATION_DELAY_SECONDS,
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=30)),
                vol.Optional(
                    CONF_STATUS_REFRESH_MINUTES,
                    default=options.get(
                        CONF_STATUS_REFRESH_MINUTES,
                        DEFAULT_STATUS_REFRESH_MINUTES,
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


async def _validate(*, hass, data: dict[str, Any]) -> None:
    session = async_get_clientsession(hass)
    method = AuthMethod(data[CONF_AUTH_METHOD])
    client = ProviderClient(
        base_url=data[CONF_PROVIDER_URL],
        session=session,
        auth_method=method,
        api_key=data.get(CONF_API_KEY),
        password=data.get(CONF_PASSWORD),
    )
    state = await client.async_get_state()
    if not ("sponsor" in state or "result" in state or "version" in state):
        raise ProviderError("response does not look like the expected token provider")
    await client.async_validate_credentials()
