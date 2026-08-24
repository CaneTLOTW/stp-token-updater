# STP Token Updater v0.2.0 – Codex live-system handoff

Date: 2026-08-24
Repository: `CaneTLOTW/stp-token-updater`
Production domain: `stp_token_updater`

## Purpose

Bring the current v0.2.0 pre-release from repository-level implementation to a validated Home Assistant / provider integration. Work in the order below. Fix reproducible defects directly in the repository, add regression tests for every defect you fix, and finish by writing the required export report.

The live system is needed for the final acceptance layer only. Do not use the live provider as a substitute for mocks/fakes when a failure path can be tested locally.

## Non-negotiable safety rules

1. **Never commit, print, log or export:**
   - a full trial JWT;
   - API key;
   - administrator password;
   - auth cookie/session value;
   - private LAN addresses or other user-specific secrets in the public repository.
2. Automated tests must **never** perform a real sponsor-token POST.
3. Keep `dry_run=true` for all initial live-system work.
4. A real write may be performed only in the explicit final write-acceptance stage below and only if the candidate expiry is strictly later than the provider-reported active expiry.
5. A POST timeout is an uncertain write. Verify by readback. **Never immediately POST the same candidate again.**
6. Do not hammer the official token source. Normal live checks must respect the implemented cadence. Failure/rate-limit testing should use mocks/fakes/local test doubles.
7. Do not alter provider machine identity, device identity or abuse/rate-limit mechanisms.
8. Do not rewrite Git history, create a release or create a public tag during this handoff. History cleanup is a separate final task after acceptance.
9. Direct commits to `main` are acceptable for this repository, but keep commits focused and descriptive.

## Starting state expected

Before changing anything, verify and record the actual starting commit SHA.

Expected repository surface:

```text
custom_components/
└── stp_token_updater/
```

There must be **no** `custom_components/evcc_token_updater/` directory and no runtime `strings.json` in the STP integration.

Expected manifest:

```text
domain:  stp_token_updater
name:    STP Token Updater
version: 0.2.0
```

Expected CI target:

```text
Python 3.14.2
Home Assistant 2026.8.2
```

The integration includes a local brand image at:

```text
custom_components/stp_token_updater/brand/icon.png
```

## Phase 1 – repository and static validation

Do this before touching the live Home Assistant instance.

### 1.1 Clean checkout

- Pull the latest `main`.
- Record `git rev-parse HEAD`.
- Confirm the working tree is clean before your own changes.
- Inspect the repository for accidental legacy/public branding. Provider-specific identifiers are allowed only where technically required by the upstream protocol, for example:
  - official source host;
  - JWT issuer;
  - provider API paths / field names.
- Public product/UI/domain names must remain STP-based.

### 1.2 Compile and unit tests

Run at minimum:

```bash
python --version
python -m compileall -q custom_components/stp_token_updater tests
python -m pytest -q
```

Use Python 3.14.2 and Home Assistant 2026.8.2 if the local environment allows it.

If the repository test environment does not already provide dependencies, install an isolated environment rather than modifying the Home Assistant runtime Python environment.

### 1.3 HACS and hassfest

Run/verify:

- HACS integration validation;
- hassfest validation;
- repository GitHub Actions where available.

Fix all deterministic repository failures before live installation.

### 1.4 Required regression coverage

Make sure tests cover at least:

- URL normalization, including IPv6, default port, and rejection of URL credentials/path/query;
- provider state parsing with wrapped/direct state;
- `Retry-After` seconds and HTTP-date parsing;
- trial JWT issuer/subject/expiry plausibility;
- selection of the latest valid candidate when multiple JWT-like strings occur;
- T-48/T-12/T-6/T-1/expired scheduler boundaries;
- restart/missed-checkpoint behavior: do not replay every missed checkpoint in sequence;
- YAML/file-managed token conflict: never write;
- candidate same/older than active token: never write;
- POST timeout/connection failure followed by successful readback: exactly one POST;
- first readback failure followed by successful second readback: exactly one POST;
- definite authentication rejection propagates and is not converted to generic verification failure;
- no full JWT/credentials in diagnostics, entity attributes or error/event payloads.

## Phase 2 – known coordinator edge case: rate-limit expiry

This is a known item from the pre-handoff review and must be explicitly tested.

Current design persists:

```text
retry_not_before
rate_limit_scope
retry_apply_pending
```

and creates a `rate_limit` Repair.

### Required behavior

For provider state, source and write scopes:

1. while `retry_not_before` is in the future, the prohibited network action must not run repeatedly;
2. when `retry_not_before` becomes due, exactly the intended action may resume;
3. a pending write retry must refresh the public candidate source before writing;
4. when the rate limit is no longer active, stale `retry_not_before`/scope metadata must be cleared appropriately;
5. the `rate_limit` Repair must be deleted once the rate-limit condition is resolved;
6. clearing rate-limit metadata must not accidentally lose a legitimate pending apply intent before that due retry is processed;
7. if the due retry finds `no_newer_candidate`, the rate-limit Repair must not remain stuck indefinitely;
8. no five-minute retry storm is allowed.

Use fake clients/source objects and controllable timestamps. Do **not** provoke a real remote rate limit for this test.

If you fix this edge case, add focused regression tests and document the exact behavior in the export report.

## Phase 3 – install in the live Home Assistant system

Only proceed once Phase 1 is clean enough to install.

### 3.1 Installation surface

Install the repository as the custom integration `stp_token_updater` using the normal HACS/custom-repository path or a development symlink/copy suitable for the live system.

Confirm after restart:

- Home Assistant starts without integration import/setup exceptions;
- **STP Token Updater** is selectable in Settings → Devices & services;
- local brand icon is visible if supported by the running HA version;
- no duplicate legacy integration is offered.

Record the Home Assistant Core version used for the test.

### 3.2 Config Flow – API-key path first

Keep Dry-Run enabled.

Test:

1. invalid provider URL;
2. unreachable provider URL;
3. valid provider URL + invalid API key;
4. valid provider URL + valid API key;
5. adding the same normalized provider URL twice must abort as already configured;
6. verify that the config entry contains only the expected auth method + selected credential, not both credentials.

Do not put the actual URL/key in the public report. Use placeholders such as `<provider-host>` and `<redacted>`.

### 3.3 Entity/device creation

After successful setup, inventory all created entities and report their actual entity IDs.

Expected functional groups:

Sensors:

```text
token_status
token_expires_at
token_remaining_hours
token_type
trial_candidate_expires_at
trial_candidate_remaining_hours
token_next_attempt
token_last_check
token_last_source_check
token_last_update
token_last_success
token_last_error
token_update_attempts
```

Binary sensors:

```text
token_valid
new_trial_token_available
token_update_required
token_updater_problem
api_reachable
```

Buttons:

```text
check_trial_token
apply_trial_token_now
verify_active_token
```

Verify:

- one STP device groups the entities;
- German HA UI shows German translated names/states;
- English HA UI shows English translated names/states if practical to test;
- timestamp entities expose valid timestamps;
- enum `token_status` exposes only defined options;
- `token_valid` requires a future expiry **and** an authorized sponsor/name, but a valid `yamlSource=file` token is not automatically considered invalid;
- no entity contains a full token/credential.

## Phase 4 – read-only live behavior with Dry-Run enabled

### 4.1 Active provider state

Record sanitized values only:

- provider reachable yes/no;
- provider version if exposed;
- sponsor/token type/name;
- active expiry;
- remaining hours;
- `yamlSource` classification;
- updater status.

Cross-check the active expiry against the provider's own UI/API if available.

### 4.2 Public trial source

Press **Check trial token** once.

Verify:

- source fetch succeeds or fails cleanly;
- candidate expiry/fingerprint metadata appears when valid;
- full JWT is not persisted or exposed;
- `new_trial_token_available` reflects candidate expiry > active expiry;
- same/older candidate results in no write requirement;
- repeated button presses are not needed; do not hammer the source.

### 4.3 Apply button in Dry-Run

With `dry_run=true`, press **Apply trial token now** once.

Verify:

- no real provider POST occurs;
- active provider expiry remains unchanged;
- real write-attempt counter is not falsely incremented;
- state/error clearly indicates Dry-Run rather than success;
- no secret appears in HA log/event/diagnostics.

### 4.4 Verify button

Press **Verify active token** and confirm it performs read-only verification/refresh and does not write.

## Phase 5 – password/session authentication

Do this after the API-key path works.

Use Reauthentication/auth switching as appropriate.

Verify:

- valid administrator password obtains/uses the provider session as designed;
- wrong password yields HA reauthentication behavior, not a retry loop;
- protected `401` causes at most one controlled re-login and one request retry;
- switching from API key to password removes the API key from the Config Entry;
- switching back removes the password;
- neither secret appears in diagnostics/logs/export.

If a real wrong-password test risks provider lockout, use a fake/local endpoint for repeated failure-path testing and perform at most one controlled live negative test.

## Phase 6 – Reconfigure and restart behavior

### 6.1 Reconfigure

Verify provider URL reconfiguration:

- normalization remains stable;
- duplicate target URL is rejected;
- successful reconfigure reloads the entry;
- existing credential remains intact;
- Config Entry unique ID follows the normalized provider URL.

### 6.2 Restart

Restart Home Assistant with Dry-Run still enabled.

Verify:

- config entry loads automatically;
- runtime data is rebuilt cleanly;
- persisted metadata restores without storing a full candidate JWT;
- provider state is freshly read;
- current lifecycle stage is recalculated;
- missed scheduler checkpoints are not replayed one by one;
- at most the currently due action is considered;
- no retry/request storm appears in logs.

## Phase 7 – Repairs and failure-path validation

Prefer mocks/fakes/local response manipulation for destructive/error scenarios.

Validate the following Repairs/status paths:

- authentication failure;
- source unavailable;
- renewal warning;
- critical renewal state;
- expired token state;
- YAML/file configuration conflict;
- rate limit.

Confirm Repairs clear when their condition is genuinely resolved, especially `rate_limit` after Phase 2.

Check event `stp_token_updater_warning` for warning/critical/expired escalation. Payload may contain only non-secret fields, e.g.:

```yaml
level: warning
remaining_hours: 5.8
expires_at: "..."
new_token_available: true
consecutive_failures: 2
error_class: verification_failed
next_attempt_at: "..."
```

Confirm the same escalation is not emitted repeatedly during the same active-token cycle.

## Phase 8 – diagnostics/privacy audit

Download or invoke integration diagnostics and inspect HA logs.

Required result:

- no full JWT;
- no API key;
- no password;
- no cookie;
- no Authorization header;
- no private provider URL/host in the public export report;
- fingerprints may be shown only in intentionally shortened/non-reversible form where exposed publicly.

Search the repository and generated report before commit for accidental secrets.

## Phase 9 – optional single real write acceptance

**This phase is conditional. Skipping it is acceptable and must not be treated as a failure if no newer candidate exists.**

Proceed only when all of the following are true:

1. Phases 1–8 are satisfactory;
2. active provider expiry has been freshly read;
3. candidate has just been freshly fetched;
4. candidate expiry is strictly later than active expiry;
5. provider is not reporting `yamlSource=file`;
6. there is no active rate-limit/backoff;
7. user has intentionally disabled Dry-Run for this acceptance step.

### Write procedure

1. Record sanitized pre-write active expiry and candidate expiry/fingerprint.
2. Trigger **one** apply operation.
3. Observe exactly one POST attempt.
4. Allow built-in delayed readback:
   - first read around configured ~3 s delay;
   - second read after an additional ~5 s if needed.
5. Success requires provider-reported expiry to be newer than the prior expiry and to match candidate `exp` within the configured tolerance.
6. If POST times out, do not manually repeat it; inspect readback first.
7. If provider returns auth/rate-limit/definite API error, stop and document it.
8. Re-enable Dry-Run after the controlled acceptance test unless explicitly required otherwise.

If the candidate is same/older, **do not write merely to test the code**. Report `WRITE_TEST=SKIPPED_NO_NEWER_CANDIDATE`.

## Phase 10 – final code/doc cleanup

After test fixes:

- keep version at `0.2.0` unless there is a clear reason to increment;
- make README/examples match actual entity/domain behavior;
- do not restore the legacy domain;
- no `strings.json` for runtime translations;
- keep `translations/en.json` and `translations/de.json` self-contained;
- ensure tests contain no live network write path;
- leave the repository installable through HACS.

Do not perform the eventual orphan/root-history cleanup in this task.

# Required return artifact

Create the directory if it does not exist:

```text
export/
```

Then create and commit:

```text
export/CODEX_STP_LIVE_VALIDATION.md
```

This file is the hand-back to the next review session and is mandatory even if testing is blocked.

## Required report structure

Use these sections exactly or equivalently:

### 1. Executive result

One of:

```text
HANDOFF_RESULT: PASS
HANDOFF_RESULT: PASS_WITH_OPEN_ITEMS
HANDOFF_RESULT: FAIL
HANDOFF_RESULT: BLOCKED
```

Also include:

```text
START_COMMIT: <sha>
END_COMMIT: <sha>
WRITE_TEST: PASS | FAIL | SKIPPED_NO_NEWER_CANDIDATE | SKIPPED_SAFETY | NOT_REACHED
```

### 2. Environment

Sanitized only:

- Home Assistant Core version;
- Python version for repository tests;
- HACS version if relevant;
- installation method;
- provider endpoint shown only as `<provider-host>:<port>` or similarly redacted.

### 3. Changes made

For every code change made during this handoff:

- file(s);
- defect/reason;
- solution;
- regression test added;
- commit SHA.

### 4. Static/CI test matrix

Table with:

```text
Test / command | Result | Notes
```

Include compile, pytest, HACS, hassfest and any relevant Actions result.

### 5. Live Config Flow matrix

Include API-key, password, invalid auth, unreachable URL, duplicate URL, reconfigure and reauth results.

Never include secrets.

### 6. Entity inventory

List actual entity IDs and key sanitized states after setup.

### 7. Scheduler / restart / rate-limit results

Explicitly state:

- checkpoint behavior;
- restart behavior;
- no-loop evidence;
- Phase 2 rate-limit expiry result;
- whether the stale-Repair edge case required a fix.

### 8. Repairs/events

For each relevant Repair/event:

- trigger method;
- expected result;
- actual result;
- cleanup result.

### 9. Privacy/security audit

Explicit checklist confirming absence of JWT/API key/password/cookie/Authorization header from logs, diagnostics, entities, event payloads and committed files.

### 10. Optional real-write acceptance

If run, include only:

- active expiry before;
- candidate expiry;
- shortened fingerprint;
- POST count;
- first/second readback result;
- active expiry after;
- final provider status;
- Dry-Run restored yes/no.

Never include the full JWT.

If skipped, state exactly why.

### 11. Open items / blockers

Be precise. Separate:

- code defect;
- environment limitation;
- safety-based skipped test;
- optional future enhancement.

### 12. Recommended next action

State what the next reviewer should do next, not a generic summary.

## Final action for Codex

1. Commit/push all justified code/test fixes.
2. Commit/push `export/CODEX_STP_LIVE_VALIDATION.md`.
3. Leave the repository working tree clean.
4. In your chat response to the user, return only a short summary containing:
   - `HANDOFF_RESULT`;
   - final commit SHA;
   - whether the real write test ran;
   - path `export/CODEX_STP_LIVE_VALIDATION.md`;
   - any blocking issue that requires human action.

The detailed evidence belongs in the export file, not in a long chat response.
