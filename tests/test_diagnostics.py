from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("homeassistant")

from custom_components.stp_token_updater.const import (
    CONF_API_KEY,
    CONF_AUTH_METHOD,
    CONF_PROVIDER_URL,
)
from custom_components.stp_token_updater.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.stp_token_updater.models import SponsorStatus, UpdaterState


def test_diagnostics_redact_connection_and_credentials() -> None:
    state = UpdaterState(
        reachable=True,
        sponsor=SponsorStatus("trial", None, False, "***", "db"),
    )
    coordinator = SimpleNamespace(
        state=state,
        store=SimpleNamespace(data={}),
    )
    entry = SimpleNamespace(
        entry_id="test-entry",
        data={
            CONF_PROVIDER_URL: "http://192.0.2.44:7070",
            CONF_AUTH_METHOD: "api_key",
            CONF_API_KEY: "evcc_DO_NOT_EXPOSE",
        },
        options={},
        runtime_data=SimpleNamespace(coordinator=coordinator),
    )

    diagnostics = asyncio.run(async_get_config_entry_diagnostics(None, entry))
    rendered = repr(diagnostics)

    assert diagnostics["provider_url"] == "REDACTED"
    assert diagnostics["credentials"] == "REDACTED"
    assert "192.0.2.44" not in rendered
    assert "evcc_DO_NOT_EXPOSE" not in rendered
