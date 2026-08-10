# BT-053 — Add AI Workspace Workflow Acceptance and Disposable Worker Fixtures

## Task ID

`BT-053` — Status: `Proposed`

## Title

Prove the Album AI Workspace Workflow with Disposable Worker and Photo Fixtures

## Related Specification(s)

- UI-011A AI Collection Workspace Specification.
- UI-011B stable review state machine.
- [Testing Strategy](../Testing-Strategy.md).

## Goal

Provide deterministic end-to-end evidence for model configuration, remote
Photo sampling, two-stage AI output, review, unique Promotion, and archival.

## Scope

- Disposable Album database, directories/images, Tokens, filtered dispatch
  candidates, Batches/Reservations/Groups, AI Workspace, configurations, mock
  llama.cpp provider, Worker process, logs, snapshots, and outputs.
- Happy paths for one Album under multiple model configurations.
- Authorization, claim, Manifest, transfer, hash-change, result-schema, rework,
  rejection, stale decision, competing Promotion, idempotency, and archive scenarios.
- Durable assertions across Workspace, Item, evidence, Operation, Issue, Album,
  Reservation, promotion, release, and historical access boundaries.
- Cross-Worker reservation conflict, multi-configuration single-Group behavior,
  unchanged Status at dispatch, Promotion Status policy, and redispatch history.

## Out of Scope

- AI model quality benchmarks or production model downloads.
- UI browser actions, owned by UI-011D.

## Dependencies

- BT-043 through BT-052 and BT-054 through BT-057 implemented.
- Approved test JSON corpus and tiny non-sensitive image fixtures.

## Implementation Steps

1. Extend workflow sandbox and mock Worker/provider with safe image fixtures
   plus at least two Worker kinds for reservation-conflict proof.
2. Implement scenario matrix with exact zero-side-effect and durable-state assertions.
3. Add an AI Workspace workflow-readiness suite and run it repeatedly from clean roots.

## Acceptance Criteria

- The Worker receives only Manifest-bound images and submits only to its claim.
- Same Album/different configurations remain comparable and independently auditable.
- Reject has no permanent side effect; exactly one competing approved run promotes.
- Archived history is read-only and legacy `workspace_album` never enters any scenario.
- Dispatch does not change Album Status; successful name Promotion maps only
  `TEMPORARY` to `NAME_GENERATED`, and release preserves all Group history.
- All retained artifacts are disposable and redact Tokens and absolute production paths.

## Verification

- Run the AI Workspace workflow suite twice from clean fixtures.
- Run Backend workflow-readiness twice and complete Backend regression once.
- Provide the Backend fixture contract required by UI-011D.

## Risks or Notes

- Mock outputs must exercise the same versioned JSON validation as real llama.cpp
  results rather than bypassing the submission boundary.
