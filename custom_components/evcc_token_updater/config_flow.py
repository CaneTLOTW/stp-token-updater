"""UI configuration and options flow."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import EvccAuthenticationError, EvccClient, EvccConnectionError, EvccError
from .const import (
    AUTH_API_KEY,
    AUTH_PASSWORD,
    CONF_API_KEY,
    CONF_AUTH_METHOD,
    CONF_AUTOMATIC_UPDATES,
    CONF_DRY_RUN,
    CONF_EVCC_URL,
    CONF_PASSWORD,
    CONF_RENEWAL_WINDOW_HOURS,
    CONF_STATUS_REFRESH_MINUTES,
    CONF_VERIFICATION_DELAY_SECONDS,
    CONF_WARNING_HOURS,
    DEFAULT_AUTOMATIC_UPDATES,
    DEFAULT_DRY_RUN,
    DEFAULT_RENEWAL_WINDOW_HOURS,
    DEFAULT_STATUS_REFRESH_MINUTES,
    DEFAULT_VERIFICATION_DELAY_SECONDS,
    DEFAULT_WARNING_HOURS,
    DOMAIN,
)
from .models import AuthMethod


def normalize_url(value: str) -> str:
    value = value.strip()
    if "://" not in value:
        value = f"http://{value}"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("invalid URL")
    if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("provider URL must be a base URL without a path")
    try:
        port = parsed.port or 7070
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


def _credential_selector():
    return TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Set up one direct provider connection."""

    VERSION = 1

    def __init__(self) -> None:
        self._input: dict = {}

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input:
            try:
                self._input = {
                    CONF_EVCC_URL: normalize_url(user_input[CONF_EVCC_URL]),
                    CONF_AUTH_METHOD: user_input[CONF_AUTH_METHOD],
                }
                return await self.async_step_credential()
            except ValueError:
                errors[CONF_EVCC_URL] = "invalid_url"
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EVCC_URL, default="http://"): str,
                    vol.Required(CONF_AUTH_METHOD, default=AUTH_API_KEY): _auth_selector(),
                }
            ),
            errors=errors,
        )

    async def async_step_credential(self, user_input=None):
        errors: dict[str, str] = {}
        credential_key = (
            CONF_API_KEY
            if self._input[CONF_AUTH_METHOD] == AUTH_API_KEY
            else CONF_PASSWORD
        )
        if user_input:
            try:
                credential = user_input[credential_key]
                if not credential:
                    raise ValueError("empty credential")
                data = {**self._input, credential_key: credential}
                await _validate(hass=self.hass, data=data)
                await self.async_set_unique_id(self._input[CONF_EVCC_URL])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="STP Token Updater", data=data)
            except ValueError:
                errors[credential_key] = "invalid_auth"
            except EvccAuthenticationError:
                errors[credential_key] = "invalid_auth"
            except EvccConnectionError:
                errors["base"] = "cannot_connect"
            except EvccError:
                errors["base"] = "unsupported_evcc"
        return self.async_show_form(
            step_id="credential",
            data_schema=vol.Schema(
                {vol.Required(credential_key): _credential_selector()}
            ),
            errors=errors,
            description_placeholders={"auth_method": self._input[CONF_AUTH_METHOD]},
        )

    async def async_step_reconfigure(self, user_input=None):
        errors: dict[str, str] = {}
        current = self._get_reconfigure_entry()
        if user_input:
            try:
                self._input = {
                    CONF_EVCC_URL: normalize_url(user_input[CONF_EVCC_URL]),
                    CONF_AUTH_METHOD: user_input[CONF_AUTH_METHOD],
                }
                return await self.async_step_reconfigure_credential()
            except ValueError:
                errors[CONF_EVCC_URL] = "invalid_url"
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EVCC_URL, default=current.data[CONF_EVCC_URL]
                    ): str,
                    vol.Required(
                        CONF_AUTH_METHOD, default=current.data[CONF_AUTH_METHOD]
                    ): _auth_selector(),
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure_credential(self, user_input=None):
        errors: dict[str, str] = {}
        credential_key = (
            CONF_API_KEY
            if self._input[CONF_AUTH_METHOD] == AUTH_API_KEY
            else CONF_PASSWORD
        )
        if user_input:
            try:
                data = {**self._input, credential_key: user_input[credential_key]}
                await _validate(hass=self.hass, data=data)
                entry = self._get_reconfigure_entry()
                new_unique_id = self._input[CONF_EVCC_URL]
                for existing in self._async_current_entries():
                    if (
                        existing.entry_id != entry.entry_id
                        and existing.unique_id == new_unique_id
                    ):
                        return self.async_abort(reason="already_configured")
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=data,
                    unique_id=new_unique_id,
                )
                return self.async_abort(reason="reconfigure_successful")
            except ValueError:
                errors[credential_key] = "invalid_auth"
            except EvccAuthenticationError:
                errors[credential_key] = "invalid_auth"
            except EvccConnectionError:
                errors["base"] = "cannot_connect"
            except EvccError:
                errors["base"] = "unsupported_evcc"
        return self.async_show_form(
            step_id="reconfigure_credential",
            data_schema=vol.Schema(
                {vol.Required(credential_key): _credential_selector()}
            ),
            errors=errors,
        )

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_AUTOMATIC_UPDATES,
                    default=options.get(
                        CONF_AUTOMATIC_UPDATES, DEFAULT_AUTOMATIC_UPDATES
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
                        CONF_RENEWAL_WINDOW_HOURS, DEFAULT_RENEWAL_WINDOW_HOURS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
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
                        CONF_STATUS_REFRESH_MINUTES, DEFAULT_STATUS_REFRESH_MINUTES
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


async def _validate(*, hass, data: dict) -> None:
    session = async_get_clientsession(hass)
    method = AuthMethod(data[CONF_AUTH_METHOD])
    client = EvccClient(
        base_url=data[CONF_EVCC_URL],
        session=session,
        auth_method=method,
        api_key=data.get(CONF_API_KEY),
        password=data.get(CONF_PASSWORD),
    )
    state = await client.async_get_state()
    if not isinstance(state, dict) or not (
        "sponsor" in state or "result" in state or "version" in state
    ):
        raise EvccError("response does not look like the expected provider")
    await client.async_validate_credentials()
