# MT-002 — Relocate Backend into the Modular Monolith

## Task ID

`MT-002` — Status: `Complete`

## Title

Relocate Backend into the Modular Monolith

## Related Specification(s)

- [Backend Architecture](../../Backend/Backend-Architecture.md), Proposed Backend Architecture and Request Flow.
- [Supported Backend Surface](../../Backend/Supported-Backend-Surface.md), Active entry point.

## Goal

Move the runnable Backend from `tools/web_ui` into `apps/backend` while
preserving the tested `/api/v1` contract and a temporary compatibility launcher.

## Scope

- Place API adapters, services, repositories, infrastructure, and bootstrap code under `apps/backend`.
- Introduce one documented backend startup command and retain a thin old-path launcher during migration.
- Update imports, test discovery, and runtime path resolution without changing business behavior.

## Out of Scope

- Redesigning API routes, database schema, or workflow behavior.
- Migrating static UI assets or AI code.

## Dependencies

- `MT-001` — runtime paths and configuration conventions exist first.

## Implementation Steps

1. Move modules by layer, maintaining compatibility imports only where required. — Complete
2. Move regression and workflow tests with the Backend test boundary. — Complete
3. Make the new entry point authoritative; mark the old launcher as transitional. — Complete

## Acceptance Criteria

- The new Backend entry point passes `workflow-readiness` twice and full regression once.
- `/api/v1` behavior and durable operation data remain compatible.
- No client code opens SQLite or bypasses Services.

## Verification

- Run API, workflow-readiness twice, and full regression through the new entry point. — Complete
- Confirm the compatibility launcher delegates rather than duplicates application logic. — Complete

## Risks or Notes

- This is a physical relocation, not permission to refactor every module simultaneously.
