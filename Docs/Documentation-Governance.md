# Curator Documentation Governance

> Documentation status: Current  
> Owner: Project documentation  
> Last verified: 2026-08-11

## Purpose

Curator documentation preserves intent, contracts, current architecture, and
decision history. This policy tells humans and AI Agents what a document means,
which source controls a decision, and how to keep documentation truthful as the
system changes.

## Document lifecycle classes

| Class | Meaning | May control new work? |
| --- | --- | --- |
| `Current` | Verified description of the implemented or operational system. | Yes, within its declared scope. |
| `Approved` | Reviewed target contract or design that may not yet be fully implemented. | Yes; implementation status must still be checked. |
| `Historical` | Completed migration record, retired design, or preserved former behavior. | No; use only for provenance or recovery context. |
| `Memo` | Non-binding idea, exploration, or future product direction. | No; promote it through Architecture, Specification, and Tasks first. |
| `Task` | Bounded work item with its own execution status. | It authorizes only the scope stated by the task. |

Task execution status (`Proposed`, `Ready`, `In Progress`, `Blocked`,
`Complete`, or `Superseded`) is separate from document lifecycle. A completed
task is historical evidence of delivery; it is not automatically the current
behavioral contract.

## Reusable status header

New or materially reworked non-task documents use this compact header directly
below the title:

```text
> Documentation status: Current | Approved | Historical | Memo
> Owner: Backend | UI | Database | Project documentation | Project
> Last verified: YYYY-MM-DD
```

Use `Last verified`, not an automatically changing timestamp. Update it only
after checking the document against its declared authority. Existing documents
may adopt the header when they are next materially reviewed; DOC-001 does not
pretend that all legacy documents have already been classified.

Tasks retain their established `Task ID — Status` field and do not need the
non-task header.

## Authority by question

There is no single document that wins every kind of disagreement. Use the
source that owns the question:

| Question | Primary authority | Supporting evidence |
| --- | --- | --- |
| What does the running system currently do? | Active source code and passing tests | Current architecture and supported-surface docs |
| What behavior is allowed or required? | Approved Specifications | Acceptance tests and completed implementation tasks |
| What is the persisted physical schema? | Declared authoritative schema/migrations | Disposable DB introspection and migration tests |
| Why is the system divided this way? | Current Architecture and accepted ADRs | Specifications and implementation |
| What is the product/domain meaning? | Current conceptual/domain documents | Architecture and Specifications |
| Is planned work complete? | Owning task file and task index | Commit and verification evidence |
| What was true before retirement? | Historical documents and migration records | Archived source and completed tasks |
| What might be built later? | Memo | No authority until promoted |

If current code contradicts an approved Specification, code remains evidence of
actual behavior but does not silently rewrite the contract. Record the mismatch
and create the appropriate implementation or Specification task. If a current
document contradicts both code and accepted Specification, classify it as stale
and do not use it to justify a change.

## Precedence within a change

1. Read the governing Specification and current Architecture for the affected boundary.
2. Inspect active implementation and acceptance evidence.
3. Inspect the authoritative schema for persistence changes.
4. Use Tasks to determine delivery status and approved scope.
5. Consult conceptual documents for domain meaning.
6. Consult Historical documents and Memos only for context.

Security, destructive operations, authentication, recovery, and data-retention
rules require explicit approved contracts. Observed implementation alone must
not be generalized into a new safety policy.

## Ownership and task routing

| Change discovered | Owning task series |
| --- | --- |
| Backend behavior, API, persistence implementation, security, or workflow | `BT-*` |
| Web UI behavior or browser acceptance | `UI-*` |
| Repository/runtime boundary or cross-project migration | `MT-*` |
| Cross-document governance, navigation, architecture, or conceptual correction | `DOC-*` |
| Database catalog, diagrams, persistence maps, or schema-doc verification | `DBDOC-*` |

A DOC or DBDOC task may describe an implementation gap but must not silently
change runtime behavior. Create or unblock the owning BT, UI, or MT task.
Likewise, implementation tasks must update affected Current/Approved documents
before completion when they change a documented boundary.

## Review triggers

Review affected documentation when any of the following changes:

- a table, column, constraint, index, migration, or retention rule;
- a public API resource, role, error, state transition, or destructive action;
- application ownership, runtime entry point, or external-client boundary;
- a workflow's transaction, evidence, audit, failure, or recovery behavior;
- a product concept moving between Memo, Approved, Current, or Historical;
- a task becoming blocked, superseded, or complete in a way that changes navigation.

## Archival rules

- Preserve decision and migration history; do not rewrite it as if the former
  design never existed.
- Move retired active guidance into an appropriate `Historical/` location when
  practical, and add a visible `Historical` header.
- State the retirement reason, replacement, and controlling task.
- Remove Historical documents from active reading paths while keeping direct
  links from migration or provenance records.
- Never use `Historical` or `Memo` material as an active API, schema, or safety contract.

## Representative classifications

| Document | Classification | Reason |
| --- | --- | --- |
| `Backend/Specifications/API-Contract.md` | Approved/current contract | Controls shared API behavior; implementation evidence verifies it. |
| `UI/Workflow-Readiness-Matrix.md` | Current | Reports implemented UI coverage and gate evidence. |
| `Database/Copilot_Schema_and_Migration_Instructions.md` | Historical candidate | One-time v0.2 migration guidance; DBDOC-005 will relocate it. |
| `Backend/Backend-Architecture.md` | Current but due re-verification | Owns boundaries; DOC-004 will remove stale proposal language. |
| `Project/macOS-Native-Curator-Memo.md` | Memo | Preserves future product thinking without authorizing implementation. |
| `Tasks/DOC-001-establish-documentation-authority-and-lifecycle.md` | Task | Bounded documentation-governance delivery record. |

## Completion rule

A documentation task is complete only when its deliverables exist, links
resolve, examples and diagrams render where applicable, conflicts are either
resolved or assigned to the correct task series, and its index and completion
record reflect verified evidence.

