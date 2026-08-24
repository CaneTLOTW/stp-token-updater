"""Secret-safe Home Assistant diagnostics."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry):
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime["coordinator"]
    state = coordinator.state
    sponsor = state.sponsor
    return {
        "integration_version": "0.1.0",
        "entry_id": entry.entry_id,
        "evcc_url": entry.data.get("evcc_url"),
        "auth_method": entry.data.get("auth_method"),
        "credentials": {"api_key": "REDACTED", "password": "REDACTED"},
        "state": {
            "evcc_version": state.evcc_version,
            "reachable": state.reachable,
            "updater_status": state.updater_status.value,
            "active_expiry": state.active_expiry.isoformat() if state.active_expiry else None,
            "candidate_expiry": state.candidate.expires_at.isoformat() if state.candidate else None,
            "candidate_fingerprint": state.candidate.fingerprint if state.candidate else None,
            "candidate_is_newer": state.candidate_is_newer,
            "last_check": state.last_check.isoformat() if state.last_check else None,
            "last_source_check": state.last_source_check.isoformat() if state.last_source_check else None,
            "last_update_attempt": state.last_update_attempt.isoformat() if state.last_update_attempt else None,
            "last_success": state.last_success.isoformat() if state.last_success else None,
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
