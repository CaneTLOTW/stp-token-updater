from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.stp_token_updater.api import (
    parse_datetime,
    parse_retry_after,
    parse_sponsor_status,
)


def test_parse_wrapped_sponsor_state() -> None:
    status = parse_sponsor_status(
        {
            "result": {
                "sponsor": {
                    "status": {
                        "name": "trial",
                        "expiresAt": "2026-08-25T12:00:00Z",
                        "expiresSoon": True,
                        "token": "***",
                    },
                    "yamlSource": "db",
                }
            }
        }
    )
    assert status is not None
    assert status.name == "trial"
    assert status.expires_at == datetime(2026, 8, 25, 12, tzinfo=UTC)
    assert status.expires_soon is True
    assert status.yaml_source == "db"


def test_parse_direct_missing_and_file_managed_sponsor() -> None:
    missing = parse_sponsor_status({"version": "0.1"})
    assert missing is None

    file_managed = parse_sponsor_status(
        {"sponsor": {"status": None, "yamlSource": "file"}}
    )
    assert file_managed is not None
    assert file_managed.expires_at is None
    assert file_managed.yaml_source == "file"


def test_parse_datetime_normalizes_to_utc() -> None:
    assert parse_datetime("2026-08-25T14:00:00+02:00") == datetime(
        2026, 8, 25, 12, tzinfo=UTC
    )
    assert parse_datetime("not-a-date") is None


def test_retry_after_seconds_and_http_date() -> None:
    now = datetime(2026, 8, 24, 20, tzinfo=UTC)
    assert parse_retry_after("120", now=now) == now + timedelta(minutes=2)
    assert parse_retry_after("Mon, 24 Aug 2026 20:05:00 GMT", now=now) == now + timedelta(
        minutes=5
    )
    assert parse_retry_after("-1", now=now) is None
    assert parse_retry_after("nonsense", now=now) is None
