# BT-014 — Implement Canonical Path Normalization

## Task ID

`BT-014` — Status: `Complete`

## Title

Implement Canonical Path Normalization

## Related Specification(s)

- [Canonical Path Rules](../Specifications/Canonical-Path-Rules.md), normalization, comparison, collision, and final-path sections.
- [Import Workflow](../Specifications/Import-Workflow.md), path validation and execution sections.
- [Repair Workflow](../Specifications/Repair-Workflow.md), repair path handling sections.

## Goal

Provide one shared canonical path service for Backend path normalization, comparison, collision detection, and final-path derivation.

## Scope

- Implement the specified canonical path normalization, comparison, collision, and final-path rules in a shared service.
- Replace ad hoc path handling in import, repair, and repository logic with the shared service.
- Ensure path storage and validation use canonical values where specified.
- Add unit tests for normalization edge cases and collision behavior.

## Out of Scope

- Changing specified path policy, archive layout, import naming rules, or filesystem execution behavior.
- Adding new import, repair, or repository workflows beyond replacing path-handling logic.
- Performing data migration beyond any normalization explicitly required by the specification.

## Dependencies

- `BT-005` — repository access provides the persistence boundary for canonical path storage and collision checks.
- [Canonical Path Rules](../Specifications/Canonical-Path-Rules.md) — controls all normalization and collision behavior.
- `BT-008` — import validation consumes canonical comparison and collision decisions.

## Implementation Steps

1. Identify ad hoc path normalization, comparison, collision, and derivation logic in active Backend code.
2. Implement the shared canonical path service from the Canonical Path Rules specification.
3. Migrate import, repair, and repository callers to the shared service.
4. Add unit and integration tests for normalization edge cases and collisions across migrated callers.

## Acceptance Criteria

- All in-scope Backend path comparisons, storage, validation, and final-path derivation use the shared service.
- Canonical values and collision results match the Canonical Path Rules specification.
- Import, repair, and repository logic no longer contain divergent ad hoc path rules.
- Automated tests cover specified normalization edge cases and collision behavior.

## Verification

- Run focused path-service unit tests for canonicalization, equivalence, final paths, and collisions.
- Run import, repair, and repository tests that exercise migrated path handling.
- Inspect in-scope code paths to confirm duplicate normalization logic has been removed.

## Risks or Notes

- Preserve the distinction between a canonical logical path and a filesystem path where the specification requires it.
- Any ambiguous normalization rule must be resolved in the Canonical Path Rules specification before implementation.
