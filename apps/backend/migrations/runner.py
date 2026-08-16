"""Explicit, ordered, backup-first Curator SQLite migration runner."""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


MIGRATION_ID = "0001_add_album_remark"  # compatibility for MT-007 callers/tests
MIGRATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = MIGRATION_DIR.parents[2]
DEFAULT_DATABASE = REPO_ROOT / "var" / "data" / "Curator.db"
DEFAULT_BACKUP_DIR = REPO_ROOT / "var" / "backups"
MIGRATION_FILES = tuple(sorted(MIGRATION_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")))


class MigrationError(RuntimeError):
    """Raised when a database cannot be safely constructed or upgraded."""


@dataclass(frozen=True)
class MigrationResult:
    database: Path
    backup: Path | None
    applied: bool
    adopted_existing_column: bool
    applied_migrations: tuple[str, ...] = ()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _verify_connection(conn: sqlite3.Connection) -> None:
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise MigrationError(f"SQLite integrity check failed: {integrity}")
    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise MigrationError(f"Foreign-key check failed: {violations}")


def _verify_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        _verify_connection(conn)


def _create_verified_backup(
    database: Path, backup_dir: Path, migration_id: str = "ordered_schema"
) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = backup_dir / f"Curator_{stamp}_{migration_id}.db"
    with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(backup)) as destination:
        source.backup(destination)
    _verify_database(backup)
    return backup


def _statements(sql: str):
    pending = ""
    for line in sql.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            statement = pending.strip()
            pending = ""
            if statement:
                yield statement
    if pending.strip():
        raise MigrationError("Migration source ends with an incomplete SQL statement.")


def _apply_sql(conn: sqlite3.Connection, source: Path) -> None:
    for statement in _statements(source.read_text(encoding="utf-8")):
        conn.execute(statement)


def _apply_0001(conn: sqlite3.Connection, source: Path) -> bool:
    if not _table_exists(conn, "album"):
        raise MigrationError("Migration 0001 requires the canonical album table.")
    adopted = "remark" in _columns(conn, "album")
    if not adopted:
        _apply_sql(conn, source)
    if "remark" not in _columns(conn, "album"):
        raise MigrationError("Migration 0001 did not create album.remark.")
    return adopted


def _apply_0002(conn: sqlite3.Connection) -> None:
    required = {
        "lifecycle_state": "TEXT NOT NULL DEFAULT 'active'",
        "archive_classification": "TEXT",
        "archive_reason": "TEXT",
        "archived_at": "TEXT",
        "archive_operation_uuid": "TEXT",
    }
    existing = _columns(conn, "workspace_album")
    active_rows = conn.execute(
        "SELECT COUNT(*) FROM workspace_album WHERE "
        + ("lifecycle_state <> 'archived_retired'" if "lifecycle_state" in existing else "1=1")
    ).fetchone()[0]
    if active_rows:
        raise MigrationError(
            "Migration 0002 requires guarded MT-008 archival for active "
            "workspace_album rows; run archive_workspace_album first."
        )
    for name, declaration in required.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE workspace_album ADD COLUMN "{name}" {declaration}')


def _apply_0015(conn: sqlite3.Connection) -> None:
    """Adopt columns that older defensive repositories may already have added."""
    conn.execute("""CREATE TABLE IF NOT EXISTS registration_proof_state (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1), proof_hash TEXT NOT NULL,
        created_at TEXT NOT NULL, rotated_at TEXT, disabled_at TEXT, last_used_at TEXT)""")
    if not _table_exists(conn,"device_registration"):
        raise MigrationError("Migration 0015 requires the device_registration table.")
    required={"candidate_token_hash":"TEXT","enrollment_proof_hash":"TEXT",
        "enrollment_expires_at":"TEXT","cancelled_at":"TEXT"}
    existing=_columns(conn,"device_registration")
    for name,declaration in required.items():
        if name not in existing:conn.execute(f'ALTER TABLE device_registration ADD COLUMN "{name}" {declaration}')


def _apply_0016(conn: sqlite3.Connection) -> None:
    """Adopt/backfill capability columns without replaying duplicate ALTERs."""
    if not _table_exists(conn,"workspace_album_ai_worker") or not _table_exists(conn,"ai_work_item_attempt"):
        raise MigrationError("Migration 0016 requires the AI Work Item and attempt tables.")
    if "worker_kind" not in _columns(conn,"workspace_album_ai_worker"):
        conn.execute("ALTER TABLE workspace_album_ai_worker ADD COLUMN worker_kind TEXT NOT NULL DEFAULT 'album_name_analysis'")
    if "worker_kinds_json" not in _columns(conn,"ai_work_item_attempt"):
        conn.execute("ALTER TABLE ai_work_item_attempt ADD COLUMN worker_kinds_json TEXT")
    conn.execute("""CREATE INDEX IF NOT EXISTS idx_ai_work_item_kind_queue
        ON workspace_album_ai_worker(worker_kind, run_state, created_at, id)""")


def _apply_0017(conn: sqlite3.Connection, source: Path) -> None:
    """Install Profile storage, bind configurations, and seed the published default."""
    _apply_sql(conn, source)
    if "instruction_profile_version_uuid" not in _columns(conn,"ai_model_configuration"):
        conn.execute("ALTER TABLE ai_model_configuration ADD COLUMN instruction_profile_version_uuid TEXT")
    from apps.ai_instruction_profile import DEFAULT_PROFILE_UUID, LEGACY_DEFAULT_VERSION_UUID, content_hash, legacy_default_content
    now=datetime.now(timezone.utc).isoformat();content=legacy_default_content()
    conn.execute("""INSERT OR IGNORE INTO ai_instruction_profile
        (uuid,name,worker_kind,dataset_type,lifecycle_state,is_default,version,created_at,updated_at)
        VALUES (?,?,?,?,'Published',1,1,?,?)""",
        (DEFAULT_PROFILE_UUID,"Curator Album Analysis Default","album_name_analysis","album_analysis",now,now))
    conn.execute("""INSERT OR IGNORE INTO ai_instruction_profile_version
        (uuid,profile_uuid,version,global_instruction,dataset_instruction,vision_prompt_template,
         writer_prompt_template,output_language,naming_policy_json,vision_schema_version,writer_schema_version,
         validator_policy_version,instruction_transport,composition_version,content_hash,created_at)
        VALUES (?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(LEGACY_DEFAULT_VERSION_UUID,DEFAULT_PROFILE_UUID,
        content["global_instruction"],content["dataset_instruction"],content["vision_prompt_template"],
        content["writer_prompt_template"],content["output_language"],json.dumps(content["naming_policy"],sort_keys=True),
        content["vision_schema_version"],content["writer_schema_version"],content["validator_policy_version"],
        content["instruction_transport"],content["composition_version"],content_hash(content),now))
    conn.execute("""UPDATE ai_model_configuration SET instruction_profile_version_uuid=?
        WHERE instruction_profile_version_uuid IS NULL""",(LEGACY_DEFAULT_VERSION_UUID,))


def _apply_0019(conn: sqlite3.Connection, source: Path) -> None:
    """Publish the sensual editorial Writer prompt as immutable Profile v2."""
    _apply_sql(conn, source)
    from apps.ai_instruction_profile import DEFAULT_PROFILE_UUID, DEFAULT_VERSION_UUID, content_hash, default_content
    now=datetime.now(timezone.utc).isoformat();content=default_content()
    conn.execute("""INSERT OR IGNORE INTO ai_instruction_profile_version
        (uuid,profile_uuid,version,global_instruction,dataset_instruction,vision_prompt_template,
         writer_prompt_template,output_language,naming_policy_json,vision_schema_version,writer_schema_version,
         validator_policy_version,instruction_transport,composition_version,content_hash,created_at)
        VALUES (?,?,2,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(DEFAULT_VERSION_UUID,DEFAULT_PROFILE_UUID,
        content["global_instruction"],content["dataset_instruction"],content["vision_prompt_template"],
        content["writer_prompt_template"],content["output_language"],json.dumps(content["naming_policy"],sort_keys=True),
        content["vision_schema_version"],content["writer_schema_version"],content["validator_policy_version"],
        content["instruction_transport"],content["composition_version"],content_hash(content),now))
    conn.execute("""UPDATE ai_model_configuration SET instruction_profile_version_uuid=?,version=version+1,updated_at=?
        WHERE instruction_profile_version_uuid IN (?,?)""",
        (DEFAULT_VERSION_UUID,now,DEFAULT_VERSION_UUID,"00000000-0000-4000-8000-000000000101"))
    conn.execute("""UPDATE ai_instruction_profile SET lifecycle_state='Published',is_default=1,updated_at=?
        WHERE uuid=?""",(now,DEFAULT_PROFILE_UUID))


def _recorded(conn: sqlite3.Connection) -> set[str]:
    if not _table_exists(conn, "schema_migration"):
        return set()
    return {row[0] for row in conn.execute("SELECT migration_id FROM schema_migration")}


def migrate(
    database: Path | str = DEFAULT_DATABASE,
    backup_dir: Path | str = DEFAULT_BACKUP_DIR,
) -> MigrationResult:
    """Build or upgrade *database* through every reviewed migration."""
    database = Path(database).expanduser().resolve()
    backup_dir = Path(backup_dir).expanduser().resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    if not database.exists():
        database.touch()

    with closing(sqlite3.connect(database)) as conn:
        recorded = _recorded(conn)
    pending = [source for source in MIGRATION_FILES if source.stem not in recorded]
    if not pending:
        _verify_database(database)
        return MigrationResult(database, None, False, False, ())

    backup = _create_verified_backup(database, backup_dir)
    adopted_remark = False
    applied: list[str] = []
    try:
        with closing(sqlite3.connect(database)) as conn, conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migration ("
                "migration_id TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            for source in pending:
                migration_id = source.stem
                if migration_id == MIGRATION_ID:
                    adopted_remark = _apply_0001(conn, source)
                elif migration_id == "0002_archive_historical_workspace_album":
                    _apply_0002(conn)
                elif migration_id == "0015_ui_device_enrollment":
                    _apply_0015(conn)
                elif migration_id == "0016_capability_aware_work_claim":
                    _apply_0016(conn)
                elif migration_id == "0017_ai_instruction_profile":
                    _apply_0017(conn, source)
                elif migration_id == "0019_sensual_editorial_writer_profile":
                    _apply_0019(conn, source)
                else:
                    _apply_sql(conn, source)
                _verify_connection(conn)
                conn.execute(
                    "INSERT INTO schema_migration(migration_id,applied_at) VALUES (?,?)",
                    (migration_id, datetime.now(timezone.utc).isoformat()),
                )
                applied.append(migration_id)
            conn.commit()
    except Exception:
        raise
    _verify_database(database)
    return MigrationResult(database, backup, True, adopted_remark, tuple(applied))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply all Curator SQLite migrations.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    args = parser.parse_args(argv)
    try:
        result = migrate(args.database, args.backup_dir)
    except (MigrationError, sqlite3.DatabaseError) as exc:
        parser.error(str(exc))
    if not result.applied:
        print("already current")
        return 0
    print("applied: " + ", ".join(result.applied_migrations))
    print(f"verified backup: {result.backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
