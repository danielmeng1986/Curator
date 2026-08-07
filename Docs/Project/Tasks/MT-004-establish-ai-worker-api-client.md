# MT-004 — Establish AI Worker as an API Client

## Task ID

`MT-004` — Status: `Completed`

## Title

Establish AI Worker as an API Client

## Related Specification(s)

- [Backend Architecture](../../Backend/Backend-Architecture.md), REST external write boundary.
- [AI Architecture](../../05-AI.md).
- [Authentication](../../Backend/Specifications/Authentication.md).

## Goal

Move llama.cpp analysis and candidate-name generation into `workers/ai_worker`,
where it communicates with Curator only through authenticated `/api/v1` calls
and future dataset-specific AI Workspace operations.

## Scope

- Separate model-provider adapters, prompt/profile configuration, analysis workflows, and API client code.
- Define the client boundary for durable request/result hand-off through a
  future, separately specified AI Workspace API.
- Add worker configuration templates, token handling, retries, and safe diagnostic output.

## Out of Scope

- Direct SQLite access or in-process Service imports.
- Creating, editing, promoting, or reviving the historical `workspace_album`
  collection.
- Inventing an AI Workspace schema, AI-result persistence endpoint, or
  promotion contract before its dataset-specific Specification exists.

## Dependencies

- `MT-001` — configuration and runtime boundaries.
- `MT-002` and `MT-003` — stable Backend API conventions.
- `BT-031` — generic Workspace lifecycle and promotion baseline; it does not
  authorize use of `workspace_album` by the Worker.
- A future AI Workspace Specification — before the Worker submits durable AI
  results or requests promotion.

## Implementation Steps

1. Inventory existing llama.cpp scripts, profiles, prompts, and outputs.
2. Move provider code and orchestration into the Worker with an API client
   boundary that has no historical Workspace-table knowledge.
3. Add isolated provider doubles and authenticated API integration tests for
   supported endpoints; leave durable result submission behind a future
   specified client operation.

## Acceptance Criteria

- The Worker never opens `Curator.db` or imports Backend repositories/services.
- Model profiles are versioned configuration; runtime outputs remain untracked.
- Failed worker calls preserve a recoverable, diagnosable Backend outcome.
- The Worker neither reads nor writes `workspace_album`, and it cannot treat a
  successful model response as approval or permanent Album materialization.

## Verification

- Run Worker unit tests with a fake provider and API integration tests against a disposable Backend.
- Verify a writer token cannot perform administrative operations.

## Risks or Notes

- `workspace_album` is a historical collection being closed and archived by
  `MT-008`; it is not an AI Worker integration surface. Define a new
  dataset-specific AI Workspace Specification before adding an AI submission
  endpoint or a promotion journey.

## Completion Record

- Added an isolated Worker API client, llama.cpp provider adapter, retrying
  suggestion-only workflow, and fake-provider test. The Worker has no SQLite
  or Backend-service dependency and exposes no durable-result operation.
