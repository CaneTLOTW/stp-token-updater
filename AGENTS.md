# Maintainer notes for coding agents

This repository is the standalone source of truth for STP Token Updater.

## Task tracking and ChatGPT/Codex handoff

- GitHub Issues in `CaneTLOTW/stp-token-updater` are the canonical operative work items for bugs, features, investigations and follow-ups that are not completed immediately.
- Do **not** mirror STP repository work into Home Assistant `todo.codex` merely for tracking. This standalone repository owns its backlog locally through GitHub Issues.
- Durable architecture, behavior contracts and implementation decisions remain versioned in this repository. An Issue is the work/handoff thread, not the sole technical documentation.
- Before creating a new Issue, search open and recently closed Issues for an existing matching work item.
- ChatGPT should prepare repository analysis, research, architecture, code, tests, documentation, frontend/mockups where relevant, and an executable runbook as far as possible before handing runtime work to Codex.
- Codex is primarily the executor for work requiring a real Home Assistant / provider runtime: installation, config-entry resolution, local API behavior, reload/restart, runtime validation and sanitized evidence collection.
- Codex may perform additional analysis/design when live runtime evidence invalidates the prepared assumptions or the task explicitly requires local investigation. Document the result in the Issue and commit durable findings.
- Use Issue comments headed `## ChatGPT → Codex Handoff`, `## Codex → ChatGPT Ergebnis`, and `## ChatGPT Review / Next Step` for iterative handoff.
- Handoffs must reference the exact branch/commit, authoritative files/runbook, remaining runtime steps, expected outputs, abort criteria, acceptance criteria and protected areas.
- Codex results should include final commit/branch, runtime PASS/FAIL, actual work executed, reports/exports, blockers and consciously remaining local changes.
- Keep Issues open until acceptance criteria and required runtime validation are complete. Do not close merely because code was committed.
- Prefer `Refs #<issue>` while work remains open. Use `Fixes/Closes #<issue>` only when the issue is genuinely complete.

## Repository and release discipline

- `main` is the release/source branch unless a task explicitly establishes another development branch.
- Published GitHub releases are the HACS update channel.
- Production integration changes must keep the version contract in `manifest.json` and `const.py` consistent.
- Preserve the safety rule that a transport timeout must never cause a blind immediate second write.
- Never commit API keys, administrator passwords, sessions, active tokens, authorization headers or private diagnostics.

## Validation

Before release-ready changes, run the repository's documented validation from `docs/TESTING.md`, including Python/tests and HACS/hassfest gates where applicable.
