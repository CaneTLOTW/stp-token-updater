"""Regression coverage for expired Retry-After coordinator gates.

These tests deliberately use only fakes. They must never contact the public
trial source or a real token provider.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.stp_token_updater import coordinator as coordinator_module
from custom_components.stp_token_updater.coordinator import StpTokenCoordinator
from custom_components.stp_token_updater.models import (
    TrialTokenCandidate,
    TrialTokenMetadata,
    UpdaterState,
)
from custom_components.stp_token_updater.trial_source import TrialSourceError

NOW = datetime(2026, 8, 24, 20, tzinfo=UTC)
ACTIVE_EXPIRY = NOW + timedelta(days=10)


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW if tz else NOW.replace(tzinfo=None)


class FakeStore:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.save_calls = 0

    async def async_save(self) -> None:
        self.save_calls += 1


class FakeProvider:
    def __init__(self) -> None:
        self.state_calls = 0
        self.post_calls = 0

    async def async_get_state(self) -> dict:
        self.state_calls += 1
        return {
            "version": "test",
            "sponsor": {
                "status": {
                    "name": "trial",
                    "expiresAt": ACTIVE_EXPIRY.isoformat(),
                    "expiresSoon": False,
                    "token": "REDACTED",
                }
            },
        }

    async def async_set_sponsor_token(self, _token: str) -> None:
        self.post_calls += 1


class FakeSource:
    def __init__(self, result: TrialTokenCandidate | Exception) -> None:
        self.result = result
        self.calls = 0

    async def async_get_latest(self, *, now: datetime) -> TrialTokenCandidate:
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _candidate(*, newer: bool) -> TrialTokenCandidate:
    expiry = ACTIVE_EXPIRY + timedelta(days=1) if newer else ACTIVE_EXPIRY
    return TrialTokenCandidate(
        "test.jwt.value",
        TrialTokenMetadata(
            "evcc.io",
            "trial",
            NOW,
            expiry,
            "sha256:regression-test",
        ),
    )


def _coordinator(source: FakeSource, store: FakeStore) -> StpTokenCoordinator:
    """Build just enough coordinator state for deterministic unit testing."""
    coordinator = object.__new__(StpTokenCoordinator)
    coordinator.hass = SimpleNamespace(bus=SimpleNamespace(async_fire=lambda *_: None))
    coordinator.entry = SimpleNamespace(entry_id="test", data={}, options={})
    coordinator.client = FakeProvider()
    coordinator.source = source
    coordinator.store = store
    coordinator.automatic_updates = True
    coordinator.dry_run = True
    coordinator.renewal_window_hours = 48
    coordinator.warning_hours = 6
    coordinator.verification_delay_seconds = 0
    coordinator._candidate = None
    coordinator._state = UpdaterState(dry_run=True)
    coordinator.data = None
    return coordinator


def _expired_write_gate() -> dict:
    return {
        "retry_not_before": (NOW - timedelta(minutes=1)).isoformat(),
        "rate_limit_scope": "write",
        "retry_apply_pending": True,
        "active_expires_at": ACTIVE_EXPIRY.isoformat(),
        "active_token_cycle_identifier": ACTIVE_EXPIRY.isoformat(),
    }


def _patch_runtime(monkeypatch, deleted: list[str]) -> None:
    monkeypatch.setattr(coordinator_module, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        coordinator_module,
        "async_delete",
        lambda _hass, issue_id: deleted.append(issue_id),
    )
    monkeypatch.setattr(
        coordinator_module,
        "async_create_or_update",
        lambda *_args, **_kwargs: None,
    )


def test_due_write_rate_retry_with_no_newer_candidate_clears_stale_gate(
    monkeypatch,
) -> None:
    """A due write gate refreshes source once, then cannot leave its Repair stuck."""
    deleted: list[str] = []
    _patch_runtime(monkeypatch, deleted)
    source = FakeSource(_candidate(newer=False))
    store = FakeStore(_expired_write_gate())
    coordinator = _coordinator(source, store)

    asyncio.run(coordinator._run_cycle())

    assert source.calls == 1
    assert coordinator.client.post_calls == 0
    assert store.data["retry_not_before"] is None
    assert store.data["rate_limit_scope"] is None
    assert store.data["retry_apply_pending"] is False
    assert coordinator_module.REPAIR_RATE_LIMIT in deleted

    # The completed gate must not turn the five-minute coordinator tick into
    # another immediate public-source request.
    asyncio.run(coordinator._run_cycle())
    assert source.calls == 1


def test_due_write_rate_retry_preserves_apply_intent_until_dry_run_decision(
    monkeypatch,
) -> None:
    """A pending write is considered only after a fresh candidate source read."""
    deleted: list[str] = []
    _patch_runtime(monkeypatch, deleted)
    source = FakeSource(_candidate(newer=True))
    store = FakeStore(_expired_write_gate())
    coordinator = _coordinator(source, store)

    state = asyncio.run(coordinator._run_cycle())

    assert source.calls == 1
    assert coordinator.client.post_calls == 0  # Dry-Run remains safe.
    assert state.last_error_class == "dry_run"
    assert store.data["retry_not_before"] is None
    assert store.data["retry_apply_pending"] is False
    assert coordinator_module.REPAIR_RATE_LIMIT in deleted


def test_due_retry_keeps_a_new_source_rate_limit(monkeypatch) -> None:
    """A newly received Retry-After replaces, rather than being cleared with, the old gate."""
    deleted: list[str] = []
    _patch_runtime(monkeypatch, deleted)
    retry_after = NOW + timedelta(hours=1)
    source = FakeSource(TrialSourceError("source limited", retry_after=retry_after))
    store = FakeStore(_expired_write_gate())
    coordinator = _coordinator(source, store)

    asyncio.run(coordinator._run_cycle())

    assert source.calls == 1
    assert store.data["rate_limit_scope"] == "source"
    assert store.data["retry_apply_pending"] is True
    assert store.data["retry_not_before"] == retry_after.isoformat()
    assert coordinator_module.REPAIR_RATE_LIMIT not in deleted


def test_future_state_rate_limit_blocks_manual_apply_without_network(
    monkeypatch,
) -> None:
    """Manual controls may not bypass a provider Retry-After gate."""
    deleted: list[str] = []
    _patch_runtime(monkeypatch, deleted)
    source = FakeSource(_candidate(newer=True))
    store = FakeStore(
        {
            **_expired_write_gate(),
            "retry_not_before": (NOW + timedelta(hours=1)).isoformat(),
            "rate_limit_scope": "state",
            "retry_apply_pending": False,
        }
    )
    coordinator = _coordinator(source, store)

    state = asyncio.run(coordinator._run_cycle(force_apply=True))

    assert coordinator.client.state_calls == 0
    assert source.calls == 0
    assert state.retry_not_before == NOW + timedelta(hours=1)
