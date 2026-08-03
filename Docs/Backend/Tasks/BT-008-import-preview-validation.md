# BT-008 — Implement Import Preview and Validation

## Task ID

`BT-008` — Status: `Ready`

## Title

Implement Import Preview and Validation

## Related Specification(s)

- [Import Workflow](../Specifications/Import-Workflow.md), preview, validation, duplicate, and collision sections.
- [Canonical Path Rules](../Specifications/Canonical-Path-Rules.md), normalization and collision rules.
- [API Contract](../Specifications/API-Contract.md), validation-error response contract.

## Goal

Implement deterministic import preview and pre-write validation that reports structured errors for duplicate or colliding imports without changing persistent state.

## Scope

- Generate deterministic import previews from the specified import inputs.
- Normalize candidate paths before duplicate and collision checks.
- Detect specified duplicate paths and blocked filesystem or persistence collisions.
- Return structured validation outcomes without performing database or filesystem writes.
- Add focused tests for valid previews, duplicates, and collisions.

## Out of Scope

- Executing filesystem copy or move operations, database writes, compensation, or final import recording.
- Changing import naming, path, duplicate, or collision rules defined by the specifications.
- Adding UI behavior beyond the existing API contract.

## Dependencies

- `BT-003` — structured validation outcomes use the shared API error contract.
- `BT-005` — persistence checks must use repository access.
- [Canonical Path Rules](../Specifications/Canonical-Path-Rules.md) — controls path normalization and collision decisions.

## Implementation Steps

1. Define the preview input and deterministic output using the Import Workflow specification.
2. Apply canonical path normalization before all comparison and collision checks.
3. Implement repository and filesystem collision checks without mutation.
4. Return structured validation results and add tests for valid, duplicate, and blocked-collision cases.

## Acceptance Criteria

- Equivalent import input produces the same preview and validation result.
- Duplicate and collision checks use canonicalized paths before any write action.
- Invalid imports return specified structured validation errors without mutating database or filesystem state.
- Valid import previews identify any required follow-on execution information without performing execution.
- Automated tests cover valid imports, duplicate paths, and blocked collision cases.

## Verification

- Run focused import-service tests for deterministic preview and validation outcomes.
- Run canonical-path tests for representative normalization and collision cases.
- Confirm database and filesystem fixtures remain unchanged after validation-only test runs.

## Risks or Notes

- Keep validation and execution separate so a successful preview cannot itself authorize or perform a write.
- Treat unresolved path or collision semantics as a Specification decision, not an implementation default.
