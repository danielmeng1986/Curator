# UI-016 — Establish UI Workflow Readiness Gate

## Task ID

`UI-016` — Status: `Complete`

## Title

Establish the Complete UI Workflow Readiness Gate

## Related Specification(s)

- UI-001 Workflow Coverage Matrix.
- [Backend Testing Strategy](../../Backend/Testing-Strategy.md).
- [Backend Workflow Readiness Matrix](../../Backend/Workflow-Readiness-Matrix.md).

## Goal

Compose the UI smoke, entity, Import, Repair/Quarantine, permission, Admin, and
future Workspace suites into one deterministic readiness command and matrix.

## Scope

- Named suite entry points, dependency/startup checks, isolation, timeouts, failure artifacts, and summary.
- Readiness matrix classification and links to UI/Backend evidence.
- Required two consecutive clean runs followed by Backend workflow-readiness and full regression.
- Explicit handling for not-yet-implemented or specification-blocked Workspace rows without silently skipping required Ready scenarios.

## Out of Scope

- Performance, visual-regression, broad accessibility, deployment, or production-data certification unless separately tasked.
- Replacing lower-level Backend workflow gates.

## Dependencies

- UI-001 through UI-015 for all rows classified Ready; blocked rows remain explicitly classified.

## Implementation Steps

1. Define suite manifest, readiness classifications, execution order, artifact/redaction policy, and failure semantics.
2. Add one repository-root command and CI/local documentation.
3. Run the gate twice, Backend workflow-readiness twice, then full Backend regression; publish evidence.

## Acceptance Criteria

- A required scenario failure fails the gate; no required test is converted to a skip.
- Every suite uses disposable resources and leaves no Token, process, file, or database state behind.
- Summary identifies scenario, UI task, controlling Specification, Backend evidence, and sanitized artifact location.
- The matrix distinguishes `Ready`, `Failing`, `Not Implemented`, and `Blocked by Specification` truthfully.

## Verification

- Execute the complete command twice from clean fixtures.
- Execute `python3 -m apps.backend.tests.run_regression workflow-readiness` twice and `python3 -m apps.backend.tests.run_regression all` once afterward.

## Risks or Notes

- Gate duration should be controlled through fixture reuse only where isolation remains provable; safety scenarios must not share mutable state.

## Completion Record

- Added `npm run test:ui-readiness` and an explicit ten-suite manifest. Every
  suite is mandatory and names its UI task, controlling Specification, Backend
  evidence, and timeout.
- The runner performs startup checks, uses disposable resources, stops on the
  first failure, retains a sanitized failure artifact, and removes the gate
  artifact root after complete success.
- Two consecutive final UI gate runs passed with all ten suites and no skips.
- `workflow-readiness` passed twice (34 tests per run), followed by the full
  Backend regression (751 tests).
- The gate exposed three immediate UI-test reads; their acceptance scripts now
  wait for completed authentication or visible role controls before asserting.
