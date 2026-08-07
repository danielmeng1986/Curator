"""MT-008 archival migration for the completed historical workspace_album set."""
from __future__ import annotations

import argparse
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .runner import DEFAULT_BACKUP_DIR, DEFAULT_DATABASE, MigrationError, _create_verified_backup, _verify_database

MIGRATION_ID = "0002_archive_historical_workspace_album"


def inventory(database: Path | str) -> dict:
    """Return a complete, non-mutating classification summary."""
    with sqlite3.connect(database) as conn:
        total = conn.execute("SELECT COUNT(*) FROM workspace_album").fetchone()[0]
        invalid = conn.execute("""SELECT COUNT(*) FROM workspace_album w
            LEFT JOIN album a ON a.id = w.album_id LEFT JOIN studio s ON s.id = a.studio_id
            WHERE a.id IS NULL OR w.expected_path IS NULL OR w.current_path <> w.expected_path
               OR w.studio_name <> s.name OR w.album_name <> a.title OR w.expected_path <> a.path""").fetchone()[0]
        missing_relations = conn.execute("""SELECT COUNT(*) FROM workspace_album w
            JOIN workspace_album parent ON parent.id = w.belongs_to_album_id
            LEFT JOIN album_relation ar ON ar.album_id = w.album_id AND ar.related_album_id = parent.album_id AND ar.relation_type = 'BELONGS_TO'
            WHERE w.belongs_to_album_id <> w.id AND ar.id IS NULL""").fetchone()[0]
        duplicate_paths = conn.execute("SELECT COUNT(*) FROM (SELECT path FROM album WHERE path IS NOT NULL GROUP BY path HAVING COUNT(*) > 1)").fetchone()[0]
    return {"total": total, "already_materialized": total - invalid, "invalid": invalid,
            "missing_relations": missing_relations, "duplicate_paths": duplicate_paths}


def apply(database: Path | str = DEFAULT_DATABASE, backup_dir: Path | str = DEFAULT_BACKUP_DIR) -> dict:
    database, backup_dir = Path(database).resolve(), Path(backup_dir).resolve()
    report = inventory(database)
    if report["invalid"] or report["missing_relations"] or report["duplicate_paths"]:
        raise MigrationError(f"MT-008 validation failed: {report}")
    with sqlite3.connect(database) as conn:
        recorded = conn.execute("SELECT 1 FROM schema_migration WHERE migration_id = ?", (MIGRATION_ID,)).fetchone()
    if recorded:
        return {**report, "applied": False, "backup": None}
    backup = _create_verified_backup(database, backup_dir, MIGRATION_ID)
    operation_uuid, now = str(uuid.uuid4()), datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(database) as conn:
        conn.execute("PRAGMA foreign_keys = ON"); conn.execute("BEGIN IMMEDIATE")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(workspace_album)")}
        for name, ddl in (("lifecycle_state", "TEXT NOT NULL DEFAULT 'active'"), ("archive_classification", "TEXT"), ("archive_reason", "TEXT"), ("archived_at", "TEXT"), ("archive_operation_uuid", "TEXT")):
            if name not in columns: conn.execute(f"ALTER TABLE workspace_album ADD COLUMN {name} {ddl}")
        conn.execute("INSERT INTO operation (uuid, operation_type, initiator, status, summary, started_at, ended_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (operation_uuid, "historical_workspace_archive", "System", "Succeeded", f"Archived {report['total']} already-materialized workspace_album records.", now, now))
        conn.execute("UPDATE workspace_album SET lifecycle_state='archived_retired', archive_classification='already_materialized', archive_reason='MT-008 verified historical materialization', archived_at=?, archive_operation_uuid=?", (now, operation_uuid))
        conn.execute("INSERT INTO schema_migration (migration_id, applied_at) VALUES (?, ?)", (MIGRATION_ID, now))
        if conn.execute("PRAGMA foreign_key_check").fetchall(): raise MigrationError("Foreign-key check failed.")
        conn.commit()
    _verify_database(database)
    return {**report, "applied": True, "backup": str(backup), "operation_uuid": operation_uuid}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE); parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR); parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv); report = inventory(args.database)
    if not args.apply: print(report); return 0
    print(apply(args.database, args.backup_dir)); return 0

if __name__ == "__main__": raise SystemExit(main())
