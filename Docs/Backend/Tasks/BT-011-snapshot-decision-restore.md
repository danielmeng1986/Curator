# BT-011 — Implement Snapshot Decision and Restore Behavior

## Task ID

`BT-011` — Status: `Complete`

## Title

Implement Snapshot Decision and Restore Behavior

## Related Specification(s)

- [Snapshot Specification](../Specifications/Snapshot-Specification.md), decision policy, catalog, restore, and retention sections.
- [Operation Logging](../Specifications/Operation-Logging.md), material-operation recording requirements.
- [Backend Architecture](../Backend-Architecture.md), Domain Service Layer and database infrastructure guidance.

## Goal

Implement deterministic, policy-driven snapshot creation, cataloging, restore, and retention behavior through a backend service workflow.

## Scope

- Implement specified snapshot decision thresholds and policy evaluation.
- Catalog snapshots and expose their required persistent metadata through backend boundaries.
- Implement specified restore behavior and outcome handling.
- Enforce retention cleanup according to the defined policy.
- Add focused tests for threshold decisions, successful restore, and retention cleanup.

## Out of Scope

- Changing snapshot policies, thresholds, retention rules, or restore semantics.
- Replacing the database engine or adding unrelated backup providers.
- Adding UI workflows beyond required backend service and API integration points.

## Dependencies

- `BT-005` — snapshot catalog persistence must use repository access.
- [Snapshot Specification](../Specifications/Snapshot-Specification.md) — controls snapshot decisions, restore, metadata, and retention.
- [Operation Logging](../Specifications/Operation-Logging.md) — controls required recording of material snapshot operations.

## Implementation Steps

1. Map the specified snapshot policy, thresholds, catalog fields, restore sequence, and retention rules.
2. Implement deterministic snapshot-decision and catalog service operations using repository and snapshot-storage boundaries.
3. Implement restore and retention cleanup with specified outcome and failure handling.
4. Add tests for creation-threshold decisions, restore success, and retention cleanup.

## Acceptance Criteria

- Snapshot decisions are deterministic and match the specified policy and thresholds.
- Created snapshots are cataloged with the required metadata through the normal persistence path.
- Restore follows the specified workflow and records a successful or failed outcome.
- Retention cleanup removes only snapshots eligible under the specified policy.
- Automated tests cover creation thresholds, successful restore, and retention cleanup.

## Verification

- Run focused snapshot-service tests for policy decisions and catalog behavior.
- Run isolated restore tests using disposable database and snapshot fixtures.
- Run retention tests with eligible and protected snapshot fixtures, then run applicable regression tests.

## Risks or Notes

- Snapshot storage and database restoration are infrastructure concerns coordinated by the service; do not expose engine-specific behavior to controllers.
- Use isolated fixtures for restore tests so verification cannot alter an active database.
