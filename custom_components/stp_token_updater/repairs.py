"""Home Assistant Repairs integration points."""

from __future__ import annotations

import logging

from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def async_create_or_update(hass, issue_id: str, *, critical: bool = False) -> None:
    """Create/update a translated issue without secret-bearing placeholders."""
    try:
        async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            translation_key=issue_id,
            severity=IssueSeverity.ERROR if critical else IssueSeverity.WARNING,
            is_fixable=False,
        )
    except Exception:  # pragma: no cover - compatibility guard for HA API changes
        _LOGGER.debug("Could not create repair %s", issue_id, exc_info=True)


def async_delete(hass, issue_id: str) -> None:
    """Delete a resolved integration Repair issue."""
    try:
        async_delete_issue(hass, DOMAIN, issue_id)
    except Exception:  # pragma: no cover - compatibility guard for HA API changes
        _LOGGER.debug("Could not delete repair %s", issue_id, exc_info=True)
