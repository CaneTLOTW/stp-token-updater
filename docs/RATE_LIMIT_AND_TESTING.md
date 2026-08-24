# STP – Live-write and rate-limit safety

The integration has three distinct network activities:

1. read the public trial-token source;
2. read local provider state;
3. apply a sponsor token, which may trigger upstream authorization/abuse checks.

No authoritative numerical quota for sponsor-token validation is assumed by the integration. Do not encode an invented requests-per-hour/day limit.

## Mandatory automated-test policy

Automated tests must not perform real sponsor-token writes. Mock/fake:

- provider client;
- public token source;
- delayed readback;
- write responses;
- time/scheduler state.

This allows deterministic testing of `T-48h/T-12h/T-6h/T-1h/expired` without external authorization traffic.

## Live acceptance test

A live write is allowed only as an explicit acceptance test:

1. read current provider state;
2. fetch/decode the public candidate;
3. verify candidate expiry is strictly later than active expiry;
4. send one deliberate write;
5. perform delayed readback;
6. do not blind-retry a transport timeout;
7. stop on authentication, rate-limit, block/abuse or other definite provider rejection.

## Production safeguards

- source polling never implies a write;
- the same renewal checkpoint runs once, not every status poll;
- only a strictly newer candidate can be written;
- after expiry retries are controlled at six-hour intervals;
- `Retry-After` should be honored when supplied;
- abuse/block responses require user attention rather than identity/token cycling attempts.
