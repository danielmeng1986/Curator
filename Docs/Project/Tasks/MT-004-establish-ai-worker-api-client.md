# MT-004 — Establish AI Worker as an API Client

## Task ID

`MT-004` — Status: `Proposed`

## Title

Establish AI Worker as an API Client

## Related Specification(s)

- [Backend Architecture](../../Backend/Backend-Architecture.md), REST external write boundary.
- [AI Architecture](../../05-AI.md).
- [Authentication](../../Backend/Specifications/Authentication.md).

## Goal

Move llama.cpp analysis and candidate-name generation into `workers/ai_worker`,
where it communicates with Curator only through authenticated `/api/v1` calls.

## Scope

- Separate model-provider adapters, prompt/profile configuration, analysis workflows, and API client code.
- Define durable request/result hand-off through supported Workspace or future specified API operations.
- Add worker configuration templates, token handling, retries, and safe diagnostic output.

## Out of Scope

- Direct SQLite access or in-process Service imports.
- Inventing a Workspace promotion or AI-result persistence contract not yet specified.

## Dependencies

- `MT-001` — configuration and runtime boundaries.
- `MT-002` and `MT-003` — stable Backend API conventions.
- `BT-031` where candidate results require permanent promotion.

## Implementation Steps

1. Inventory existing llama.cpp scripts, profiles, prompts, and outputs.
2. Move provider code and orchestration into the Worker with an API client boundary.
3. Add isolated provider doubles and authenticated API integration tests.

## Acceptance Criteria

- The Worker never opens `Curator.db` or imports Backend repositories/services.
- Model profiles are versioned configuration; runtime outputs remain untracked.
- Failed worker calls preserve a recoverable, diagnosable Backend outcome.

## Verification

- Run Worker unit tests with a fake provider and API integration tests against a disposable Backend.
- Verify a writer token cannot perform administrative operations.

## Risks or Notes

- Define a new Backend Specification before adding any missing AI submission endpoint.
