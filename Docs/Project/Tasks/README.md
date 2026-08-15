# Curator Project Migration Tasks

This directory plans cross-cutting repository migration work. It complements
`Docs/Backend/Tasks`: Backend tasks implement specified behavior, while these
Migration Tasks move the project into its long-lived layout without changing
the supported Backend contract.

Task IDs use `MT-<three-digit-sequence>` and are executed in dependency order.
The target architecture is the modular monolith defined in
[Backend Architecture](../../Backend/Backend-Architecture.md): Backend owns
database access; Web UI, AI Worker, and tools are API clients.

## Task index

| Task | Outcome | Status |
| --- | --- | --- |
| [MT-001](MT-001-establish-project-runtime-boundaries.md) | Project runtime boundaries | Completed |
| [MT-002](MT-002-relocate-backend-into-modular-monolith.md) | Backend modular-monolith layout | Completed |
| [MT-003](MT-003-migrate-web-client-to-api-only-layout.md) | API-only Web client | Completed |
| [MT-004](MT-004-establish-ai-worker-api-client.md) | AI Worker API-client foundation | Completed |
| [MT-005](MT-005-retire-and-archive-legacy-code.md) | Retired legacy code archive | Completed |
| [MT-006](MT-006-ui-workflow-acceptance.md) | UI workflow acceptance foundation | Completed |
| [MT-007](MT-007-add-album-remark-schema-compatibility.md) | Album remark compatibility | Completed |
| [MT-008](MT-008-close-and-archive-historical-workspace-albums.md) | Historical Workspace closure/archive | Completed |
| [MT-009](MT-009-add-runnable-ai-worker.md) | Runnable, enrollable WSL2 AI Worker | Completed |
| [MT-010](MT-010-add-capability-aware-waiting-ai-worker.md) | Capability-declared long-poll AI Worker | Completed |
