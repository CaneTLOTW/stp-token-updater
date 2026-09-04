# STP Token Updater

![STP Token Updater](assets/stp-token-updater.svg)

Home Assistant custom integration for monitoring and automatically renewing a sponsor/trial token through a local provider API.

[![Open your Home Assistant instance and add this repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=CaneTLOTW&repository=stp-token-updater&category=integration)

**STP = Sponsor Token Provider.** Provider-specific protocol identifiers are only kept where the upstream protocol requires them.

## What it does

STP Token Updater reads the current token state from the local provider, checks the public trial-token source, validates candidate metadata and automatically replaces the active token when a strictly newer valid candidate is available.

The integration includes:

- local provider access using API key or administrator password/session;
- automatic renewal scheduling with retries around token expiry;
- rate-limit handling including `Retry-After`;
- one-write-only update verification with readback after transport uncertainty;
- translated Home Assistant entities, buttons and Repairs;
- reauthentication, reconfiguration and runtime options;
- diagnostics with secret redaction;
- HACS installation and release-based updates.

The complete current behavior is summarized in [`docs/BEHAVIOR.md`](docs/BEHAVIOR.md).

## Installation via HACS

1. Add this repository to HACS as an **Integration** or use the HACS badge above.
2. Install **STP Token Updater**.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Select **STP Token Updater** and enter the provider's direct local API address.
6. Choose API key (recommended) or administrator password authentication.

Do not use a Home Assistant Ingress URL. STP must reach the provider directly over its local API.

## Automatic updates

Automatic token replacement is enabled by default. `Dry-Run` remains available as an optional troubleshooting/test mode, but its default is **off** from v0.2.1 onward.

An existing Home Assistant config entry keeps explicitly saved options during an upgrade. If Dry-Run was previously enabled manually, disable it once in the integration options to allow real writes.

STP only writes when the candidate expires later than the active token. A write is followed by delayed readback verification. A timeout never causes an immediate blind second POST.

## Home Assistant entities

The integration exposes token status and expiry information, provider reachability, renewal state, candidate information and update diagnostics, plus buttons to check the public source, apply an eligible candidate and verify the active token.

## Dashboard card

From v0.2.2 the integration includes its own compact dashboard card. No separate HACS frontend plugin and no manual Lovelace resource are required.

Open a dashboard in edit mode and choose **Add card → By card → Token Renewal**. The card is registered automatically by the integration and also appears as a suggestion when a matching STP entity is selected in Home Assistant 2026.6 or newer.

The default card configuration is zero-config for a normal single STP installation:

```yaml
type: custom:stp-token-renewal-card
```

It displays the current token status, validity, remaining lifetime, expiry, last provider check and whether a newer token candidate is available. The overview is intentionally read-only; pressing the manual apply button remains an explicit action through the STP device entities.

If entity IDs were renamed, they can be overridden explicitly:

```yaml
type: custom:stp-token-renewal-card
title: Token Renewal
entities:
  status: sensor.stp_token_updater_token_status
  valid: binary_sensor.stp_token_updater_token_valid
  remaining: sensor.stp_token_updater_token_remaining_hours
  expires: sensor.stp_token_updater_token_expires_at
  lastCheck: sensor.stp_token_updater_token_last_check
  candidate: binary_sensor.stp_token_updater_new_trial_token_available
  problem: binary_sensor.stp_token_updater_updater_problem
```

Additional dashboard examples remain available under [`examples/`](examples/), including the optional Bubble Card example.

## Releases and HACS updates

Published GitHub releases are the HACS update channel. Production integration changes must bump the version in both `manifest.json` and `const.py`; CI enforces this and the release workflow publishes the new version after successful validation.

After a HACS-managed integration update, restart Home Assistant before relying on the new Python code. HACS/Home Assistant can surface this as a restart-required repair or notification with a direct restart action.

## Validation

CI runs Python compilation, pytest, HACS validation and hassfest. Network write safety and the current test scope are summarized in [`docs/TESTING.md`](docs/TESTING.md).

## License

MIT License. See [`LICENSE`](LICENSE).
