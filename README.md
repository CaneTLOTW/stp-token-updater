# STP Token Updater

![STP Token Updater](assets/stp-token-updater.svg)

Home Assistant custom integration / HACS project for monitoring and managing a sponsor/trial-token lifecycle through a local provider API.

[![Open your Home Assistant instance and add this repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=CaneTLOTW&repository=stp-token-updater&category=integration)

**STP = Sponsor Token Provider.** Provider-specific protocol identifiers are kept only where the upstream protocol requires them.

## Status

**v0.2.0 – pre-release validation**

The production Home Assistant domain is now `stp_token_updater`. The repository contains exactly one custom integration under `custom_components/stp_token_updater/`.

Token writes are protected by a `dry_run` option which defaults to enabled. Automated tests must never perform a real sponsor-token write.

## Installation via HACS

### One-click installation

Select the HACS badge above in Home Assistant. It opens the **Add custom
repository** dialog with this repository and the **Integration** category
already filled in. Confirm it, install **STP Token Updater** through HACS and
restart Home Assistant.

### Manual installation

1. Open **HACS** → **Integrations**.
2. Open the menu `⋮` → **Custom repositories**.
3. Add `https://github.com/CaneTLOTW/stp-token-updater` with category
   **Integration**.
4. Search for **STP Token Updater** in HACS and select **Download**.
5. Restart Home Assistant completely.
6. Open **Settings** → **Devices & services** → **Add integration** and select
   **STP Token Updater**.
7. Enter the provider's direct local API URL and choose **API key**
   (recommended) or **administrator password**.
8. Leave **Dry-Run** enabled for the initial verification.

For acceptance testing, keep **Dry-Run enabled** until the read-only paths, entities and authentication have been verified.

> Do not use a Home Assistant Ingress URL. The integration must reach the
> provider directly over its local API address.

## Setup

The integration expects the provider's direct local API base URL. Authentication can use either:

- API key (recommended), or
- administrator password/session.

The provider URL is normalized and validated. User-info URLs, paths, query strings and fragments are rejected. The default direct provider API port is added when no explicit port is supplied.

## Safety model

Default settings:

```text
Dry-Run = on
Automatic updates = on
```

A real candidate is only written when it expires strictly later than the currently active token. One POST is followed by delayed read-after-write verification. A transport timeout is treated as an uncertain write and causes readback, never an immediate blind second POST.

Credentials, cookies and full candidate JWTs must never appear in entity states, events, Repairs, diagnostics or logs. Candidate JWTs are kept in memory only; persistence contains sanitized metadata such as expiry and fingerprints.

## Renewal schedule

```text
T-48h  first renewal attempt
T-12h  retry if unresolved
T-6h   retry + warning event/Repair
T-1h   retry + critical event/Repair
T+0    expired
T+...  retry every 6 hours until verified success
```

Provider state polling, public source polling and write scheduling are separate. `429`/`Retry-After` handling prevents normal status polling from turning into a retry storm.

## Home Assistant implementation

- Config Flow only; no YAML setup.
- `ConfigEntry.runtime_data` for runtime objects.
- `DataUpdateCoordinator` for shared polling/state.
- Reconfigure and reauthentication flows.
- `OptionsFlowWithReload` for runtime options.
- translated sensor, binary sensor, button and Repair names in German and English.
- local Home Assistant brand image under `custom_components/stp_token_updater/brand/icon.png`.
- diagnostics with explicit secret redaction.

## Repository structure

- `custom_components/stp_token_updater/` – production integration.
- `tests/` – pure-logic, safety and Home Assistant smoke tests.
- `docs/REQUIREMENTS.md` – authoritative lifecycle requirements.
- `docs/RATE_LIMIT_AND_TESTING.md` – network/test safety rules.
- `docs/CODEX_LIVE_HANDOFF.md` – ordered live-system acceptance handoff.
- `examples/` – native dashboard and notification examples.
- `assets/` – repository branding.

## Validation

CI targets Home Assistant 2026.8.2 on Python 3.14.2 and includes:

- Python compilation;
- pytest;
- HACS validation;
- hassfest validation.

A real provider write is **not** part of automated CI. The final live write acceptance test is explicit and optional, and may be performed only when the candidate is strictly newer than the active token.

## License

MIT License. See [`LICENSE`](LICENSE).
