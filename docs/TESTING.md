# Testing and safety

The repository validates the integration with GitHub Actions on the supported Home Assistant/Python baseline.

CI covers:

- Python compilation and pytest;
- Home Assistant import/config-flow smoke tests;
- token parsing and candidate selection;
- provider authentication and API error handling;
- renewal scheduling and rate-limit handling;
- write verification, including transport uncertainty and readback;
- diagnostics redaction;
- HACS and hassfest validation.

Automated tests never perform a real sponsor-token write. Real writes are guarded in production by candidate-expiry comparison, rate-limit checks and read-after-write verification.

The integration has also been exercised in a real Home Assistant installation against a local provider for setup, both authentication paths, restart persistence, entities and diagnostics. A real token replacement is naturally only performed when a strictly newer candidate exists.
