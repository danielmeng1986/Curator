# DOC-004 — Convert Backend Architecture to As-Built Architecture

## Task ID

`DOC-004` — Status: `Proposed`

## Goal

Update the Backend Architecture from an early refactoring proposal into a
truthful as-built architecture while preserving approved principles and clearly
marking remaining targets.

## Scope

- Replace completed future-tense statements with current component boundaries.
- Document the active server/controller, Service, Repository, database,
  migration, filesystem, authentication, operation, and recovery responsibilities.
- Describe apps.web and external Windows AI Worker access boundaries.
- Describe current AI Workspace and Work Dispatch ownership.
- Mark remaining architectural debt and unimplemented Digital Asset Trash work
  without presenting it as current behavior.

## Out of Scope

- Refactoring Backend modules.
- Replacing detailed Specifications or Supported Backend Surface documentation.

## Inputs and Authority

- Current Backend source and test composition.
- Backend Specifications, Supported Backend Surface, and Database documentation.
- DOC-001 lifecycle rules.

## Deliverables

- Revised `Docs/Backend/Backend-Architecture.md`.
- A current component/dependency diagram.
- Explicit current-state and remaining-target sections.

## Acceptance Criteria

- No completed architecture is described merely as a likely or future candidate.
- Database ownership, REST boundary, transaction/business-rule ownership, and
  external Worker access are consistent with current Specifications.
- Historical modules are clearly separated from active architecture.
- Remaining targets link to their owning tasks rather than appearing implemented.

## Verification

- Cross-check named active modules and entry points against the repository.
- Cross-check boundaries against Backend Specifications and Supported Surface.

## Dependencies

- DOC-002.
- DOC-003.
- DBDOC-001 through DBDOC-005.

## Risks or Notes

- Preserve still-valid architectural rationale; this is an as-built update, not
  a reason to erase decision history.

