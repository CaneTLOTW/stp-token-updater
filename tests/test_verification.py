from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from custom_components.evcc_token_updater.models import SponsorStatus, TrialTokenCandidate, TrialTokenMetadata
from custom_components.evcc_token_updater.verification import async_apply_and_verify


def _candidate(now: datetime) -> TrialTokenCandidate:
    token = "header.payload.signature"
    return TrialTokenCandidate(token, TrialTokenMetadata("evcc.io", "trial", now, now + timedelta(days=7), "sha256:test"))


class FakeClient:
    def __init__(self, statuses):
        self.statuses = iter(statuses)
        self.posted = 0

    async def async_get_sponsor_status(self):
        return next(self.statuses)

    async def async_set_sponsor_token(self, token):
        self.posted += 1


def test_delayed_readback_succeeds_without_second_write() -> None:
    now = datetime(2026, 8, 24, 18, tzinfo=UTC)
    old = SponsorStatus("trial", now + timedelta(hours=1), False, "***", "db")
    new = SponsorStatus("trial", now + timedelta(days=7), False, "***", "db")
    client = FakeClient([old, old, new])
    result = asyncio.run(async_apply_and_verify(client, _candidate(now), first_delay=0, second_delay=0, sleep=lambda _: asyncio.sleep(0)))
    assert result.success is True
    assert client.posted == 1
