from __future__ import annotations

from datetime import UTC, datetime

from custom_components.evcc_token_updater.api import parse_sponsor_status


def test_parse_wrapped_sponsor_state() -> None:
    status = parse_sponsor_status({"result": {"sponsor": {"status": {"name": "trial", "expiresAt": "2026-08-25T12:00:00Z", "expiresSoon": True, "token": "***"}, "yamlSource": "db"}}})
    assert status is not None
    assert status.name == "trial"
    assert status.expires_at == datetime(2026, 8, 25, 12, tzinfo=UTC)
    assert status.yaml_source == "db"


def test_parse_direct_and_missing_sponsor() -> None:
    assert parse_sponsor_status({"sponsor": {"status": None}}).expires_at is None
    assert parse_sponsor_status({"version": "0.1"}) is None
