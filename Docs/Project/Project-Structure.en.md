# Curator Project Structure

[中文](Project-Structure.zh.md)

## Purpose

This document describes Curator's current long-lived project boundaries.
Application code, runtime state, configuration, documentation, and developer
tools are separated. Clients and Workers access business data only through the
authenticated Backend API; they never open the SQLite database directly.

## Directory overview

```text
Curator/
├── apps/
│   ├── backend/       Backend, domain services, repositories, migrations, tests
│   └── web/           Web-client source and client tests
├── workers/
│   └── ai_worker/     Out-of-process AI Worker; API-only Backend client
├── config/            Versioned configuration examples and guidance
├── var/               Local runtime state (not committed)
│   ├── data/          Current SQLite database and WAL/SHM sidecars
│   ├── backups/       Current snapshots and migration recovery backups
│   ├── logs/          Backend operation and backup logs
│   └── outputs/       Disposable runtime output
├── Docs/              Specifications, architecture, tasks, and project docs
├── tools/
│   └── dev/           Developer-only utilities, such as benchmarks
├── outputs/           Old local output residue; not a supported runtime path
└── .github/           Repository automation and collaboration guidance
```

## Application boundaries

### `apps/backend/`

The sole runnable Backend, started with `python3 -m apps.backend`. It owns
database access, migrations, business rules, authentication, `/api/v1`, and
Backend tests. Schema evolution source lives in `apps/backend/migrations/`.
Migrations run only when explicitly invoked, never merely because the server
starts.

### `apps/web/`

The browser client source. Its static assets are served by the Backend and are
normally opened at `http://127.0.0.1:8788`, not directly via `file://`. The
client stores a device token in its browser profile and uses authenticated
`/api/v1` calls; it does not read database files.

### `workers/ai_worker/`

The foundation for an independent AI Worker. It encapsulates model providers,
retries, and an API client, and currently creates local suggestion-only output.
It may not open `Curator.db`, import Backend internals, or read/write archived
`workspace_album` data. Persistent AI results await a dedicated AI Workspace
specification and API.

## Configuration and runtime state

### `config/`

Only `.example` configuration and documentation are committed. Machine paths,
tokens, registration secrets, and other sensitive values belong in ignored
local configuration or environment variables, never Git.

### `var/`

The only supported local runtime directory. It is excluded from Git; databases,
backups, logs, and generated output belong here. Confirm recovery value before
moving or deleting its contents.

## Documentation and tools

### `Docs/`

The planning source for the project. `Docs/Backend/Specifications/` defines
business rules; `Docs/Project/` records runtime layout, project structure, and
migration work; `Docs/UI/` records UI direction and acceptance requirements.

### `tools/dev/`

Developer-only utilities, not part of the product runtime surface. It currently
contains model benchmark tools. They may reference historical analysis scripts
for research, but must not become runtime dependencies of the Backend, Web UI,
or Worker.

## Historical recovery

The former scripts, compatibility UI, and Workspace application were removed
from the current worktree. They are retained in the remote Git Tag
`legacy-preservation-2026-08-08`. To inspect or restore them, check out a copy
from that Tag rather than reconnecting them to current runtime paths.
