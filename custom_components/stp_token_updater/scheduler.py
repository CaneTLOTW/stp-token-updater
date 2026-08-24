"""Pure expiry-based scheduler; no network or Home Assistant dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .const import POST_EXPIRY_RETRY, RETRY_1H, RETRY_6H, RETRY_12H


@dataclass(frozen=True, slots=True)
class ScheduleDecision:
    """One scheduler decision."""

    due: bool
    next_attempt: datetime
    stage: str


def calculate_schedule(
    *,
    now: datetime,
    expires_at: datetime,
    last_action_at: datetime | None,
    renewal_window_hours: int = 48,
) -> ScheduleDecision:
    """Calculate the currently due checkpoint and next planned attempt."""
    if now.tzinfo is None or expires_at.tzinfo is None:
        raise ValueError("now and expires_at must be timezone-aware")
    renewal_window = timedelta(hours=renewal_window_hours)
    checkpoints = [
        (expires_at - renewal_window, "renewal_window"),
        (expires_at - RETRY_12H, "t_minus_12h"),
        (expires_at - RETRY_6H, "t_minus_6h"),
        (expires_at - RETRY_1H, "t_minus_1h"),
    ]
    if now < checkpoints[0][0]:
        return ScheduleDecision(False, checkpoints[0][0], "healthy")
    if now >= expires_at:
        if last_action_at is None or last_action_at < expires_at:
            return ScheduleDecision(True, now, "expired")
        next_attempt = last_action_at + POST_EXPIRY_RETRY
        return ScheduleDecision(now >= next_attempt, max(now, next_attempt), "expired")

    crossed = max(i for i, (at, _stage) in enumerate(checkpoints) if now >= at)
    current_at, stage = checkpoints[crossed]
    if last_action_at is None or last_action_at < current_at:
        return ScheduleDecision(True, now, stage)
    if crossed + 1 < len(checkpoints):
        next_at, next_stage = checkpoints[crossed + 1]
        return ScheduleDecision(False, next_at, next_stage)
    return ScheduleDecision(False, expires_at, "expiry")


def remaining_hours(now: datetime, expires_at: datetime) -> float:
    return (expires_at - now).total_seconds() / 3600


def escalation_level(now: datetime, expires_at: datetime, warning_hours: int = 6) -> str:
    """Return warning severity independent from write scheduling."""
    remaining = expires_at - now
    if remaining <= timedelta(0):
        return "expired"
    if remaining <= RETRY_1H:
        return "critical"
    if remaining <= timedelta(hours=warning_hours):
        return "warning"
    if remaining <= RETRY_12H:
        return "attention"
    return "normal"
