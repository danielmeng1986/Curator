#!/usr/bin/env python3
"""Migrate Curator SQLite schema to DatabaseModel v0.2.

Scope:
- Replace permanent Album path columns ``current_path`` and ``expected_path``
  with one canonical ``path`` column.
- Add self-referencing ``album_relation`` table.
- Migrate logical grouping data from ``workspace_album.belongs_to_album_id``
  into ``album_relation`` rows with ``relation_type = 'BELONGS_TO'``.
- Leave ``workspace_album`` unchanged (its ``current_path``,
  ``expected_path``, and ``belongs_to_album_id`` are temporary-workspace
  fields and are preserved).

Default mode is dry-run (transaction rollback).
Use ``--apply`` to persist changes.

Conflict handling:
  If any permanent Album row has both ``current_path`` and ``expected_path``
  set to different (non-equal) values the migration STOPS and reports those
  rows.  Pass ``--force-path=current`` or ``--force-path=expected`` only after
  a curator has inspected the conflicts and decided which value to keep.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ConflictRow:
    album_id: int
    uuid: str
    title: str | None
    current_path: str
    expected_path: str


@dataclass
class SkippedRelation:
    ws_id: int
    reason: str
    detail: str = ""


@dataclass
class MigrationStats:
    album_rows_total: int = 0
    album_rows_path_set: int = 0
    album_rows_path_null: int = 0
    album_conflict_rows: list[ConflictRow] = field(default_factory=list)

    relations_total_ws: int = 0
    relations_skipped_null: int = 0
    relations_skipped_self: int = 0
    relations_skipped_perm_self: int = 0
    relations_skipped_invalid: int = 0
    relations_inserted: int = 0
    skipped_invalid_list: list[SkippedRelation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(r[1]) for r in rows}


def get_indexes(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Return index metadata for *table* (excluding auto-generated SQLite indexes)."""
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name = ?",
        (table,),
    ).fetchall()
    return [{"name": r[0], "sql": r[1]} for r in rows if r[1]]  # skip auto-indexes (no sql)


def backup_db(db_path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = db_path.with_name(
        f"{db_path.stem}.backup_before_model_v02_{ts}{db_path.suffix}"
    )
    shutil.copy2(db_path, backup)
    return backup


# ---------------------------------------------------------------------------
# Phase 1: Rebuild album table with path column
# ---------------------------------------------------------------------------

def create_album_v02(conn: sqlite3.Connection, table_name: str = "album") -> None:
    conn.execute(
        f"""
        CREATE TABLE {table_name} (
            id INTEGER PRIMARY KEY,
            uuid TEXT NOT NULL UNIQUE,
            studio_id INTEGER REFERENCES studio(id),
            status_id INTEGER REFERENCES status(id),
            title TEXT,
            description TEXT,
            scene TEXT,
            location TEXT,
            capture_date DATETIME,
            publish_date DATETIME,
            rating INTEGER,
            path TEXT,
            created_at DATETIME,
            updated_at DATETIME
        )
        """
    )


def scan_path_conflicts(
    conn: sqlite3.Connection,
    old_cols: set[str],
) -> list[ConflictRow]:
    """Return rows where current_path and expected_path are both non-null and differ."""
    if "current_path" not in old_cols or "expected_path" not in old_cols:
        return []
    rows = conn.execute(
        """
        SELECT id, uuid, title, current_path, expected_path
        FROM album
        WHERE current_path IS NOT NULL
          AND expected_path IS NOT NULL
          AND current_path <> expected_path
        ORDER BY id
        """
    ).fetchall()
    return [
        ConflictRow(
            album_id=r[0],
            uuid=r[1] or "",
            title=r[2],
            current_path=r[3],
            expected_path=r[4],
        )
        for r in rows
    ]


def choose_path(
    current_path: str | None,
    expected_path: str | None,
    force_path: str | None,
) -> str | None:
    """Return the canonical path value for a single album row.

    ``force_path`` must be ``'current'``, ``'expected'``, or ``None``.
    When ``None``, both values must be equal (enforced earlier by conflict scan).
    """
    if current_path is None and expected_path is None:
        return None
    if force_path == "current":
        return current_path
    if force_path == "expected":
        return expected_path
    # No conflict (enforced by caller): use whichever is non-null.
    return current_path if current_path is not None else expected_path


def migrate_album_table(
    conn: sqlite3.Connection,
    stats: MigrationStats,
    force_path: str | None,
) -> None:
    """Rebuild permanent album table replacing current_path/expected_path with path."""
    if not table_exists(conn, "album"):
        create_album_v02(conn)
        return

    old_cols = get_columns(conn, "album")

    # --- Conflict check ---
    conflicts = scan_path_conflicts(conn, old_cols)
    stats.album_conflict_rows = conflicts

    if conflicts and force_path is None:
        ids = ", ".join(str(c.album_id) for c in conflicts)
        raise ConflictError(
            f"Found {len(conflicts)} album row(s) where current_path and expected_path "
            f"differ (IDs: {ids}). Inspect them and rerun with --force-path=current or "
            f"--force-path=expected after a curator decision."
        )

    # --- Preserve existing indexes (exclude auto-generated) ---
    existing_indexes = get_indexes(conn, "album")

    # --- Read all rows ---
    col_names = [
        d[0] for d in conn.execute("SELECT * FROM album LIMIT 0").description
    ]
    rows = conn.execute("SELECT * FROM album ORDER BY id").fetchall()
    stats.album_rows_total = len(rows)

    def col(row: tuple, name: str):
        if name not in old_cols:
            return None
        return row[col_names.index(name)]

    # --- Build new table ---
    conn.execute("DROP TABLE IF EXISTS album_v02_new")
    create_album_v02(conn, "album_v02_new")

    for row in rows:
        cp = col(row, "current_path")
        ep = col(row, "expected_path")
        path = choose_path(cp, ep, force_path)

        if path is not None:
            stats.album_rows_path_set += 1
        else:
            stats.album_rows_path_null += 1

        conn.execute(
            """
            INSERT INTO album_v02_new (
                id, uuid, studio_id, status_id,
                title, description, scene, location,
                capture_date, publish_date, rating,
                path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                col(row, "id"),
                col(row, "uuid"),
                col(row, "studio_id"),
                col(row, "status_id"),
                col(row, "title"),
                col(row, "description"),
                col(row, "scene"),
                col(row, "location"),
                col(row, "capture_date"),
                col(row, "publish_date"),
                col(row, "rating"),
                path,
                col(row, "created_at"),
                col(row, "updated_at"),
            ),
        )

    conn.execute("DROP TABLE album")
    conn.execute("ALTER TABLE album_v02_new RENAME TO album")

    # Recreate preserved indexes
    for idx in existing_indexes:
        try:
            conn.execute(idx["sql"])
        except sqlite3.OperationalError:
            pass  # already exists (idempotent rerun after partial apply)


class ConflictError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Phase 2: Create album_relation table
# ---------------------------------------------------------------------------

def create_album_relation_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS album_relation (
            id INTEGER PRIMARY KEY,
            album_id INTEGER NOT NULL REFERENCES album(id),
            related_album_id INTEGER NOT NULL REFERENCES album(id),
            relation_type TEXT NOT NULL,
            remarks TEXT,
            CHECK (album_id <> related_album_id),
            UNIQUE (album_id, related_album_id, relation_type)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_album_relation_album_id
            ON album_relation(album_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_album_relation_related_album_id
            ON album_relation(related_album_id)
        """
    )


# ---------------------------------------------------------------------------
# Phase 3: Migrate workspace_album.belongs_to_album_id → album_relation
# ---------------------------------------------------------------------------

def migrate_album_relations(
    conn: sqlite3.Connection,
    stats: MigrationStats,
) -> None:
    """Insert BELONGS_TO rows into album_relation from workspace_album."""
    wa_cols = get_columns(conn, "workspace_album")
    if "belongs_to_album_id" not in wa_cols:
        print("[WARN] workspace_album has no belongs_to_album_id column; skipping relation migration.")
        return
    if "album_id" not in wa_cols:
        print("[WARN] workspace_album has no album_id column; skipping relation migration.")
        return

    rows = conn.execute(
        "SELECT id, belongs_to_album_id, album_id FROM workspace_album ORDER BY id"
    ).fetchall()
    stats.relations_total_ws = len(rows)

    for ws_id, belongs_to_ws_id, source_perm_id in rows:
        # Step 1: Skip null
        if belongs_to_ws_id is None:
            stats.relations_skipped_null += 1
            continue

        # Step 2: Skip self-reference
        if belongs_to_ws_id == ws_id:
            stats.relations_skipped_self += 1
            continue

        # Step 3: Resolve source permanent album
        if source_perm_id is None:
            stats.relations_skipped_invalid += 1
            stats.skipped_invalid_list.append(
                SkippedRelation(ws_id, "source_album_id is null")
            )
            continue

        # Step 4: Resolve target workspace row → target permanent album
        target_row = conn.execute(
            "SELECT id, album_id FROM workspace_album WHERE id = ?",
            (belongs_to_ws_id,),
        ).fetchone()

        if target_row is None:
            stats.relations_skipped_invalid += 1
            stats.skipped_invalid_list.append(
                SkippedRelation(
                    ws_id,
                    "target workspace row not found",
                    f"belongs_to_album_id={belongs_to_ws_id}",
                )
            )
            continue

        target_perm_id = target_row[1]
        if target_perm_id is None:
            stats.relations_skipped_invalid += 1
            stats.skipped_invalid_list.append(
                SkippedRelation(
                    ws_id,
                    "target workspace row has null album_id",
                    f"target_ws_id={target_row[0]}",
                )
            )
            continue

        # Step 5: Skip permanent self-relation
        if source_perm_id == target_perm_id:
            stats.relations_skipped_perm_self += 1
            continue

        # Step 6: Conflict-safe insert (INSERT OR IGNORE)
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO album_relation
                (album_id, related_album_id, relation_type, remarks)
            VALUES (?, ?, 'BELONGS_TO', NULL)
            """,
            (source_perm_id, target_perm_id),
        )
        if cur.rowcount:
            stats.relations_inserted += 1


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(conn: sqlite3.Connection) -> list[str]:
    """Run post-migration checks. Returns list of warning strings."""
    warnings: list[str] = []

    # 1. album must have path, must not have current_path/expected_path
    album_cols = get_columns(conn, "album")
    if "path" not in album_cols:
        warnings.append("FAIL: album.path column missing")
    if "current_path" in album_cols:
        warnings.append("FAIL: album.current_path still present")
    if "expected_path" in album_cols:
        warnings.append("FAIL: album.expected_path still present")

    # 2. workspace_album retains its fields
    wa_cols = get_columns(conn, "workspace_album")
    for col in ("current_path", "expected_path", "belongs_to_album_id"):
        if col not in wa_cols:
            warnings.append(f"FAIL: workspace_album.{col} missing")

    # 3. No self-relations in album_relation
    self_count = conn.execute(
        "SELECT COUNT(*) FROM album_relation WHERE album_id = related_album_id"
    ).fetchone()[0]
    if self_count:
        warnings.append(f"FAIL: {self_count} self-relations found in album_relation")

    # 4. No duplicate tuples
    dup_count = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT album_id, related_album_id, relation_type, COUNT(*) AS cnt
            FROM album_relation
            GROUP BY album_id, related_album_id, relation_type
            HAVING cnt > 1
        )
        """
    ).fetchone()[0]
    if dup_count:
        warnings.append(f"FAIL: {dup_count} duplicate tuples in album_relation")

    # 5. FK check
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_violations:
        for v in fk_violations:
            warnings.append(f"FAIL: FK violation: {v}")

    return warnings


def print_summary(stats: MigrationStats, warnings: list[str]) -> None:
    print("\n[INFO] === Migration Summary ===")
    print(f"  album rows total:         {stats.album_rows_total}")
    print(f"  album rows path set:      {stats.album_rows_path_set}")
    print(f"  album rows path null:     {stats.album_rows_path_null}")
    print(f"  album conflict rows:      {len(stats.album_conflict_rows)}")
    if stats.album_conflict_rows:
        for c in stats.album_conflict_rows:
            print(
                f"    id={c.album_id} uuid={c.uuid!r} title={c.title!r}"
                f"\n      current_path={c.current_path!r}"
                f"\n      expected_path={c.expected_path!r}"
            )

    print(f"  workspace_album rows:     {stats.relations_total_ws}")
    print(f"  relations skipped (null): {stats.relations_skipped_null}")
    print(f"  relations skipped (self): {stats.relations_skipped_self}")
    print(f"  relations skipped (perm self): {stats.relations_skipped_perm_self}")
    print(f"  relations skipped (invalid): {stats.relations_skipped_invalid}")
    if stats.skipped_invalid_list:
        for s in stats.skipped_invalid_list:
            print(f"    ws_id={s.ws_id}: {s.reason} {s.detail}")
    print(f"  album_relation inserted:  {stats.relations_inserted}")

    if warnings:
        print("\n[WARN] Post-migration check issues:")
        for w in warnings:
            print(f"  {w}")
    else:
        print("\n[INFO] All post-migration checks passed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate Curator DB schema to DatabaseModel v0.2"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite DB path (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist migration changes (default: dry-run)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create database backup before apply",
    )
    parser.add_argument(
        "--force-path",
        choices=["current", "expected"],
        default=None,
        help=(
            "Curator-approved resolution for albums where current_path and expected_path "
            "differ. Specify 'current' to keep current_path or 'expected' to keep "
            "expected_path for conflicting rows. Requires curator review first."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = args.db.expanduser().resolve()

    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}")
        return 1

    if args.apply and not args.no_backup:
        backup_path = backup_db(db_path)
        print(f"[INFO] Backup created: {backup_path}")

    stats = MigrationStats()

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")

        # Phase 1: Rebuild album table
        migrate_album_table(conn, stats, args.force_path)

        # Phase 2: Create album_relation
        create_album_relation_table(conn)

        # Phase 3: Migrate workspace relations
        migrate_album_relations(conn, stats)

        # Phase 4: Verify
        conn.execute("PRAGMA foreign_keys = ON")
        warnings = verify(conn)

        if args.apply:
            conn.commit()
            action = "APPLIED"
        else:
            conn.rollback()
            action = "DRY-RUN (ROLLED BACK)"

        print(f"[INFO] Migration status: {action}")
        print_summary(stats, warnings)

        if warnings and args.apply:
            print("\n[ERROR] Migration applied but verification found issues.")
            return 1

        return 0

    except ConflictError as exc:
        conn.rollback()
        print(f"\n[ERROR] Conflicting album paths detected — migration aborted.\n{exc}")
        print("\nConflicting albums:")
        for c in stats.album_conflict_rows:
            print(
                f"  id={c.album_id}, uuid={c.uuid!r}, title={c.title!r}"
                f"\n    current_path  = {c.current_path!r}"
                f"\n    expected_path = {c.expected_path!r}"
            )
        return 2

    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        print(f"ERROR: migration failed: {exc}")
        raise

    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
