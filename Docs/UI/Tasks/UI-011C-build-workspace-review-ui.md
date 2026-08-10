# UI-011C — Build Workspace Review UI

## Task ID

`UI-011C` — Status: `Complete`

## Title

Build Dataset-Adaptable AI Workspace Review UI

## Related Specification(s)

- UI-011A AI Collection Workspace Specification.
- UI-011B stable review state machine and read model.
- [UI Data Interaction Rules](../02_Data_Interaction_Rules.md).

## Goal

Provide a review queue and detail experience for AI Worker results using stable
review contracts plus dataset-specific field presentation adapters.

## Scope

- Queue filters, assignment where specified, detail, source/provenance, AI value versus human revision, confidence, validation, and retained drafts.
- Submit, begin review, approve, reject/return, Promotion preview/execution, and archive actions as allowed by the approved state machine.
- Batch review/edit only for fields and states explicitly approved.
- Operation/Issue/permanent-entity navigation and stale-version conflict recovery.

## Out of Scope

- Historical `workspace_album` routes or raw table editing.
- Client-side AI execution or automatic acceptance of suggestions.

## Dependencies

- UI-002, UI-003, UI-007, UI-011A/B, UI-011E, and completed Backend Workspace
  API tasks. Review consumes Backend-created Groups and Work Items rather than
  direct table or ad hoc Item creation.

## Implementation Steps

1. Define stable queue/detail components and a versioned dataset adapter interface.
2. Implement the first approved dataset adapter and state-driven actions.
3. Add client tests for field ownership, validation, concurrency, and every visible transition.

## Acceptance Criteria

- AI values, human revisions, final selections, and system evidence are visually and semantically distinct.
- UI exposes only Backend-permitted actions for the current state/role and supplies record version on mutation.
- Stale writes retain the local draft, show the conflict, and do not overwrite newer decisions.
- Reject never creates permanent data; Promotion results are unique, durable, and traceable as specified.

## Verification

- Run client contract tests and Backend Workspace workflow acceptance.
- UI-011D supplies browser-level evidence.

## Risks or Notes

- Dataset adapters must be presentation mappings, not alternate business-rule implementations.

## Completion Record

- Added Admin-only AI Workspace list/overview, review queue, review detail, and
  Dispatch Group detail routes.
- Implemented the Album-analysis presentation adapter with visually distinct
  immutable AI output, retained editable human draft, and system evidence and
  provenance panels.
- Rendered only Backend-provided review and Workspace lifecycle actions; every
  mutation sends the current record version. Failed stale mutations leave the
  in-memory human draft intact for conflict recovery.
- Added review start, approval, rejection, rework, exact-name Promotion,
  Workspace close/archive, Group release/cancel/abandon, and durable
  Operation/Issue/evidence/lineage navigation.
- Added focused Workspace Review UI contract coverage and retained the complete
  Backend AI Workspace acceptance suite as the data/state-machine gate.
