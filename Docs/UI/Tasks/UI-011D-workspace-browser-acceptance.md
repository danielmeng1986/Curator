# UI-011D — Add Workspace Browser Acceptance

## Task ID

`UI-011D` — Status: `Complete`

## Title

Add AI Workspace Review Browser Acceptance

## Related Specification(s)

- UI-011A, UI-011B, and UI-011C.
- Approved Backend AI Workspace workflow acceptance tasks.

## Goal

Prove AI Worker submission, human review, decision, Promotion, and archival
outcomes through the UI without touching historical Workspace data.

## Scope

- AI result appears in queue; provenance and field ownership are rendered correctly.
- Entry from an existing Dispatch Group; human draft/revision, valid and invalid
  transitions, reject/rework, approval, Promotion, Group release, duplicate
  protection, and archive/read-only behavior.
- Stale concurrent edit and dataset-adapter compatibility scenarios.
- Durable Operation, Issue, Workspace, and permanent-entity assertions.

## Out of Scope

- Testing AI model quality or every dataset field permutation.
- Loading retired `workspace_album` fixtures as active records.

## Dependencies

- UI-003 and completed UI-011A/B/C/F plus Backend workflow evidence.

## Implementation Steps

1. Map each state transition and failure path to exact UI and durable assertions.
2. Build disposable AI Worker submission and browser review scenarios.
3. Run twice from clean fixtures and verify historical data remains inaccessible.

## Acceptance Criteria

- UI cannot transition a record outside the approved state machine or overwrite a newer version.
- Reject has no permanent-entity side effect; Promotion is idempotent and exactly traceable.
- Dispatch leaves Album Status unchanged; successful name Promotion applies the
  specified Status policy, and terminal Group release preserves history.
- Archived records are read-only and remain auditable.
- Variable dataset fields do not change the stable review-state semantics.

## Verification

- Run Workspace browser suite twice, Backend Workspace workflow-readiness, and full regression.

## Risks or Notes

- The first dataset is the approved version-1 Album-analysis adapter. Future
  datasets require their own presentation adapter fixtures without changing the
  stable review-state semantics.

## Completion Record

- Added a disposable three-Album AI Workspace browser journey with real
  Manifest-bound JPEG evidence and formal Writer Vision/Writer submissions.
- Proved queue discovery, immutable AI output, editable retained human draft,
  eight-photo provenance, valid/invalid approval, exact-name Promotion, and the
  `TEMPORARY → NAME_GENERATED` policy with one durable Promotion Operation.
- Proved rejection leaves its Album unchanged, a concurrent decision rejects a
  stale browser version while retaining the local draft, and ReworkRequested
  creates an auditable successor Work Item.
- Proved all terminal Groups release their Albums, Workspace close/archive is
  Backend-gated, archived review remains readable and action-free, and retired
  historical Workspace routes remain inaccessible.
- The full browser journey passed twice from distinct clean temporary roots;
  all Web contract/browser suites, the four-scenario Backend AI Workspace gate,
  and all 751 Backend tests also passed on 2026-08-10.
