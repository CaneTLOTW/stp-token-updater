# STP Token Updater – Requirements

`STP` means **Sponsor Token Provider**. This document defines the behaviour of the Home Assistant integration without exposing provider branding in the public product surface.

## Setup

The integration is configured through the Home Assistant UI and requires:

- provider base URL;
- authentication method: API key or administrator password;
- credential for the selected method.

The integration must validate reachability and authentication during setup. Credentials are secrets and must never be copied into logs, entities, events, Repairs or diagnostics.

## Token state

The provider's active token expiry is the primary source of truth. A locally decoded JWT `exp` is only a candidate/fallback value and is never treated as proof that the provider accepted the token.

Full candidate JWTs are held only in memory. Persistent state may contain expiry timestamps, fingerprints, retry state and sanitized errors.

## Renewal schedule

```text
T-48h  first renewal attempt
T-12h  retry if unresolved
T-6h   retry + warning event/Repair
T-1h   retry + critical event/Repair
T+0    expired
T+...  retry every 6h until verified success
```

A checkpoint is processed once. A normal five-minute provider status poll must never cause the same checkpoint to run repeatedly.

## Source polling

```text
>48 h remaining     every 6 h
48–12 h             every 3 h
<=12 h              every 1 h
expired/unresolved  at least every 6 h
```

A due renewal attempt always performs a fresh source check. Failed source checks update the source-check timestamp so a temporary source outage cannot create a five-minute request storm.

## Candidate selection

A candidate must:

- be a three-part JWT;
- have a decodable JSON payload;
- match the provider-required issuer and trial subject;
- contain a numeric future `exp`;
- have plausible timestamps;
- expire strictly later than the active token.

When multiple valid candidates are present, select the one with the latest plausible expiry. The integration does not claim local cryptographic signature validation; the upstream provider remains the authority when a token is applied.

## Write safety

Automatic writes are enabled by feature design but the pre-release build starts in `dry_run=true` for safe acceptance testing.

A real write occurs only for a strictly newer candidate. After one POST:

1. wait about 3 seconds;
2. read provider state;
3. if still inconsistent, wait about 5 more seconds;
4. read provider state again;
5. only then report success or failure.

A transport timeout is an uncertain write and must be followed by readback before another POST is considered. Definite authentication/rate-limit/provider rejections are propagated and must not be hidden as generic verification failures.

Success requires a later provider-reported expiry matching the candidate expiry within a small tolerance.

## Configuration conflicts

If the provider reports that the active sponsor token is controlled by a file/YAML source, the active token may still be valid, but STP must not claim that an API-written replacement became authoritative. Raise a configuration Repair instead.

## Notifications

The integration emits:

```text
stp_token_updater_warning
```

Escalation levels are `warning`, `critical` and `expired`. Each level is emitted at most once per active-token cycle. A verified new active token starts a new cycle and clears resolved Repairs.

## Home Assistant entities

The integration exposes sensors for lifecycle state/timestamps/errors, binary sensors for validity/reachability/update requirements, and buttons for source check, controlled apply and verification.

No entity may contain a full JWT or credential.

## Testing

Unit/component tests use mocks/fakes for network boundaries and never perform a real sponsor-token write. A real end-to-end write is reserved for an explicit acceptance test with a strictly newer candidate.

The repository must run:

- pytest with Home Assistant installed;
- HACS validation;
- hassfest validation.
