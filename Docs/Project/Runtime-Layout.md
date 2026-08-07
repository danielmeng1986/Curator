# Curator Runtime Layout

## Purpose

This document establishes the repository boundary between versioned source and
local runtime state. It is introduced by MT-001 before application code moves
to the target layout.

## Target layout

```text
apps/
  backend/              Backend source; owns repositories and migrations
  web/                  Web-client source
workers/
  ai_worker/            Out-of-process AI Worker source
tools/
  dev/                  Retained developer-only utilities
legacy/                 Historical code retained only with a manifest
var/
  data/                 Local database files and SQLite sidecars
  backups/              Local database snapshots
  logs/                 Local JSONL and operational logs
  outputs/              Generated reports and other disposable outputs
config/                 Committed examples plus ignored local overrides
```

`var/` is wholly local runtime state. Its directory markers are versioned only
so a fresh clone exposes the intended destinations; no database, backup, log,
output, token, or model file may be committed there.

The existing `database/`, `outputs/`, and legacy application backup/log
locations remain untouched during MT-001. They are transitional runtime paths
and remain ignored until their owning code moves in later tasks.

## Local configuration and secrets

Every machine-specific configuration file is copied from a committed
`.example` file and ignored by Git. Examples must use placeholders, not local
absolute paths or secrets. Registration secrets, bearer tokens, credentials,
and deployment-specific values are environment or protected-deployment
settings; they are never checked into the repository.

## Database schema and migrations

The versioned source of database evolution is `apps/backend/migrations/`.
Each migration is a reviewed, ordered source artifact, named
`NNNN_short_description.sql` (or the equivalent migration implementation once
the Backend owns a runner). Runtime database files and migration backups remain
under `var/`, never beside the migration source.

Migrations must state their preconditions, preserve existing data, be safe to
identify as already applied, and include verification and recovery guidance.
MT-002 supplies the Backend composition root and establishes this source
location; its migration runner is added when the first schema migration is
implemented in MT-007.

## Fresh-clone setup

1. Copy the required configuration examples to their ignored local names and
   set local filesystem paths.
2. Provide secrets through the local environment or deployment mechanism.
3. Create or restore runtime data only under `var/` after the Backend migration
   path is active. Tests instead use disposable fixtures and temporary paths.
