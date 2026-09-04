from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.stp_token_updater.scheduler import (
    calculate_schedule,
    escalation_level,
)


def test_checkpoint_boundaries() -> None:
    expires = datetime(2026, 8, 25, 12, tzinfo=UTC)
    assert calculate_schedule(
        now=expires - timedelta(hours=49),
        expires_at=expires,
        last_action_at=None,
    ).due is False

    at_48 = calculate_schedule(
        now=expires - timedelta(hours=48),
        expires_at=expires,
        last_action_at=None,
    )
    assert at_48.due is True
    assert at_48.stage == "renewal_window"

    assert calculate_schedule(
        now=expires - timedelta(hours=12),
        expires_at=expires,
        last_action_at=expires - timedelta(hours=47),
    ).due is True
    assert calculate_schedule(
        now=expires - timedelta(hours=6),
        expires_at=expires,
        last_action_at=expires - timedelta(hours=11),
    ).due is True
    assert calculate_schedule(
        now=expires - timedelta(hours=1),
        expires_at=expires,
        last_action_at=expires - timedelta(hours=5),
    ).due is True


def test_processed_checkpoint_waits_for_next_one() -> None:
    expires = datetime(2026, 8, 25, 12, tzinfo=UTC)
    now = expires - timedelta(hours=40)
    result = calculate_schedule(
        now=now,
        expires_at=expires,
        last_action_at=expires - timedelta(hours=47),
    )
    assert result.due is False
    assert result.next_attempt == expires - timedelta(hours=12)
    assert result.stage == "t_minus_12h"


def test_expired_retry_is_six_hourly() -> None:
    expires = datetime(2026, 8, 25, 12, tzinfo=UTC)
    last = expires + timedelta(hours=1)
    assert calculate_schedule(
        now=last + timedelta(hours=5),
        expires_at=expires,
        last_action_at=last,
    ).due is False
    assert calculate_schedule(
        now=last + timedelta(hours=6),
        expires_at=expires,
        last_action_at=last,
    ).due is True


def test_evcc_zero_time_expiry_does_not_underflow() -> None:
    """An expired Go zero-time value must enter recovery before checkpoint math."""
    now = datetime(2026, 9, 4, 21, tzinfo=UTC)
    expires = datetime(1, 1, 1, tzinfo=UTC)

    result = calculate_schedule(
        now=now,
        expires_at=expires,
        last_action_at=None,
    )

    assert result.due is True
    assert result.next_attempt == now
    assert result.stage == "expired"


def test_missed_checkpoints_are_not_replayed_in_sequence() -> None:
    expires = datetime(2026, 8, 25, 12, tzinfo=UTC)
    now = expires - timedelta(minutes=30)
    result = calculate_schedule(now=now, expires_at=expires, last_action_at=None)
    assert result.due is True
    assert result.stage == "t_minus_1h"


def test_escalation_levels() -> None:
    expires = datetime(2026, 8, 25, 12, tzinfo=UTC)
    assert escalation_level(expires - timedelta(days=3), expires) == "normal"
    assert escalation_level(expires - timedelta(hours=7), expires) == "attention"
    assert escalation_level(expires - timedelta(hours=5), expires) == "warning"
    assert escalation_level(expires - timedelta(minutes=30), expires) == "critical"
    assert escalation_level(expires + timedelta(seconds=1), expires) == "expired"
