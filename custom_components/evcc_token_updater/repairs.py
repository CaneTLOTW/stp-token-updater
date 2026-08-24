"""Home Assistant Repairs integration points."""

from __future__ import annotations

import logging

from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import (
    DOMAIN,
    REPAIR_AUTH,
    REPAIR_CRITICAL,
    REPAIR_EXPIRED,
    REPAIR_SOURCE,
    REPAIR_WARNING,
    REPAIR_YAML_CONFLICT,
)

_LOGGER = logging.getLogger(__name__)


def async_create_or_update(hass, issue_id: str, *, critical: bool = False) -> None:
    """Create or update a translated issue without placing secrets in its payload."""
    try:
        async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            translation_key=issue_id,
            severity=IssueSeverity.ERROR if critical else IssueSeverity.WARNING,
            is_fixable=False,
        )
    except Exception:  # pragma: no cover - HA API compatibility guard
        _LOGGER.debug("Could not create repair %s", issue_id, exc_info=True)


def async_delete(hass, issue_id: str) -> None:
    """Delete an integration repair issue when it is resolved."""
    try:
        async_delete_issue(hass, DOMAIN, issue_id)
    except Exception:  # pragma: no cover - HA API compatibility guard
        _LOGGER.debug("Could not delete repair %s", issue_id, exc_info=True)


__all__ = [
    "REPAIR_AUTH",
    "REPAIR_CRITICAL",
    "REPAIR_EXPIRED",
    "REPAIR_SOURCE",
    "REPAIR_WARNING",
    "REPAIR_YAML_CONFLICT",
    "async_create_or_update",
    "async_delete",
]
