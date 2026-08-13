# UI Workflow Specification Audit — 2026-08-13

> Documentation status: Historical
> Owner: UI
> Last verified: 2026-08-13

Snapshot date: 2026-08-13. Remediation status: UI-023–028 completed after this
audit. Current source: [Workflow Readiness Matrix](../Workflow-Readiness-Matrix.md).

This file preserves the evidence and findings observed on the snapshot date.
Statements such as **Failing** and **Not Implemented** below are historical and
must not be read as the current product classification.

## Purpose

This audit evaluates shipped `apps.web` workflows against the controlling
[Curator Web UI Specification](../Specification.md). It does not treat an existing
button or passing uninterrupted happy path as sufficient evidence.

## Method and evidence

1. Ran the 11-suite UI readiness gate against disposable Backend and browser resources.
2. Ran Work Dispatch and AI Review separately after the gate stopped at its first failure.
3. Inspected browser tests for modal-close, navigation, refresh, browser restart,
   Backend restart, delayed action, retry, cancellation, and upgrade coverage.
4. Inspected UI state ownership, modal dismissal, routing, and browser storage.

### Test result

| Result | Suites |
| --- | --- |
| Passed | Foundation contracts, authenticated smoke, Admin workflows, device enrollment, permanent entities, Import, Operation history, Repair/Quarantine, Work Dispatch, AI Review |
| Failed | Permission disclosure: the assertion rejects the metadata key `registration_proof` in Admin state even though this field contains managed proof state rather than plaintext proof material. The test no longer distinguishes a forbidden plaintext value from a permitted state descriptor. |

The ten passing suites remain valuable functional evidence. They do not satisfy
the new interruption matrix by themselves.

## Workflow findings

| Workflow | Existing strength | Specification gap | Classification | Task |
| --- | --- | --- | --- | --- |
| Authentication and enrollment | Stable top-bar resume entry, refresh compatibility, role isolation, credential redaction | Existing coverage is the reference implementation; Backend-restart/manual Safari parity remains release evidence rather than a current implementation defect | Ready | UI-022 / UI-021 |
| Permanent entities and relationships | Complete CRUD, validation, inline relationships, Reader denial, durable verification | Unsaved form and relationship edits are lost on route change or refresh without warning; list search/pagination is held in memory rather than reliably represented in the URL | Not Implemented | UI-024 |
| Import | Strong preview identity, replay/stale rejection, COPY/MOVE/database-only outcomes, Operation link | Compose batch, reviewed selection, preview identity, and result view are in page memory and reset whenever the route renders or the browser refreshes; no stable resume/restart explanation | Not Implemented | UI-025 |
| Operation history | Stable read-only routes, role-sensitive disclosure, evidence links | No material local draft or delayed action; current route-based recovery is adequate | Ready | Existing UI-007/UI-015 |
| Issue and Repair decisions | Stable detail routes, stale conflict retains entered values, role/policy rejection evidence | Shared reviewed-action dialogs can still be dismissed implicitly; explicit abandonment behavior is not uniform | Not Implemented | UI-026 |
| Quarantine and item Restore | Preview-bound execution, cancellation and filesystem truth are verified | Preview Token exists only in module memory; Escape/overlay dismissal silently abandons it and the UI does not identify this as cancellation or offer resume/re-preview guidance | Not Implemented | UI-026 |
| Backup cleanup and database Restore | Verified targets, typed Restore confirmation, protective Snapshot and session invalidation | Reviewed previews are transient dismissible modals with no common explicit-abandonment contract; refresh/restart recovery is not verified | Not Implemented | UI-026 |
| Work Dispatch | Stable Active/History views, conflict safety, release/cancel evidence | Album/configuration selection and reviewed preview are in memory; implicit modal dismissal and refresh lose progress without explanation | Not Implemented | UI-026 |
| AI Review and Promotion | Durable review states, validation retention, stale-conflict retention, Promotion evidence | Human evaluation/name/rating/reason draft is module memory only and is lost on refresh or browser restart; Promotion preview shares the transient modal problem | Not Implemented | UI-027 and UI-026 |
| Permission/disclosure gate | Role-separated payload and rendered-output checks | Secret-field assertion conflates a field name describing managed proof state with plaintext secret disclosure, stopping the readiness gate before later suites | Failing | UI-023 |
| Cross-workflow interruption evidence | Existing tests cover selected cancellation, stale/replay, and a few refresh cases | There is no required interruption manifest proving the applicable close/navigation/refresh/restart/delayed-action/cache paths for each matrix row | Not Implemented | UI-028 |

## Cross-cutting conclusions

- Authentication is currently the only workflow designed and tested as an
  explicitly resumable multi-session journey.
- `localStorage` is intentionally used only for connection and enrollment.
  Other complex drafts have no browser persistence owner or schema.
- The shared modal is dismissible by Escape and overlay click unless a caller
  opts out. Several reviewed high-risk previews use the dismissible default.
- Current entity filter state and many wizard states are JavaScript singleton
  state, not URL or validated browser state.
- Existing zero-write Preview and replay protection make accidental dismissal
  safe for durable data, but safe data is not the same as a clear and friendly
  recovery experience.

## Recommended execution order

1. UI-023 restores a truthful, non-blocking readiness gate.
2. UI-024 and UI-025 address common daily Writer workflows.
3. UI-026 establishes one reviewed-action lifecycle for all material previews.
4. UI-027 protects long-form AI review work using the shared draft rules.
5. UI-028 adds the interruption matrix to the final gate and reclassifies rows
   only after their evidence passes.

## Resolution record

- UI-023 corrected the permission-disclosure gate.
- UI-024 and UI-025 added entity and Import continuity.
- UI-026 standardized the reviewed-action lifecycle.
- UI-027 added versioned AI Review drafts and stale reconciliation.
- UI-028 made interruption evidence mandatory in the readiness manifest.
- The upgraded gate subsequently passed; UI-029 later added a focused no-model
  Dispatch-to-Promotion drill. Current status belongs to the living matrix.
