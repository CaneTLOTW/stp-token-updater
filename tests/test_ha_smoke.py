from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("homeassistant")

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "stp_token_updater"


def test_sensor_descriptions_use_translation_keys() -> None:
    from custom_components.stp_token_updater.sensor import DESCRIPTIONS

    assert DESCRIPTIONS
    assert all(description.translation_key for description in DESCRIPTIONS)
    assert {description.key for description in DESCRIPTIONS} >= {
        "token_status",
        "token_expires_at",
        "token_remaining_hours",
    }


def test_repairs_module_uses_current_issue_registry_api() -> None:
    from custom_components.stp_token_updater import repairs

    assert callable(repairs.async_create_or_update)
    assert callable(repairs.async_delete)


def test_custom_integration_translation_files_are_self_contained() -> None:
    en = json.loads((INTEGRATION / "translations" / "en.json").read_text())
    de = json.loads((INTEGRATION / "translations" / "de.json").read_text())
    for payload in (en, de):
        assert "config" in payload
        assert "options" in payload
        assert "entity" in payload
        assert "issues" in payload
    assert not (INTEGRATION / "strings.json").exists()


def test_manifest_matches_new_public_domain() -> None:
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    assert manifest["domain"] == "stp_token_updater"
    assert manifest["name"] == "STP Token Updater"
    assert manifest["version"] == "0.2.0"


def test_legacy_integration_directory_is_absent() -> None:
    assert not (ROOT / "custom_components" / "evcc_token_updater").exists()
