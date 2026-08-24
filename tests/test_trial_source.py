from __future__ import annotations

import pytest

pytest.importorskip("aiohttp")

from custom_components.stp_token_updater.trial_source import TrialTokenSource


def test_trial_source_accepts_only_allowed_https_host() -> None:
    session = object()
    source = TrialTokenSource(session=session)  # type: ignore[arg-type]
    assert source.source_url.startswith("https://docs.evcc.io/")

    with pytest.raises(ValueError):
        TrialTokenSource(
            session=session,  # type: ignore[arg-type]
            source_url="http://docs.evcc.io/de/sponsorship/",
        )
    with pytest.raises(ValueError):
        TrialTokenSource(
            session=session,  # type: ignore[arg-type]
            source_url="https://example.invalid/trial",
        )
