"""Secret-safe Home Assistant diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from . import StpConfigEntry
from .const import CONF_AUTH_METHOD, VERSION
from .token import short_fingerprint


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: StpConfigEntry,
) -> dict:
    """Return only sanitized runtime/configuration information."""
    coordinator = entry.runtime_data.coordinator
    state = coordinator.state
    sponsor = state.sponsor
    active_fingerprint = coordinator.store.data.get("active_token_fingerprint")
    return {
        "integration_version": VERSION,
        "entry_id": entry.entry_id,
        "provider_url": "REDACTED",
        "auth_method": entry.data.get(CONF_AUTH_METHOD),
        "credentials": "REDACTED",
        "options": dict(entry.options),
        "state": {
            "provider_version": state.provider_version,
            "reachable": state.reachable,
            "updater_status": state.updater_status.value,
            "active_expiry": state.active_expiry.isoformat() if state.active_expiry else None,
            "active_fingerprint": (
                short_fingerprint(active_fingerprint)
                if isinstance(active_fingerprint, str)
                else None
            ),
            "candidate_expiry": (
                state.candidate.expires_at.isoformat() if state.candidate else None
            ),
            "candidate_fingerprint": (
                short_fingerprint(state.candidate.fingerprint) if state.candidate else None
            ),
            "candidate_is_newer": state.candidate_is_newer,
            "next_attempt": state.next_attempt.isoformat() if state.next_attempt else None,
            "retry_not_before": (
                state.retry_not_before.isoformat() if state.retry_not_before else None
            ),
            "last_check": state.last_check.isoformat() if state.last_check else None,
            "last_source_check": (
                state.last_source_check.isoformat() if state.last_source_check else None
            ),
            "last_update_attempt": (
                state.last_update_attempt.isoformat() if state.last_update_attempt else None
            ),
            "last_success": state.last_success.isoformat() if state.last_success else None,
            "last_error": state.last_error,
            "last_error_class": state.last_error_class,
            "consecutive_failures": state.consecutive_failures,
            "update_attempts": state.update_attempts,
            "dry_run": state.dry_run,
            "sponsor": {
                "name": sponsor.name if sponsor else None,
                "expires_soon": sponsor.expires_soon if sponsor else None,
                "yaml_source": sponsor.yaml_source if sponsor else None,
                "token": "REDACTED" if sponsor and sponsor.redacted_token else None,
            },
        },
    }
