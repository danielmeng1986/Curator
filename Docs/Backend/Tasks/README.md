# Curator Backend Tasks

## Purpose

This directory is the implementation-planning layer for the Curator Backend. A Task document turns a bounded item from one or more Backend Specifications into independently implementable and verifiable work. It does not define new product behavior or override Architecture or Specifications.

The documentation hierarchy is:

```text
Vision
  ↓
Architecture
  ↓
Specification
  ↓
Task
  ↓
Implementation
  ↓
Testing
```

- **Architecture** defines enduring boundaries and responsibilities.
- **Specifications** define observable behavior and constraints.
- **Tasks** define a small, sequenced implementation unit that realizes specified behavior.
- **Implementation** contains the code, migrations, configuration, and tests that complete a task.

If a task exposes an ambiguity or missing decision, resolve the relevant Specification before implementation. A task must never silently invent backend behavior.

## Naming convention

Each task document uses this filename format:

```text
BT-<three-digit-sequence>-<short-kebab-case-title>.md
```

For example: `BT-003-shared-api-contract.md`.

Task IDs use the same `BT-<three-digit-sequence>` prefix. IDs are permanent: do not reuse an ID after a task is cancelled, superseded, or split. Mark the original document accordingly and create new IDs for replacement tasks. Use the next available sequence number rather than renumbering existing tasks.

## Creating a task

Start from [Task Template](Task-Template.md) and follow the [Task Decomposition Guidelines](Task-Decomposition-Guidelines.md). Link each task to the controlling Specification sections and keep its acceptance criteria observable. A task is ready for implementation only when its scope, dependencies, verification approach, and unresolved risks are explicit.

## Status and change control

Task documents may record a status near their Task ID (`Proposed`, `Ready`, `In Progress`, `Blocked`, `Complete`, or `Superseded`). Status does not replace source control history or test results. Update a task when its implementation boundary, dependencies, or verification evidence changes; do not use a task document to change a Specification.

## AI Workspace implementation sequence

The first Album-analysis AI Workspace is decomposed into the following proposed
Backend tasks. Their product and state-machine decisions are controlled by
UI-011A and UI-011B; implementation does not begin until those Specifications
are approved.

| Task | Outcome |
| --- | --- |
| [BT-043](BT-043-retire-historical-workspace-album-client-api.md) | Retire historical Workspace Album active-client access. |
| [BT-044](BT-044-ai-workspace-container-dataset-schema-contract.md) | Add the AI Workspace container and versioned Album-analysis Dataset. |
| [BT-045](BT-045-managed-llama-model-configuration-contract.md) | Manage portable, versioned llama.cpp configurations. |
| [BT-046](BT-046-album-ai-work-item-claim-contract.md) | Add Album AI Work Items, claims, leases, and retries. |
| [BT-047](BT-047-album-photo-evidence-manifest-contract.md) | Build Backend-selected immutable Photo evidence Manifests. |
| [BT-048](BT-048-controlled-ai-photo-evidence-transfer-api.md) | Stream only Manifest-bound evidence to Workers/Admins. |
| [BT-049](BT-049-two-stage-ai-result-submission-contract.md) | Validate Vision and Writer result stages. |
| [BT-050](BT-050-ai-workspace-review-evaluation-contract.md) | Add review, evaluation, approval, rejection, and rework. |
| [BT-051](BT-051-unique-album-name-promotion-contract.md) | Promote one unique approved Album name. |
| [BT-052](BT-052-ai-workspace-closure-archive-retention-contract.md) | Close/archive Workspaces and retain evidence. |
| [BT-053](BT-053-ai-workspace-workflow-acceptance-fixtures.md) | Prove the full workflow with disposable Worker/Photo fixtures. |
| [BT-054](BT-054-generic-work-dispatch-eligibility-contract.md) | Add generic dispatch identities, Worker eligibility, and Album-exclusive reservations. |
| [BT-055](BT-055-album-dispatch-candidate-preview-contract.md) | Query filtered Album candidates and bind a zero-write dispatch preview. |
| [BT-056](BT-056-atomic-album-ai-work-dispatch-execution.md) | Atomically reserve Albums and create AI comparison Work Items. |
| [BT-057](BT-057-work-dispatch-release-redispatch-safety.md) | Safely close Groups, release Albums, and preserve redispatch history. |
| [BT-058](BT-058-ai-workspace-ui-read-models.md) | Stable Workspace, dispatch, review, and Promotion UI projections. |
| [BT-059](BT-059-consolidate-canonical-schema-bootstrap-and-migrations.md) | Consolidate the canonical empty-database bootstrap and ordered migration path. |
| [BT-060](BT-060-managed-registration-proof-lifecycle.md) | Admin-managed hash-only Registration Proof lifecycle. |
| [BT-061](BT-061-client-owned-device-token-enrollment.md) | Client-owned Device Token activation after Admin approval. |

BT identifiers record planning order, not mandatory execution order. Dispatch
is an entry boundary for AI work, so BT-054 through BT-056 precede BT-047 in
the first complete workflow. BT-057 follows review and Promotion behavior.

Recommended implementation order:

`BT-054 → BT-055 → BT-056 → BT-047 → BT-048 → BT-049 → BT-050 → BT-051 → BT-057 → BT-052 → BT-053`.
