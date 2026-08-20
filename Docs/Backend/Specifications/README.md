# Curator Backend Specifications

## Purpose

This library defines the behavioral contracts for the Curator Backend. It inherits the responsibilities and boundaries in [Backend Architecture](../Backend-Architecture.md); it does not replace or reinterpret them.

```text
Vision
  ↓
Architecture
  ↓
Specification
  ↓
Implementation
  ↓
Testing
```

Specifications define observable behavior, valid and invalid states, responsibilities, records, and recovery expectations. Implementation chooses language, libraries, framework, and internal code structure without changing these contracts. Tests validate the contracts described here.

## How to use this library

- Read the relevant Specification before implementing or changing a Backend capability.
- Treat **Architectural decisions** as fixed unless an ADR-level change is approved.
- Treat **Specification decisions** as implementation requirements once resolved here.
- Treat **Open Questions** as unresolved. Do not infer an answer in code; resolve and document it first.
- Keep future enhancements separate from current requirements.

## Documents

| Document | Behavioral boundary |
| --- | --- |
| [API Specification](API-Specification.md) | `/api/v1` client contract, request handling, responses, errors, and pagination. |
| [API Contract](API-Contract.md) | Shared `/api/v1` envelopes, errors, status mapping, access policy, collections, and workflow outcomes. |
| [Repository Specification](Repository-Specification.md) | Persistence contracts, entities, and read models. |
| [Workspace Workflow](Workspace-Workflow.md) | Temporary workspace lifecycle and controlled promotion. |
| [AI Workspace Acceptance Fixture](AI-Workspace-Acceptance-Fixture.md) | Disposable Backend contract for BT-053 and UI-011D. |
| [Work Dispatch Workflow](Work-Dispatch-Workflow.md) | Album selection, exclusive reservations, dispatch batches, Worker groups, and redispatch safety. |
| [Import Workflow](Import-Workflow.md) | Import preview, validation, persistence, filesystem work, and repair hand-off. |
| [Digital Asset Trash](Digital-Asset-Trash.md) | Catalog visibility, recoverable Trash, restore, retention/hold, permanent asset purge, and retained evidence. |
| [Repair Workflow](Repair-Workflow.md) | Detection, repair states, user confirmation, and verification. |
| [Snapshot Specification](Snapshot-Specification.md) | Risk-based snapshot decisions, restore, retention, and metadata. |
| [Operation Logging](Operation-Logging.md) | Database-first operation history and supporting JSONL logs. |
| [Authentication](Authentication.md) | Device registration, approval, tokens, scopes, renewal, and revocation. |
| [Issue Management](Issue-Management.md) | Cross-cutting Issues and their lifecycle. |
| [Canonical Path Rules](Canonical-Path-Rules.md) | Path normalization, comparison, collision handling, and final database safety. |

## Shared conventions

- The Backend owns all business rules, writes, transactions, and database access.
- Web UI, AI Worker, CLI tools, and other clients use `/api/v1`; they never access the database directly.
- UUID is the externally stable identity for business entities, except stable lookup data such as `status` where architecture permits an integer identifier.
- A behavior that creates material state must be attributable to an initiator and produce an Operation record when required by the applicable Specification.
- A future PostgreSQL implementation must preserve these behavioral contracts; SQLite remains the current implementation.

## Specification status

This is the first milestone of the library. It establishes contracts and identifies unresolved decisions. It intentionally does not prescribe code, storage engines, HTTP libraries, ORMs, schemas beyond required persistent concepts, or framework choices.
