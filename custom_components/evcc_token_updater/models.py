"""Data models shared by the integration and its pure logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class AuthMethod(StrEnum):
    API_KEY = "api_key"
    PASSWORD = "password"


class UpdaterStatus(StrEnum):
    HEALTHY = "healthy"
    CHECKING = "checking"
    NEW_TOKEN_AVAILABLE = "new_token_available"
    UPDATE_DUE = "update_due"
    APPLYING = "applying"
    VERIFYING = "verifying"
    WARNING = "warning"
    CRITICAL = "critical"
    EXPIRED = "expired"
    SOURCE_ERROR = "source_error"
    PROVIDER_ERROR = "provider_error"
    AUTH_ERROR = "auth_error"
    CONFIGURATION_ERROR = "configuration_error"


@dataclass(frozen=True, slots=True)
class SponsorStatus:
    name: str | None
    expires_at: datetime | None
    expires_soon: bool
    redacted_token: str | None
    yaml_source: str | None


@dataclass(frozen=True, slots=True)
class TrialTokenMetadata:
    issuer: str
    subject: str
    issued_at: datetime | None
    expires_at: datetime
    fingerprint: str


@dataclass(frozen=True, slots=True)
class TrialTokenCandidate:
    """A short-lived candidate. Never expose ``token`` in repr/log output."""

    token: str
    metadata: TrialTokenMetadata

    def __repr__(self) -> str:
        return (
            "TrialTokenCandidate("
            f"expires_at={self.metadata.expires_at!r}, "
            f"fingerprint={self.metadata.fingerprint!r})"
        )


@dataclass(frozen=True, slots=True)
class TokenUpdateResult:
    success: bool
    previous_expiry: datetime | None
    candidate_expiry: datetime
    observed_expiry: datetime | None
    verified_at: datetime
    reason: str | None = None


@dataclass(slots=True)
class UpdaterState:
    provider_version: str | None = None
    reachable: bool = False
    sponsor: SponsorStatus | None = None
    active_expiry: datetime | None = None
    remaining: timedelta | None = None
    candidate: TrialTokenMetadata | None = None
    candidate_is_newer: bool = False
    next_attempt: datetime | None = None
    last_check: datetime | None = None
    last_source_check: datetime | None = None
    last_update_attempt: datetime | None = None
    last_success: datetime | None = None
    last_error: str | None = None
    last_error_class: str | None = None
    consecutive_failures: int = 0
    update_attempts: int = 0
    updater_status: UpdaterStatus = UpdaterStatus.CHECKING
    dry_run: bool = False
