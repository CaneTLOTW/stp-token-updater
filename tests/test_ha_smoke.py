from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("homeassistant")

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "stp_token_updater"


def _translation_shape(value):
    if isinstance(value, dict):
        return {key: _translation_shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_translation_shape(item) for item in value]
    return None


def test_sensor_descriptions_use_translation_keys() -> None:
    from custom_components.stp_token_updater.sensor import DESCRIPTIONS

    assert DESCRIPTIONS
    assert all(description.translation_key for description in DESCRIPTIONS)
    assert {description.key for description in DESCRIPTIONS} >= {
        "token_status",
        "token_expires_at",
        "token_remaining_hours",
    }


def test_entity_presentation_contract() -> None:
    from homeassistant.const import EntityCategory

    from custom_components.stp_token_updater.binary_sensor import (
        DESCRIPTIONS as BINARY_DESCRIPTIONS,
    )
    from custom_components.stp_token_updater.sensor import DESCRIPTIONS as SENSOR_DESCRIPTIONS

    sensors = {description.key: description for description in SENSOR_DESCRIPTIONS}
    binary = {description.key: description for description in BINARY_DESCRIPTIONS}

    assert sensors["token_remaining_hours"].suggested_display_precision == 1
    assert sensors["trial_candidate_remaining_hours"].suggested_display_precision == 1
    assert sensors["token_next_attempt"].entity_category is None
    assert binary["token_valid"].entity_category == EntityCategory.DIAGNOSTIC
    assert binary["token_updater_problem"].entity_category == EntityCategory.DIAGNOSTIC


def test_repairs_module_uses_current_issue_registry_api() -> None:
    from custom_components.stp_token_updater import repairs

    assert callable(repairs.async_create_or_update)
    assert callable(repairs.async_delete)


def test_custom_integration_translation_files_are_complete_and_in_sync() -> None:
    en = json.loads((INTEGRATION / "translations" / "en.json").read_text())
    de = json.loads((INTEGRATION / "translations" / "de.json").read_text())
    for payload in (en, de):
        assert "config" in payload
        assert "options" in payload
        assert "selector" in payload
        assert "entity" in payload
        assert "issues" in payload
    assert _translation_shape(en) == _translation_shape(de)
    assert not (INTEGRATION / "strings.json").exists()


def test_manifest_matches_new_public_domain() -> None:
    manifest = json.loads((INTEGRATION / "manifest.json").read_text())
    assert manifest["domain"] == "stp_token_updater"
    assert manifest["name"] == "STP Token Updater"
    assert manifest["version"] == "0.2.5"
    assert {"frontend", "http"}.issubset(manifest["dependencies"])


def test_hacs_metadata_has_no_unnecessary_home_assistant_minimum() -> None:
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert hacs["name"] == "STP Token Updater"
    assert "homeassistant" not in hacs


def test_local_brand_icon_is_bundled() -> None:
    icon = INTEGRATION / "brand" / "icon.png"
    assert icon.exists()
    assert icon.stat().st_size > 0


def test_dashboard_card_is_bundled_localized_and_has_english_fallback() -> None:
    card_path = INTEGRATION / "frontend" / "token-renewal-card.js"
    card = card_path.read_text()
    assert 'const CARD_TAG = "stp-token-renewal-card"' in card
    assert "const TRANSLATIONS" in card
    assert "language.startsWith(\"de\") ? \"de\" : \"en\"" in card
    assert 'problem: ["binary_sensor", "token_updater_problem"]' in card
    assert 'name: "STP Token Updater"' in card
    assert "window.customCards" in card
    assert "getEntitySuggestion" in card


def test_legacy_integration_directory_is_absent() -> None:
    assert not (ROOT / "custom_components" / "evcc_token_updater").exists()
