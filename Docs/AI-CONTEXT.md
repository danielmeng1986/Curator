# Curator AI Context

> Documentation status: Current
> Owner: Project documentation
> Last verified: 2026-08-11

## Purpose

This is the first documentation entry point for an AI Agent working on Curator.
Use it to locate authority; do not treat this overview as a substitute for the
Specification, schema source, or owning task.

## Current system

Curator is a local-first digital asset management and intelligence platform.
The active system has these boundaries:

- `apps.backend` owns SQLite, filesystem mutations, validation, workflows,
  authentication, audit, snapshots, recovery, and the versioned REST API.
- `apps.web` is the browser-based administration client. It manages digital
  assets primarily at Album level and never opens the database directly.
- The external Windows AI Worker uses authenticated REST only. It receives
  Backend-selected Manifest-bound Photo evidence and submits versioned results.
- SQLite is the metadata source of truth; the filesystem remains physical asset truth.
- Admin review and explicit Promotion control permanent AI-suggested Album-name changes.
- The former `workspace_album` client model is archived and unavailable to active clients.
- A future macOS native curator is a Memo, not an implemented application or contract.

## Active workflow map

```text
Approved device / Admin bootstrap
        ↓
Album catalog and direct Import
        ↓
Operation / Issue / Repair / recovery evidence
        ↓
Admin filters Albums for Work Dispatch
        ↓
Exclusive Album Reservation + model-configuration Work Items
        ↓
Worker claims → Photo Manifest → Vision result → Writer result
        ↓
Admin review → Approve / Reject / ReworkRequested
        ↓
Reviewed Promotion → one winning Album name
        ↓
Group release + Workspace close/archive with retained audit history
```

Album business Status is separate from Dispatch, Worker execution, and review state.

## Non-negotiable boundaries

- Clients do not access SQLite or call Services in-process.
- External writes use authenticated `/api/v1` contracts.
- Never use production/runtime data for tests, diagrams, or documentation extraction.
- Destructive or recovery actions require their approved preview, confirmation,
  Snapshot, authorization, replay, and failure contracts.
- AI recommends; a human approves permanent business changes.
- Historical documents and Memos provide context but do not authorize implementation.

## Authority and conflicts

Read [Documentation Governance](Documentation-Governance.md). In summary:

- source and passing tests evidence actual current behavior;
- approved Specifications control required/allowed behavior;
- declared schema sources control physical persistence;
- Architecture controls component boundaries;
- Tasks control delivery scope/status;
- Historical documents and Memos never override active contracts.

If code and Specification disagree, report the drift and create/update the
owning task. Do not silently choose one and rewrite the other.

## Task-oriented reading paths

| Work type | Read before acting |
| --- | --- |
| Backend/API/workflow | Governance → [Backend Architecture](Backend/Backend-Architecture.md) → relevant [Specification](Backend/Specifications/README.md) → Backend task → implementation/tests |
| Web UI | Governance → [UI plan](UI/Curator_Web_UI_Plan.md) → relevant UI chapter/matrix → UI task → browser evidence |
| Database/schema | Governance → [Schema Source](Database/Schema-Source-of-Truth.md) → [Schema Catalog](Database/Schema-Catalog.md) → relevant [diagram](Database/Curator_Database_Model.md) and persistence map → DBDOC/BT task |
| AI Worker/Workspace | Backend Architecture → Work Dispatch Specification → AI Workspace acceptance fixture → AI diagram/persistence map → BT/UI task |
| Runtime/repository migration | [Runtime Layout](Project/Runtime-Layout.md) → Project task index → owning MT task |
| Documentation maintenance | Governance → [Docs task index](Tasks/README.md) → owning DOC/DBDOC task |
| Future native product discussion | [macOS Memo](Project/macOS-Native-Curator-Memo.md); treat as non-binding Memo |

## Current task families

- `BT-*`: Backend behavior, API, persistence implementation, safety, and workflows.
- `UI-*`: apps.web behavior and browser acceptance.
- `MT-*`: cross-project runtime/repository migrations.
- `DOC-*`: documentation governance, navigation, architecture, and concepts.
- `DBDOC-*`: database catalog, diagrams, persistence documentation, and drift checks.

## Before completing a change

1. Verify the owning Specification and task status.
2. Use disposable fixtures and the relevant readiness gate.
3. Update Current/Approved documentation affected by the change.
4. Preserve audit, recovery, and historical evidence.
5. Record unresolved gaps in the correct task series rather than hiding them.
