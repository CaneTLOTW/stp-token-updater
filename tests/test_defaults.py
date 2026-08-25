"""Tests for production defaults."""

from custom_components.stp_token_updater.const import (
    DEFAULT_AUTOMATIC_UPDATES,
    DEFAULT_DRY_RUN,
    VERSION,
)


def test_production_defaults() -> None:
    """Automatic renewal is active unless Dry-Run is explicitly enabled."""
    assert VERSION == "0.2.2"
    assert DEFAULT_AUTOMATIC_UPDATES is True
    assert DEFAULT_DRY_RUN is False
