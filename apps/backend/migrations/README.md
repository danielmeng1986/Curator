# Database migrations

This directory is the versioned source of Curator database schema evolution.
It intentionally contains migration source only, never a live SQLite database,
WAL/SHM sidecar, snapshot, or migration output.

Use ordered names such as `0001_add_example_column.sql`. Each migration must
document its preconditions, data-preservation behavior, verification query or
test, and recovery instructions. The migration runner is introduced by MT-002;
until then this directory establishes the authoritative source location.
