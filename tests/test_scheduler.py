from __future__ import annotations

from datetime import UTC, datetime, timedelta

from custom_components.evcc_token_updater.scheduler import calculate_schedule, escalation_level


def test_checkpoint_boundaries() -> None:
    expires = datetime(2026, 8, 25, 12, tzinfo=UTC)
    assert calculate_schedule(now=expires - timedelta(hours=49), expires_at=expires, last_attempt_at=None).due is False
    assert calculate_schedule(now=expires - timedelta(hours=48), expires_at=expires, last_attempt_at=None).stage == "t_minus_48h"
    assert calculate_schedule(now=expires - timedelta(hours=12), expires_at=expires, last_attempt_at=expires - timedelta(hours=47)).due is True
    assert calculate_schedule(now=expires - timedelta(hours=6), expires_at=expires, last_attempt_at=expires - timedelta(hours=11)).due is True
    assert calculate_schedule(now=expires - timedelta(hours=1), expires_at=expires, last_attempt_at=expires - timedelta(hours=5)).due is True


def test_expired_retry_is_six_hourly() -> None:
    expires = datetime(2026, 8, 25, 12, tzinfo=UTC)
    last = expires + timedelta(hours=1)
    assert calculate_schedule(now=last + timedelta(hours=5), expires_at=expires, last_attempt_at=last).due is False
    assert calculate_schedule(now=last + timedelta(hours=6), expires_at=expires, last_attempt_at=last).due is True


def test_escalation_levels() -> None:
    expires = datetime(2026, 8, 25, 12, tzinfo=UTC)
    assert escalation_level(expires - timedelta(days=3), expires) == "healthy"
    assert escalation_level(expires - timedelta(hours=7), expires) == "attention"
    assert escalation_level(expires - timedelta(hours=5), expires) == "warning"
    assert escalation_level(expires - timedelta(minutes=30), expires) == "critical"
    assert escalation_level(expires + timedelta(seconds=1), expires) == "expired"
