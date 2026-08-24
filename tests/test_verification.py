from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.stp_token_updater.api import (
    ProviderAuthenticationError,
    ProviderConnectionError,
)
from custom_components.stp_token_updater.models import (
    SponsorStatus,
    TrialTokenCandidate,
    TrialTokenMetadata,
)
from custom_components.stp_token_updater.verification import async_apply_and_verify


def _candidate(now: datetime) -> TrialTokenCandidate:
    return TrialTokenCandidate(
        "header.payload.signature",
        TrialTokenMetadata(
            "evcc.io",
            "trial",
            now,
            now + timedelta(days=7),
            "sha256:test",
        ),
    )


class FakeClient:
    def __init__(self, statuses, *, post_error: Exception | None = None):
        self.statuses = iter(statuses)
        self.posted = 0
        self.post_error = post_error

    async def async_get_sponsor_status(self):
        value = next(self.statuses)
        if isinstance(value, Exception):
            raise value
        return value

    async def async_set_sponsor_token(self, token):
        self.posted += 1
        if self.post_error:
            raise self.post_error


async def _no_sleep(_seconds: float) -> None:
    await asyncio.sleep(0)


def test_delayed_readback_succeeds_without_second_write() -> None:
    now = datetime(2026, 8, 24, 18, tzinfo=UTC)
    old = SponsorStatus("trial", now + timedelta(hours=1), False, "***", "db")
    new = SponsorStatus("trial", now + timedelta(days=7), False, "***", "db")
    client = FakeClient([old, old, new])
    result = asyncio.run(
        async_apply_and_verify(
            client,
            _candidate(now),
            first_delay=0,
            second_delay=0,
            sleep=_no_sleep,
        )
    )
    assert result.success is True
    assert client.posted == 1


def test_candidate_not_newer_never_posts() -> None:
    now = datetime(2026, 8, 24, 18, tzinfo=UTC)
    active = SponsorStatus("trial", now + timedelta(days=8), False, "***", "db")
    client = FakeClient([active])
    result = asyncio.run(
        async_apply_and_verify(client, _candidate(now), first_delay=0, second_delay=0)
    )
    assert result.success is False
    assert result.reason == "candidate_not_newer"
    assert client.posted == 0


def test_yaml_managed_token_never_posts() -> None:
    now = datetime(2026, 8, 24, 18, tzinfo=UTC)
    active = SponsorStatus("trial", now + timedelta(hours=1), False, "***", "file")
    client = FakeClient([active])
    result = asyncio.run(
        async_apply_and_verify(client, _candidate(now), first_delay=0, second_delay=0)
    )
    assert result.success is False
    assert result.reason == "sponsor_token_managed_by_yaml"
    assert client.posted == 0


def test_uncertain_post_is_verified_without_blind_retry() -> None:
    now = datetime(2026, 8, 24, 18, tzinfo=UTC)
    old = SponsorStatus("trial", now + timedelta(hours=1), False, "***", "db")
    new = SponsorStatus("trial", now + timedelta(days=7), False, "***", "db")
    client = FakeClient(
        [old, new],
        post_error=ProviderConnectionError("timeout after write"),
    )
    result = asyncio.run(
        async_apply_and_verify(
            client,
            _candidate(now),
            first_delay=0,
            second_delay=0,
            sleep=_no_sleep,
        )
    )
    assert result.success is True
    assert client.posted == 1


def test_first_readback_failure_can_recover_on_second_readback() -> None:
    now = datetime(2026, 8, 24, 18, tzinfo=UTC)
    old = SponsorStatus("trial", now + timedelta(hours=1), False, "***", "db")
    new = SponsorStatus("trial", now + timedelta(days=7), False, "***", "db")
    client = FakeClient([old, ProviderConnectionError("readback down"), new])
    result = asyncio.run(
        async_apply_and_verify(
            client,
            _candidate(now),
            first_delay=0,
            second_delay=0,
            sleep=_no_sleep,
        )
    )
    assert result.success is True
    assert client.posted == 1


def test_definite_auth_rejection_propagates() -> None:
    now = datetime(2026, 8, 24, 18, tzinfo=UTC)
    old = SponsorStatus("trial", now + timedelta(hours=1), False, "***", "db")
    client = FakeClient(
        [old],
        post_error=ProviderAuthenticationError("rejected"),
    )
    with pytest.raises(ProviderAuthenticationError):
        asyncio.run(
            async_apply_and_verify(
                client,
                _candidate(now),
                first_delay=0,
                second_delay=0,
                sleep=_no_sleep,
            )
        )
    assert client.posted == 1
