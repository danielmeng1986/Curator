# Database migrations

This directory is the versioned source of Curator database schema evolution.
It intentionally contains migration source only, never a live SQLite database,
WAL/SHM sidecar, snapshot, or migration output.

Use ordered names such as `0015_add_example_column.sql`. Each migration must
document its preconditions, data-preservation behavior, verification query or
test, and recovery instructions.

Run the reviewed migration explicitly during a Backend maintenance window:

```bash
python3 -m apps.backend.migrations
```

The runner defaults to `var/data/Curator.db`, creates a timestamped verified
SQLite snapshot under `var/backups/` before its first write, applies every
unrecorded migration in filename order inside one transaction, verifies
integrity and foreign keys after every step, and records each applied filename
stem in `schema_migration`. It is safe to rerun. Use `--database` and
`--backup-dir` to work on an explicit local copy. It never runs automatically
when the HTTP server starts.

`0000_base_catalog.sql` is the canonical empty-database bootstrap. `0014`
brings Authentication and operational workflow tables under migration
ownership. Repository `CREATE TABLE IF NOT EXISTS` calls remain defensive
compatibility checks and must match these sources.

`0016` adds the immutable Work Item `worker_kind`, deterministically backfills
existing Album-analysis Items as `album_name_analysis`, and adds the nullable
historical attempt capability snapshot used by new claims.

An existing database with active rows in historical `workspace_album` must run
the guarded MT-008 archive command before the ordered runner can record `0002`:

```bash
python3 -m apps.backend.migrations.archive_workspace_album --database /path/to/copy.db --apply
```

The runner refuses to silently classify or archive those rows.
