from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")


def test_config_flow_module_imports_with_home_assistant():
    import custom_components.evcc_token_updater.config_flow  # noqa: F401
