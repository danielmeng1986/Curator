# Database migrations

This directory is the versioned source of Curator database schema evolution.
It intentionally contains migration source only, never a live SQLite database,
WAL/SHM sidecar, snapshot, or migration output.

Use ordered names such as `0001_add_example_column.sql`. Each migration must
document its preconditions, data-preservation behavior, verification query or
test, and recovery instructions.

Run the reviewed migration explicitly during a Backend maintenance window:

```bash
python3 -m apps.backend.migrations
```

The runner defaults to `var/data/Curator.db`, creates a timestamped verified
SQLite snapshot under `var/backups/` before its first write, records applied
versions in `schema_migration`, and is safe to rerun. Use `--database` and
`--backup-dir` to work on an explicit local copy. It never runs automatically
when the HTTP server starts.
