# UI-011A — Specify AI Collection Workspace

## Task ID

`UI-011A` — Status: `Proposed`

## Title

Specify the AI Collection Workspace Product and Data Contract

## Related Specification(s)

- [AI](../../05-AI.md) and [AI Worker](../../../workers/ai_worker/README.md).
- [Workspace Workflow](../../Backend/Specifications/Workspace-Workflow.md), reusable review/promotion principles only.
- [UI Workspace Albums](../04_Workspace_Albums.md), to be superseded for active Workspace behavior.

## Goal

Define a new dataset-aware collection Workspace for AI Worker output without
reopening or coupling the UI to the archived historical `workspace_album` table.

## Scope

- Workspace/dataset identity, ownership, schema version, source provenance, AI result submission, and lifecycle boundaries.
- AI-owned, human-editable, review-only, and system-managed field categories.
- Relationship to Issues, Operations, permanent entities, and Promotion.
- Rejection/rework, retention, closure, archival, concurrency, and recovery rules.
- Required Backend APIs/read models and UI information needs.

## Out of Scope

- Choosing code/schema before the product contract is approved.
- Migrating or exposing historical `workspace_album` records.
- Building the review UI.

## Dependencies

- Product/architecture owner decisions about the first AI collection dataset and Promotion outcome.
- Review of stable lessons from BT-031 and MT-008 without inheriting their retired table contract.

## Implementation Steps

1. Document actors, dataset boundaries, end-to-end states, ownership, failure, and recovery.
2. Define versioned record/read-model and API contracts, including field provenance and concurrency.
3. Update UI modules and create separately scoped Backend schema/API implementation tasks.

## Acceptance Criteria

- The Specification unambiguously separates AI suggestions, human decisions, and system-managed evidence.
- Historical Workspace data cannot become active input through the new contract.
- Schema evolution does not require changing stable review fields or state semantics.
- Promotion/rejection/rework and partial-failure outcomes are explicit and testable.

## Verification

- Architecture, data-model, AI Worker, Backend, and UI cross-review.
- Trace each UI-011B/C/D acceptance outcome to a stated contract.

## Risks or Notes

- This is a Specification task; implementation remains blocked until its decisions are approved.

