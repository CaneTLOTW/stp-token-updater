from __future__ import annotations

import pytest

pytest.importorskip("aiohttp")


def test_trial_source_module_imports():
    import custom_components.evcc_token_updater.trial_source  # noqa: F401
