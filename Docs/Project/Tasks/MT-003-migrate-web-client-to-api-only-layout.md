# MT-003 — Migrate Web Client to an API-Only Layout

## Task ID

`MT-003` — Status: `Proposed`

## Title

Migrate Web Client to an API-Only Layout

## Related Specification(s)

- [Backend Architecture](../../Backend/Backend-Architecture.md), Controller/API Layer and API Versioning.
- [UI Plan](../../UI/Curator_Web_UI_Plan.md).

## Goal

Move the current static client into `apps/web` and make `/api/v1` its only
Backend integration boundary.

## Scope

- Relocate static assets and client tests into `apps/web`.
- Replace direct legacy `/api/*` dependencies with authenticated `/api/v1` calls.
- Add client configuration for Backend URL and device-token storage without embedding secrets in source.

## Out of Scope

- New UI features or a framework rewrite.
- Direct database access, local SQL utilities, or new Backend workflows.

## Dependencies

- `MT-002` — stable new Backend entry point and compatibility contract.
- `BT-031` — only for any UI promotion screen.

## Implementation Steps

1. Inventory current UI calls and map each to a versioned API endpoint.
2. Move static assets and remove unsupported direct-route dependencies.
3. Add focused browserless client/API contract tests.

## Acceptance Criteria

- The client has no SQLite, repository, or pre-versioned API dependency.
- Authentication failures are represented safely and do not trigger UI-side business fallbacks.
- Existing supported read/import paths work through `/api/v1`.

## Verification

- Run API contract tests and client build/lint checks where applicable.
- Exercise an isolated authenticated client/API smoke path.

## Risks or Notes

- Preserve temporary compatibility only in the Backend; do not perpetuate it in the migrated client.
