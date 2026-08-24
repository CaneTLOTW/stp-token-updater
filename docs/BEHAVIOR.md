# Current behavior

STP Token Updater is a Home Assistant custom integration that monitors a local sponsor-token provider and renews an active trial token from the configured public source.

## Token lifecycle

The integration reads the active provider state and its expiry, fetches the public trial-token source on a separate schedule and validates candidate JWT metadata locally. A candidate is eligible only when it is valid for the expected trial-token protocol and expires strictly later than the active token.

Automatic renewal starts ahead of expiry, retries closer to expiry when necessary and continues with spaced retries after expiry until a verified replacement is observed. Provider polling, public-source polling and write scheduling are kept separate to avoid unnecessary source requests or write loops.

## Writes and verification

Automatic updates are enabled by default. Dry-Run is available as an optional mode and is disabled by default from v0.2.1.

For an eligible replacement STP performs at most one token POST for that attempt, then reads the provider state back after a delay. If the POST transport result is uncertain, STP verifies the resulting provider state instead of blindly posting again. A successful update requires the observed active expiry to advance and match the candidate within the accepted timestamp tolerance.

Provider rate limits and `Retry-After` are respected. A file/YAML-managed provider token is treated as an update conflict, not as proof that the active token itself is invalid.

## Authentication and Home Assistant

The provider can be accessed by API key or administrator password/session. Home Assistant Config Flow supports setup, reconfiguration, reauthentication and runtime options.

The integration provides translated sensors, binary sensors and buttons for token state, expiry, candidate availability, provider reachability and update diagnostics. Repairs and warning events surface conditions that require attention.

## Data handling

Full candidate JWTs are kept in memory only and are not persisted. Stored metadata is limited to lifecycle information required across restarts. Diagnostics redact credentials, cookies, tokens and configured provider network details.

## Restart behavior

After Home Assistant restarts, STP reloads persisted metadata, refreshes the actual provider state and resumes the lifecycle from the current time window. Missed checkpoints are not replayed as a burst of write attempts.

## Distribution

The integration is distributed through HACS. GitHub releases provide the update versions shown by HACS. CI validates the integration with pytest, HACS validation and hassfest before release publication.
