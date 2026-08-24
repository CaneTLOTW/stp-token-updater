# STP Token Updater – task audit

Stand: 2026-08-24
Version: v0.2.0 pre-release
Domain: `stp_token_updater`

The authoritative live-system validation sequence is `docs/CODEX_LIVE_HANDOFF.md`.

## Implemented in the current repository

- exactly one Home Assistant custom integration under `custom_components/stp_token_updater/`;
- HACS metadata and UI Config Flow;
- API-key or administrator-password/session authentication;
- reconfigure and reauthentication flows;
- `ConfigEntry.runtime_data` runtime model;
- `OptionsFlowWithReload` options handling;
- local provider state polling through a `DataUpdateCoordinator`;
- sponsor/trial expiry parsing from provider state;
- public trial-JWT parser with issuer/subject/timestamp plausibility and SHA-256 fingerprint metadata;
- no persistence of full candidate JWTs;
- scheduler `T-48h / T-12h / T-6h / T-1h / expired +6h`;
- separate provider/source/write cadence;
- no write for same/older candidate;
- Dry-Run as safe default;
- single-POST + delayed read-after-write verification;
- uncertain POST timeout handled by readback instead of blind retry;
- YAML/file-managed token conflict detection without falsely making an otherwise valid token invalid;
- translated sensors, binary sensors, buttons, events and Repairs;
- German and English self-contained translations;
- diagnostics without credentials/full JWT;
- local HA brand icon plus repository SVG branding;
- dashboard and push-notification examples;
- pytest, HACS and hassfest workflows;
- pytest workflow targets Python 3.14.2 / Home Assistant 2026.8.2.

## Important corrections already made

- first implementation Config Flow password/import issues;
- incompatible positional `SensorEntityDescription` construction;
- wrong Repairs issue-registry import;
- repeated execution of the same renewal checkpoint on every five-minute status poll;
- source failure without advancing source-check timestamp;
- definite auth/rate-limit write errors being hidden as generic verification failures;
- file-managed token being considered invalid solely due to `yamlSource=file`;
- public product/domain migration from legacy naming to `stp_token_updater`;
- old integration directory removed completely;
- runtime `strings.json` removed; translations are under `translations/*.json`;
- entity descriptions now use translation keys;
- token-valid binary sensor now requires a future expiry and an authorized sponsor/name;
- local HA brand icon added;
- regression tests expanded for scheduler boundaries, JWT parsing, URL normalization and single-write verification safety.

## Known item that still requires executable testing

Rate-limit expiry/cleanup needs an explicit regression test with controllable time and fake provider/source objects. In particular verify that after `retry_not_before` is reached:

- exactly the intended source/write action resumes;
- a pending apply intent is not lost prematurely;
- stale `retry_not_before` / `rate_limit_scope` metadata is cleared appropriately;
- the `rate_limit` Repair is removed when the condition is resolved;
- `no_newer_candidate` after a due retry does not leave the Repair stuck;
- no five-minute retry storm occurs.

Codex must fix this if reproducible and add regression coverage. Do not provoke a real remote rate limit.

## Still requiring live acceptance

1. repository compile/pytest/HACS/hassfest results in an executable development environment;
2. installation as a real Config Entry;
3. local brand image and translated entity states in the HA frontend;
4. API-key authentication live;
5. password/session authentication live;
6. reconfigure and reauthentication live;
7. restart behavior inside lifecycle windows;
8. source failure/recovery and Repairs cleanup;
9. diagnostics/privacy audit;
10. at most one controlled real write if and only if a strictly newer candidate exists.

A missing newer candidate is a valid reason to skip item 10.

## Return path

Codex must write the hand-back report to:

```text
export/CODEX_STP_LIVE_VALIDATION.md
```

See `docs/CODEX_LIVE_HANDOFF.md` for required structure and safety constraints.
