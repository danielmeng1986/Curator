# BT-005 — Centralize Repository Access

## Task ID

`BT-005` — Status: `Complete`

## Title

Centralize Repository Access

## Related Specification(s)

- [Repository Specification](../Specifications/Repository-Specification.md), repository contracts and persistence boundaries.
- [Backend Architecture](../Backend-Architecture.md), Repository Layer and Database Layer sections.

## Goal

Make repositories the exclusive application boundary for database access, so handlers and services use domain-oriented repository operations rather than SQL or database objects.

## Scope

- Identify direct persistence access in active handlers and service entry points.
- Introduce or consolidate repository methods required by current Backend Specifications.
- Migrate application callers to repository methods and preserve existing persistence behavior.
- Add or update focused repository-boundary tests.

## Out of Scope

- Changing database schema, storage engine, or specified behavior.
- Redesigning read models beyond repository methods needed for existing callers.
- Refactoring HTTP transport or workflow behavior beyond removing direct persistence access.

## Dependencies

- `BT-004` — application service boundaries identify the callers that should consume repositories.
- [Repository Specification](../Specifications/Repository-Specification.md) — defines required persistence contracts and result conventions.

## Implementation Steps

1. Inventory SQL, database connections, transaction control, and raw-row access outside repository modules.
2. Define or consolidate focused repository methods for the required reads and writes.
3. Move low-level persistence implementation into repositories and update callers to use their contracts.
4. Add or update repository and regression tests for migrated operations.

## Acceptance Criteria

- Active handlers and service entry points contain no SQL, database connections, or raw database-row handling.
- Application code accesses persisted records only through repository methods.
- Repository methods cover the current specified read and write operations used by migrated callers.
- Existing persistence behavior and transaction outcomes remain stable.

## Verification

- Run focused repository tests for each migrated read and write operation.
- Run service and API regression tests to confirm callers preserve existing behavior.
- Inspect active handlers and services to confirm direct database access has been removed.

## Risks or Notes

- Keep repository methods purpose-specific; do not introduce a generic query executor that leaks persistence details back into application code.
- Coordinate transaction ownership with the database layer while preserving current atomicity requirements.
