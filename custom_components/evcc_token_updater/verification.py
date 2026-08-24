"""Single-write, delayed read-after-write verification."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from .api import EvccClient, EvccConnectionError
from .models import TokenUpdateResult, TrialTokenCandidate

DEFAULT_FIRST_DELAY = 3.0
DEFAULT_SECOND_DELAY = 5.0
DEFAULT_EXPIRY_TOLERANCE = timedelta(seconds=120)


def _matches(status, candidate, previous_expiry, tolerance):
    if status is None:
        return False, "sponsor_status_missing"
    if status.yaml_source == "file":
        return False, "sponsor_token_managed_by_yaml"
    if not status.name:
        return False, "sponsor_not_authorized"
    if status.expires_at is None:
        return False, "observed_expiry_missing"
    if previous_expiry is not None and status.expires_at <= previous_expiry:
        return False, "observed_expiry_not_newer"
    if abs(status.expires_at - candidate.metadata.expires_at) > tolerance:
        return False, "observed_expiry_does_not_match_candidate"
    return True, None


async def async_apply_and_verify(
    client: EvccClient,
    candidate: TrialTokenCandidate,
    *,
    first_delay: float = DEFAULT_FIRST_DELAY,
    second_delay: float = DEFAULT_SECOND_DELAY,
    tolerance: timedelta = DEFAULT_EXPIRY_TOLERANCE,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    now: Callable[[], datetime] | None = None,
) -> TokenUpdateResult:
    """Apply exactly once, then verify with delayed readback."""
    now_fn = now or (lambda: datetime.now(UTC))
    before = await client.async_get_sponsor_status()
    previous_expiry = before.expires_at if before else None

    if before and before.yaml_source == "file":
        return TokenUpdateResult(
            False,
            previous_expiry,
            candidate.metadata.expires_at,
            previous_expiry,
            now_fn(),
            "sponsor_token_managed_by_yaml",
        )

    if previous_expiry is not None and candidate.metadata.expires_at <= previous_expiry:
        return TokenUpdateResult(
            False,
            previous_expiry,
            candidate.metadata.expires_at,
            previous_expiry,
            now_fn(),
            "candidate_not_newer",
        )

    post_uncertain = False
    try:
        await client.async_set_sponsor_token(candidate.token)
    except EvccConnectionError:
        post_uncertain = True

    await sleep(first_delay)
    first = await client.async_get_sponsor_status()
    matched, reason = _matches(first, candidate, previous_expiry, tolerance)
    if matched:
        return TokenUpdateResult(
            True,
            previous_expiry,
            candidate.metadata.expires_at,
            first.expires_at,
            now_fn(),
        )

    await sleep(second_delay)
    second = await client.async_get_sponsor_status()
    matched, second_reason = _matches(second, candidate, previous_expiry, tolerance)
    if matched:
        return TokenUpdateResult(
            True,
            previous_expiry,
            candidate.metadata.expires_at,
            second.expires_at,
            now_fn(),
        )

    failure = second_reason or reason or "verification_failed"
    if post_uncertain:
        failure = f"post_uncertain_and_{failure}"
    return TokenUpdateResult(
        False,
        previous_expiry,
        candidate.metadata.expires_at,
        second.expires_at if second else None,
        now_fn(),
        failure,
    )
