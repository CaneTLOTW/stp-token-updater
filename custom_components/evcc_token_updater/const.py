"""Constants for the STP Token Updater integration."""

from __future__ import annotations

from datetime import timedelta

# Internal integration domain/key names remain stable for compatibility. Provider-
# specific values below are protocol requirements and must not be anonymized.
DOMAIN = "evcc_token_updater"
VERSION = "0.1.0"

CONF_EVCC_URL = "evcc_url"
CONF_AUTH_METHOD = "auth_method"
CONF_API_KEY = "api_key"
CONF_PASSWORD = "password"
CONF_AUTOMATIC_UPDATES = "automatic_updates"
CONF_DRY_RUN = "dry_run"
CONF_RENEWAL_WINDOW_HOURS = "renewal_window_hours"
CONF_WARNING_HOURS = "warning_hours"
CONF_VERIFICATION_DELAY_SECONDS = "verification_delay_seconds"
CONF_STATUS_REFRESH_MINUTES = "status_refresh_minutes"

AUTH_API_KEY = "api_key"
AUTH_PASSWORD = "password"

DEFAULT_SOURCE_URL = "https://docs.evcc.io/de/sponsorship/"
ALLOWED_SOURCE_HOSTS = frozenset({"docs.evcc.io"})

DEFAULT_AUTOMATIC_UPDATES = True
DEFAULT_DRY_RUN = True
DEFAULT_RENEWAL_WINDOW_HOURS = 48
DEFAULT_WARNING_HOURS = 6
DEFAULT_VERIFICATION_DELAY_SECONDS = 3
DEFAULT_STATUS_REFRESH_MINUTES = 5

RETRY_12H = timedelta(hours=12)
RETRY_6H = timedelta(hours=6)
RETRY_1H = timedelta(hours=1)
POST_EXPIRY_RETRY = timedelta(hours=6)
SOURCE_REFRESH_NORMAL = timedelta(hours=6)
SOURCE_REFRESH_RENEWAL = timedelta(hours=3)
SOURCE_REFRESH_WARNING = timedelta(hours=1)

EVENT_WARNING = "stp_token_updater_warning"

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.metadata"

REPAIR_AUTH = "authentication"
REPAIR_SOURCE = "trial_source"
REPAIR_WARNING = "renewal_warning"
REPAIR_CRITICAL = "renewal_critical"
REPAIR_EXPIRED = "token_expired"
REPAIR_YAML_CONFLICT = "yaml_conflict"
