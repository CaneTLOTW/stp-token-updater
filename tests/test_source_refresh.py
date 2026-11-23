"""Source-refresh cadence regression tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.stp_token_updater.coordinator import StpTokenCoordinator


NOW = datetime(2026, 11, 23, 13, 0, tzinfo=UTC)


def _coordinator(*, active_expiry: datetime, last_source_check: datetime) -> StpTokenCoordinator:
    coordinator = object.__new__(StpTokenCoordinator)
    coordinator.store = SimpleNamespace(
        data={"last_source_check_at": last_source_check.isoformat()}
    )
    coordinator._state = SimpleNamespace(active_expiry=active_expiry)
    return coordinator


@pytest.mark.parametrize(
    ("active_expiry", "interval"),
    [
        (NOW - timedelta(minutes=1), timedelta(minutes=15)),
        (NOW + timedelta(hours=6), timedelta(hours=1)),
        (NOW + timedelta(hours=24), timedelta(hours=3)),
        (NOW + timedelta(hours=72), timedelta(hours=6)),
    ],
)
def test_source_refresh_intervals(active_expiry: datetime, interval: timedelta) -> None:
    """Each lifecycle stage uses its intended source-refresh cadence."""
    just_before = _coordinator(
        active_expiry=active_expiry,
        last_source_check=NOW - interval + timedelta(seconds=1),
    )
    assert just_before._source_due(NOW) is False

    due = _coordinator(
        active_expiry=active_expiry,
        last_source_check=NOW - interval,
    )
    assert due._source_due(NOW) is True


def test_expired_source_refresh_is_due_after_15_minutes() -> None:
    """Expired tokens must not wait hours for a replacement source token."""
    coordinator = _coordinator(
        active_expiry=NOW - timedelta(minutes=1),
        last_source_check=NOW - timedelta(minutes=15),
    )

    assert coordinator._source_due(NOW) is True
