# MT-001 — Establish Project Runtime Boundaries

## Task ID

`MT-001` — Status: `Proposed`

## Title

Establish Project Runtime Boundaries

## Related Specification(s)

- [Backend Architecture](../../Backend/Backend-Architecture.md), Configuration Layer and Database Layer.
- [Testing Strategy](../../Backend/Testing-Strategy.md), Sandbox Environment.

## Goal

Create the target top-level layout and a clear distinction between versioned
source/configuration and untracked runtime data before moving application code.

## Scope

- Add `apps/`, `workers/`, `tools/dev/`, `legacy/`, and `var/` directory conventions.
- Move or replace runtime paths with `var/data`, `var/backups`, `var/logs`, and `var/outputs`.
- Add Git ignore rules and committed configuration examples; define local override and secret handling.
- Establish the versioned database migration/schema source location.

## Out of Scope

- Moving Backend, UI, or AI Worker code.
- Modifying production data or committing database images, tokens, model files, or outputs.

## Dependencies

- `None`.

## Implementation Steps

1. Inventory current runtime files and validate each destination before any move.
2. Create target directories, ignore rules, config examples, and migration/schema convention.
3. Update startup documentation to explain local runtime configuration.

## Acceptance Criteria

- Runtime data cannot be accidentally added to Git.
- A fresh clone can discover required configuration from committed examples.
- Database schema evolution is versioned independently of a live database file.

## Verification

- Inspect Git status after generating representative runtime files.
- Run existing Backend regression suites against disposable paths.

## Risks or Notes

- Copy or move live database data only with an explicit backup and rollback plan.
