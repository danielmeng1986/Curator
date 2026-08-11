# DOC-002 — Refresh AI Agent Context and Documentation Index

## Task ID

`DOC-002` — Status: `Complete`

## Goal

Make `Docs/AI-CONTEXT.md` and `Docs/README.md` accurate entry points that route
humans and AI Agents to current architecture, contracts, schema, tasks, and
historical material.

## Scope

- Replace the obsolete Normalize/Workspace Database/Commit overview with the
  current Backend-owned database and REST client boundaries.
- Describe apps.backend, apps.web, external AI Worker, Work Dispatch, AI review,
  and future native Curator boundaries at an orientation level.
- Publish reading paths by task type: Backend, UI, database, AI Worker,
  migrations, and architecture discussion.
- Remove nonexistent or stale navigation entries and link documentation governance.

## Out of Scope

- Duplicating full Backend or Database Specifications.
- Defining the future macOS application beyond linking its memo.

## Inputs and Authority

- DOC-001.
- Current Backend/UI architecture and completed Database documentation tasks.
- Project runtime layout and task indexes.

## Deliverables

- Updated `Docs/AI-CONTEXT.md`.
- Updated `Docs/README.md`.
- A concise task-oriented reading-order table.

## Acceptance Criteria

- An AI Agent is directed to current Specifications before changing behavior.
- Backend database ownership and REST-only external client access are explicit.
- Historical Workspace and future native application material are clearly labeled.
- Every documented directory and entry-point link exists.

## Verification

- Run a documentation link check.
- Walk through representative Backend, UI, database, and AI Worker task-routing scenarios.

## Dependencies

- DOC-001.
- DBDOC-001 through DBDOC-005.

## Risks or Notes

- The entry point should orient and route; excessive detail will make it stale again.

## Completion Record

- Rewrote AI Context around current Backend ownership, apps.web, external Worker,
  Dispatch, evidence, review, Promotion, and historical boundaries.
- Rebuilt the documentation index with real current entry points and task-oriented paths.
- Removed the nonexistent ADR directory from the active reading path and labeled
  the native application Memo and Historical Workspace correctly.
