from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

from custom_components.stp_token_updater.config_flow import _auth_selector, normalize_url


def test_config_flow_auth_selector_builds() -> None:
    assert _auth_selector() is not None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("192.0.2.10", "http://192.0.2.10:7070"),
        ("http://192.0.2.10/", "http://192.0.2.10:7070"),
        ("https://provider.example:7443", "https://provider.example:7443"),
        ("http://[2001:db8::1]", "http://[2001:db8::1]:7070"),
    ],
)
def test_normalize_url(value: str, expected: str) -> None:
    assert normalize_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "ftp://provider.example",
        "http://user:secret@provider.example",
        "http://provider.example/api/state",
        "http://provider.example/?x=1",
    ],
)
def test_normalize_url_rejects_ambiguous_forms(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_url(value)
