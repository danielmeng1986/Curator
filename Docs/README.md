# Curator Documentation

> Documentation status: Current
> Owner: Project documentation
> Last verified: 2026-08-11

Curator documentation preserves product intent, current architecture,
behavioral contracts, schema knowledge, delivery tasks, and decision history.
Start with [AI Context](AI-CONTEXT.md) for task routing and
[Documentation Governance](Documentation-Governance.md) for authority rules.

## Current system in one paragraph

Curator is a local-first digital asset management and intelligence platform.
`apps.backend` owns SQLite and all workflow/filesystem mutations; `apps.web` is
the Album-oriented administrative client; an external AI Worker communicates
only through authenticated REST and receives controlled Photo evidence. Admins
dispatch Albums, review AI results, and explicitly promote one approved name.
The historical `workspace_album` model is archived; the future macOS curator is
recorded only as a product Memo.

## Documentation map

| Area | Entry point | Authority/purpose |
| --- | --- | --- |
| AI Agent orientation | [AI-CONTEXT.md](AI-CONTEXT.md) | Current task routing and non-negotiable boundaries |
| Governance | [Documentation-Governance.md](Documentation-Governance.md) | Lifecycle, conflict, ownership, and archival rules |
| Vision/concepts | [01-Vision.md](01-Vision.md), [04-Data-Model.md](04-Data-Model.md), [05-AI.md](05-AI.md) | Product intent; check lifecycle labels before treating concepts as current |
| Backend | [Backend Architecture](Backend/Backend-Architecture.md), [Specifications](Backend/Specifications/README.md), [Supported Surface](Backend/Supported-Backend-Surface.md) | Current boundaries and approved behavior |
| Backend delivery | [Backend Tasks](Backend/Tasks/README.md), [Testing Strategy](Backend/Testing-Strategy.md), [Readiness Matrix](Backend/Workflow-Readiness-Matrix.md) | Implementation scope and evidence |
| Database | [Database Model](Database/Curator_Database_Model.md), [Schema Source](Database/Schema-Source-of-Truth.md), [Schema Catalog](Database/Schema-Catalog.md) | Physical persistence navigation and authority |
| Web UI | [UI Plan](UI/Curator_Web_UI_Plan.md), [UI Matrix](UI/Workflow-Readiness-Matrix.md), [UI Tasks](UI/Tasks/README.md) | apps.web behavior and browser acceptance |
| Runtime/project | [Runtime Layout](Project/Runtime-Layout.md), [Project Tasks](Project/Tasks/README.md) | Source/runtime boundaries and MT work |
| Documentation work | [Documentation Tasks](Tasks/README.md) | DOC/DBDOC maintenance plans and status |
| Historical database material | [Database Historical](Database/Historical/Historical-Workspace-Album.md) | Retired models and completed migrations; not active guidance |
| Future native product | [macOS Native Curator Memo](Project/macOS-Native-Curator-Memo.md) | Non-binding future product thinking |

## Reading order by task

1. Read Governance and AI Context.
2. Read the current Architecture for the affected component.
3. Read the controlling Specification and supported surface.
4. For persistence work, read Schema Source, Catalog, the domain diagram, and
   the relevant persistence workflow.
5. Read the owning task and its dependencies.
6. Inspect implementation and tests only after the contract boundary is clear.

## Documentation lifecycle

Documents are classified as `Current`, `Approved`, `Historical`, `Memo`, or
`Task`. Task execution status is separate. Existing older documents without a
header must be verified against current authority before use; DOC tasks are
progressively classifying and updating them.

Code and tests show what currently happens. Specifications state what behavior
is allowed or required. Declared schema sources define physical persistence.
Architecture explains boundaries. A mismatch is drift to resolve, not permission
to silently redefine the system.

## Maintenance rule

When behavior or schema changes, update the governing Specification/schema
source, affected Current documents, task status, and acceptance evidence in the
same delivery. Preserve retired guidance under Historical rather than leaving
it on an active reading path.
