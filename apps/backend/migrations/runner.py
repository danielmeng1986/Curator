"""Small, dependency-free runner for ordered Curator SQLite migrations.

The runner deliberately keeps schema evolution explicit: migrations do not run
when the HTTP server starts.  A curator invokes this module during a maintenance
window, receives a verified backup path, and can safely repeat the command.
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


MIGRATION_ID = "0001_add_album_remark"
MIGRATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = MIGRATION_DIR.parents[2]
DEFAULT_DATABASE = REPO_ROOT / "var" / "data" / "Curator.db"
DEFAULT_BACKUP_DIR = REPO_ROOT / "var" / "backups"


class MigrationError(RuntimeError):
    """Raised when a database does not meet a migration precondition."""


@dataclass(frozen=True)
class MigrationResult:
    database: Path
    backup: Path | None
    applied: bool
    adopted_existing_column: bool


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


def _album_columns(conn: sqlite3.Connection) -> set[str]:
    if not _table_exists(conn, "album"):
        raise MigrationError("Precondition failed: required table 'album' does not exist.")
    return {row[1] for row in conn.execute("PRAGMA table_info(album)")}


def _migration_recorded(conn: sqlite3.Connection) -> bool:
    return _table_exists(conn, "schema_migration") and conn.execute(
        "SELECT 1 FROM schema_migration WHERE migration_id = ?", (MIGRATION_ID,)
    ).fetchone() is not None


def _verify_database(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise MigrationError(f"SQLite integrity check failed for {path}: {integrity}")


def _create_verified_backup(database: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = backup_dir / f"Curator_{stamp}_{MIGRATION_ID}.db"
    with sqlite3.connect(database) as source, sqlite3.connect(backup) as destination:
        source.backup(destination)
    _verify_database(backup)
    return backup


def migrate(database: Path | str = DEFAULT_DATABASE, backup_dir: Path | str = DEFAULT_BACKUP_DIR) -> MigrationResult:
    """Apply MT-007 to *database*, creating a verified backup before writes."""
    database = Path(database).expanduser().resolve()
    backup_dir = Path(backup_dir).expanduser().resolve()
    if not database.is_file():
        raise MigrationError(f"Database not found: {database}")

    # Read before any write so a completed migration is a true no-op.
    with sqlite3.connect(database) as conn:
        columns = _album_columns(conn)
        recorded = _migration_recorded(conn)
    if recorded:
        if "remark" not in columns:
            raise MigrationError(
                f"Migration {MIGRATION_ID} is recorded but album.remark is absent; restore a backup before retrying."
            )
        return MigrationResult(database, None, applied=False, adopted_existing_column=False)

    backup = _create_verified_backup(database, backup_dir)
    adopted_existing_column = "remark" in columns
    sql = (MIGRATION_DIR / "0001_add_album_remark.sql").read_text(encoding="utf-8")
    try:
        with sqlite3.connect(database) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """CREATE TABLE IF NOT EXISTS schema_migration (
                    migration_id TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )"""
            )
            if not adopted_existing_column:
                # The source is intentionally a single DDL statement.  Do not
                # use executescript here: it performs an implicit commit before
                # running its script and would weaken the transaction boundary.
                conn.execute(sql)
            if "remark" not in _album_columns(conn):
                raise MigrationError("Migration did not create nullable album.remark.")
            violations = conn.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise MigrationError(f"Foreign-key check failed: {violations}")
            conn.execute(
                "INSERT INTO schema_migration (migration_id, applied_at) VALUES (?, ?)",
                (MIGRATION_ID, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
    except Exception:
        # The backup remains intact and is the recovery source for a failed write.
        raise
    _verify_database(database)
    return MigrationResult(database, backup, applied=True, adopted_existing_column=adopted_existing_column)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply Curator SQLite schema migrations.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    args = parser.parse_args(argv)
    try:
        result = migrate(args.database, args.backup_dir)
    except MigrationError as exc:
        parser.error(str(exc))
    if result.applied:
        mode = "adopted existing column" if result.adopted_existing_column else "applied"
        print(f"{mode}: {MIGRATION_ID}")
        print(f"verified backup: {result.backup}")
    else:
        print(f"already applied: {MIGRATION_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
