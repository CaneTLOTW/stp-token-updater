"""JWT metadata parsing for the public trial token."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from .const import TRIAL_ISSUER, TRIAL_SUBJECT
from .models import TrialTokenCandidate, TrialTokenMetadata

JWT_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"([A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})"
    r"(?![A-Za-z0-9_-])"
)
DEFAULT_MAX_TRIAL_HORIZON = timedelta(days=31)


class TrialTokenParseError(ValueError):
    """The candidate is not a plausible trial JWT."""


def fingerprint_token(token: str) -> str:
    """Return a non-reversible full SHA-256 fingerprint."""
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def short_fingerprint(fingerprint: str, length: int = 12) -> str:
    return f"sha256:{fingerprint.removeprefix('sha256:')[:length]}"


def _decode_segment(segment: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(segment + ("=" * (-len(segment) % 4)))
    except Exception as exc:  # pragma: no cover - decoder implementation detail
        raise TrialTokenParseError("invalid base64url payload") from exc


def _timestamp(value: Any, name: str) -> datetime:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TrialTokenParseError(f"{name} is not numeric")
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise TrialTokenParseError(f"invalid {name} timestamp") from exc


def parse_trial_token(
    token: str,
    *,
    now: datetime | None = None,
    max_horizon: timedelta = DEFAULT_MAX_TRIAL_HORIZON,
) -> TrialTokenCandidate:
    """Decode claims only; the upstream provider remains signature authority."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise TrialTokenParseError("JWT must contain exactly three non-empty parts")
    try:
        payload = json.loads(_decode_segment(parts[1]))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrialTokenParseError("JWT payload is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise TrialTokenParseError("JWT payload is not an object")
    if payload.get("iss") != TRIAL_ISSUER:
        raise TrialTokenParseError("unexpected JWT issuer")
    if payload.get("sub") != TRIAL_SUBJECT:
        raise TrialTokenParseError("unexpected JWT subject")
    expires_at = _timestamp(payload.get("exp"), "exp")
    if expires_at <= now:
        raise TrialTokenParseError("trial token is expired")
    if expires_at - now > max_horizon:
        raise TrialTokenParseError("trial token expiry is outside plausible horizon")
    issued_at = None
    if payload.get("iat") is not None:
        issued_at = _timestamp(payload["iat"], "iat")
        if issued_at > now + timedelta(minutes=10):
            raise TrialTokenParseError("trial token issued-at is in the future")
        if issued_at >= expires_at:
            raise TrialTokenParseError("trial token issued-at is not before expiry")
    return TrialTokenCandidate(
        token=token,
        metadata=TrialTokenMetadata(
            issuer=TRIAL_ISSUER,
            subject=TRIAL_SUBJECT,
            issued_at=issued_at,
            expires_at=expires_at,
            fingerprint=fingerprint_token(token),
        ),
    )


def extract_trial_candidates(
    content: str,
    *,
    now: datetime | None = None,
    max_horizon: timedelta = DEFAULT_MAX_TRIAL_HORIZON,
) -> list[TrialTokenCandidate]:
    candidates: dict[str, TrialTokenCandidate] = {}
    for match in JWT_RE.finditer(content):
        try:
            candidate = parse_trial_token(match.group(1), now=now, max_horizon=max_horizon)
        except TrialTokenParseError:
            continue
        candidates[candidate.metadata.fingerprint] = candidate
    return sorted(candidates.values(), key=lambda item: item.metadata.expires_at)


def select_latest_trial_candidate(
    content: str,
    *,
    now: datetime | None = None,
    max_horizon: timedelta = DEFAULT_MAX_TRIAL_HORIZON,
) -> TrialTokenCandidate:
    candidates = extract_trial_candidates(content, now=now, max_horizon=max_horizon)
    if not candidates:
        raise TrialTokenParseError("no valid trial token found")
    return candidates[-1]
