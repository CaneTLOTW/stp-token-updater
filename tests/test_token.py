from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest

from custom_components.evcc_token_updater.token import (
    TrialTokenParseError,
    parse_trial_token,
    select_latest_trial_candidate,
)


def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).decode().rstrip("=")


def _jwt(payload: dict, signature: str = "signature123") -> str:
    return f"{_b64({'alg': 'HS256', 'typ': 'JWT'})}.{_b64(payload)}.{signature}"


def test_valid_trial_and_secret_safe_repr() -> None:
    now = datetime(2026, 8, 24, 18, tzinfo=UTC)
    token = _jwt({"iss": "evcc.io", "sub": "trial", "iat": int(now.timestamp()), "exp": int((now + timedelta(days=7)).timestamp())})
    candidate = parse_trial_token(token, now=now)
    assert candidate.metadata.expires_at == now + timedelta(days=7)
    assert token not in repr(candidate)


@pytest.mark.parametrize("payload", [{"iss": "other", "sub": "trial"}, {"iss": "evcc.io", "sub": "other"}])
def test_reject_wrong_claims(payload: dict) -> None:
    now = datetime(2026, 8, 24, 18, tzinfo=UTC)
    payload["exp"] = int((now + timedelta(days=2)).timestamp())
    with pytest.raises(TrialTokenParseError):
        parse_trial_token(_jwt(payload), now=now)


def test_latest_valid_candidate_wins() -> None:
    now = datetime(2026, 8, 24, 18, tzinfo=UTC)
    older = _jwt({"iss": "evcc.io", "sub": "trial", "exp": int((now + timedelta(days=5)).timestamp())}, "signatureOLD")
    newer = _jwt({"iss": "evcc.io", "sub": "trial", "exp": int((now + timedelta(days=10)).timestamp())}, "signatureNEW")
    candidate = select_latest_trial_candidate(f"noise abc.def.ghi {older} {newer}", now=now)
    assert candidate.metadata.expires_at == now + timedelta(days=10)
