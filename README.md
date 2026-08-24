# STP Token Updater

![STP Token Updater](assets/stp-token-updater.svg)

Home Assistant custom integration / HACS project for monitoring and managing a sponsor/trial-token lifecycle through a local provider API.

**STP = Sponsor Token Provider.** Provider-specific protocol identifiers remain internal only where technically required.

## Status

**v0.1.0 – prototype under validation**

The integration is implemented as an independent HACS custom integration. Token writes are protected by a `dry_run` option which defaults to enabled. Automated tests must never perform a real sponsor-token write.

## Installation via HACS

1. HACS → Integrations → menu `⋮` → Custom repositories.
2. Add `https://github.com/CaneTLOTW/stp-token-updater` as type **Integration**.
3. Install **STP Token Updater** and restart Home Assistant.
4. Settings → Devices & services → Add integration → **STP Token Updater**.

## Setup

The integration expects the provider's direct local API base URL. Authentication can use either:

- API key (recommended), or
- administrator password/session.

The provider-specific URL, API paths, JWT claims and key formats are implementation details and are intentionally not renamed when doing so would break compatibility.

## Safety

Default settings:

```text
Dry-Run = on
Automatic updates = on
```

A real candidate is only written when it expires strictly later than the currently active token. A write is followed by delayed read-after-write verification; a timeout does not cause an immediate blind second POST.

## Renewal schedule

```text
T-48h  first renewal attempt
T-12h  retry if unresolved
T-6h   retry + warning event/Repair
T-1h   retry + critical event/Repair
T+0    expired
T+...  retry every 6 hours until verified success
```

## Repository structure

- `custom_components/evcc_token_updater/` – production Home Assistant integration. The legacy/internal domain is retained for compatibility.
- `tests/` – unit and Home Assistant smoke tests.
- `docs/` – requirements, review and test-safety notes.
- `examples/` – dashboard and push-notification examples.
- `assets/` – STP branding.

## Important compatibility note

The public product name is **STP Token Updater**. Some internal identifiers still contain the original provider name because they are part of Home Assistant persistence/identity or the upstream protocol. These must not be changed blindly without a migration strategy.

## License

MIT License. See [`LICENSE`](LICENSE).
