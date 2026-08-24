from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")


def test_coordinator_module_imports_with_home_assistant():
    import custom_components.evcc_token_updater.coordinator  # noqa: F401
