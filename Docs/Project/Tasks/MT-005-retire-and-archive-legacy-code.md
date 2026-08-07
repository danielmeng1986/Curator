# MT-005 — Retire and Archive Legacy Code

## Task ID

`MT-005` — Status: `Completed`

## Title

Retire and Archive Legacy Code

## Related Specification(s)

- [Backend Architecture](../../Backend/Backend-Architecture.md), Current Architecture.
- [Supported Backend Surface](../../Backend/Supported-Backend-Surface.md), Retirement record.

## Goal

Move historical scripts and the retired workspace application into an explicit
`legacy/` area after active replacements have been verified.

## Scope

- Classify each `scripts/` and `workspace/` item as migrated, development tool, archive reference, or deletion candidate.
- Move retained historical code to `legacy/` with a short manifest and startup guard.
- Move active non-business utilities to `tools/dev` or their owning application.

## Out of Scope

- Deleting historical code or production data without explicit approval.
- Restoring retired routes as supported Backend entry points.

## Dependencies

- `MT-002` through `MT-004` — active replacements must be verified first.

## Implementation Steps

1. Produce a file-level inventory and identify live imports or launchers.
2. Relocate only confirmed inactive material and add a legacy manifest.
3. Remove obsolete compatibility shims only after regression evidence.

## Acceptance Criteria

- Active startup, UI, and Worker paths do not import legacy code.
- Historical code is clearly marked non-runnable and discoverable for reference.
- No deletion occurs without a separately approved cleanup action.

## Verification

- Search active applications for legacy imports.
- Run full regression and verify supported entry points.

## Risks or Notes

- Archiving is reversible; deletion is a separate decision.

## Completion Record

- Historical scripts, retired workspace application, and the compatibility
  launcher moved to `legacy/` with a classification manifest and startup guard.
- Benchmark utilities moved to `tools/dev/benchmark/`.
- The historical `Database/` runtime directory was removed by curator action;
  active database state is under ignored `var/data/`.
