# BT-026 — Permit Canonical-Source Imports in Preview

## Task ID

`BT-026` — Status: `Complete`

## Title

Permit Canonical-Source Imports in Preview

## Related Specification(s)

- [Import Workflow](../Specifications/Import-Workflow.md), Album preview and confirmation and Import Action and filesystem behavior sections.
- [Canonical Path Rules](../Specifications/Canonical-Path-Rules.md), Canonicalization and comparison and Collision handling sections.

## Goal

Allow a valid source Album that is already at its computed canonical destination to pass import preview and proceed as a metadata-only import, while retaining all collision protections for other existing directories.

## Scope

- Detect when the supplied source path and computed canonical destination identify the same managed directory using the Canonical Path Rules.
- Treat that single condition as eligible for import preview and expose the effective `DATABASE_ONLY` filesystem implication.
- Preserve rejection of an existing destination that is not the supplied canonical source, database path collisions, duplicate production entities, and all other validation errors.
- Add focused service and BT-019 workflow acceptance coverage.

## Out of Scope

- Accepting arbitrary existing directories, semantic duplicate reconciliation, or changing canonical-path collision policy.
- Filesystem moves, copies, repairs, or UI presentation changes beyond the existing preview result.
- Operation lifecycle recording, which belongs to `BT-027`.

## Dependencies

- `BT-008` and `BT-014` — provide import preview validation and canonical path comparison behavior.
- `BT-019` — provides the acceptance scenario currently exposing this readiness gap.

## Implementation Steps

1. Define the service-level equivalence check between `source_path` and the computed destination without weakening canonical comparison or collision detection.
2. Update preview validation and result metadata so an already-canonical source is importable and describes its metadata-only action.
3. Confirm execution retains the directory unchanged and selects `DATABASE_ONLY`.
4. Add focused positive and negative tests, then make the relevant BT-019 scenario pass.

## Acceptance Criteria

- Preview accepts an otherwise valid source that is already at its computed canonical destination.
- The resulting execution uses `DATABASE_ONLY` and does not copy, move, overwrite, or recreate the source directory.
- An existing destination different from the supplied source remains a `PATH_EXISTS` conflict.
- Existing database and canonical-path collision validation remains unchanged for all non-exception cases.

## Verification

- Run focused import preview/execution tests for the canonical-source and unrelated-existing-destination cases.
- Run `python3 tools/web_ui/tests/run_regression.py workflow` and confirm the BT-019 canonical-source scenario passes.
- Run the import and canonical-path regression groups, followed by the complete suite.

## Risks or Notes

- The exception is based on the exact supplied source and computed canonical destination only; it must not become a general exemption for occupied destination paths.
