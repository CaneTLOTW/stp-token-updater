from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")


def test_config_flow_auth_selector_builds() -> None:
    from custom_components.evcc_token_updater.config_flow import _auth_selector

    selector = _auth_selector()
    assert selector is not None


def test_sensor_descriptions_build_with_current_ha_api() -> None:
    from custom_components.evcc_token_updater.sensor import DESCRIPTIONS

    assert DESCRIPTIONS
    assert {description.key for description in DESCRIPTIONS} >= {
        "token_status",
        "token_expires_at",
        "token_remaining_hours",
    }
    assert all(description.name for description in DESCRIPTIONS)


def test_repairs_module_uses_current_issue_registry_api() -> None:
    from custom_components.evcc_token_updater import repairs

    assert callable(repairs.async_create_or_update)
    assert callable(repairs.async_delete)
