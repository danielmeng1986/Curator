#!/usr/bin/env python3
"""Migrate Curator SQLite schema to DatabaseModel v0.1.

Scope:
- Update `model`, `studio`, `album` tables to the latest structure.
- Add new `photo`, `album_model` tables.
- Fill missing UUIDs for existing rows, especially `model` and `studio`.

Notes:
- Default mode is dry-run (transaction rollback).
- Use `--apply` to persist changes.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"


@dataclass
class MigrationStats:
    model_uuid_filled: int = 0
    studio_uuid_filled: int = 0
    album_uuid_filled: int = 0


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def get_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    if not table_exists(conn, table_name):
        return set()
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def create_status_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS status (
            id INTEGER PRIMARY KEY,
            name TEXT,
            description TEXT
        )
        """
    )


def create_model_table(conn: sqlite3.Connection, table_name: str = "model") -> None:
    conn.execute(
        f"""
        CREATE TABLE {table_name} (
            id INTEGER PRIMARY KEY,
            uuid TEXT NOT NULL UNIQUE,
            display_name TEXT,
            primary_name TEXT,
            description TEXT,
            country TEXT,
            ethnicity TEXT,
            eye_color TEXT,
            natural_hair_color TEXT,
            created_at DATETIME,
            updated_at DATETIME
        )
        """
    )


def create_studio_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS studio (
            id INTEGER PRIMARY KEY,
            uuid TEXT UNIQUE,
            name TEXT,
            website TEXT,
            description TEXT,
            media_scope TEXT,
            created_at DATETIME,
            updated_at DATETIME
        )
        """
    )


def create_album_table(conn: sqlite3.Connection, table_name: str = "album") -> None:
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
            current_path TEXT,
            expected_path TEXT,
            created_at DATETIME,
            updated_at DATETIME
        )
        """
    )


def create_photo_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS photo (
            id INTEGER PRIMARY KEY,
            uuid TEXT NOT NULL UNIQUE,
            album_id INTEGER REFERENCES album(id),
            filename TEXT,
            relative_path TEXT,
            hash TEXT,
            width INTEGER,
            height INTEGER,
            capture_time DATETIME,
            created_at DATETIME
        )
        """
    )


def create_album_model_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS album_model (
            id INTEGER PRIMARY KEY,
            album_id INTEGER REFERENCES album(id),
            model_id INTEGER REFERENCES model(id),
            age_when_shot INTEGER,
            role TEXT,
            remarks TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_album_model_album_model
            ON album_model(album_id, model_id)
        """
    )


def migrate_model(conn: sqlite3.Connection, stats: MigrationStats, now_text: str) -> None:
    if not table_exists(conn, "model"):
        create_model_table(conn)
        return

    old_cols = get_columns(conn, "model")
    rows = conn.execute("SELECT * FROM model ORDER BY id").fetchall()
    col_names = [d[0] for d in conn.execute("SELECT * FROM model LIMIT 0").description]

    conn.execute("DROP TABLE IF EXISTS model_new")
    create_model_table(conn, "model_new")

    existing_uuids: set[str] = set()

    def col(row: sqlite3.Row, name: str):
        if name not in old_cols:
            return None
        return row[col_names.index(name)]

    for row in rows:
        original_uuid = col(row, "uuid")
        final_uuid = (original_uuid or "").strip() if isinstance(original_uuid, str) else None
        if not final_uuid:
            final_uuid = str(uuid.uuid4())
            while final_uuid in existing_uuids:
                final_uuid = str(uuid.uuid4())
            stats.model_uuid_filled += 1
        existing_uuids.add(final_uuid)

        primary_name = col(row, "primary_name")
        if not primary_name:
            primary_name = col(row, "name")

        display_name = col(row, "display_name")
        if not display_name:
            display_name = primary_name

        created_at = col(row, "created_at") or now_text
        updated_at = col(row, "updated_at") or now_text

        conn.execute(
            """
            INSERT INTO model_new (
                id, uuid, display_name, primary_name, description,
                country, ethnicity, eye_color, natural_hair_color,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                col(row, "id"),
                final_uuid,
                display_name,
                primary_name,
                col(row, "description"),
                col(row, "country"),
                col(row, "ethnicity"),
                col(row, "eye_color"),
                col(row, "natural_hair_color"),
                created_at,
                updated_at,
            ),
        )

    conn.execute("DROP TABLE model")
    conn.execute("ALTER TABLE model_new RENAME TO model")


def migrate_studio(conn: sqlite3.Connection, stats: MigrationStats, now_text: str) -> None:
    create_studio_table(conn)

    cols = get_columns(conn, "studio")
    for ddl in (
        "ALTER TABLE studio ADD COLUMN uuid TEXT",
        "ALTER TABLE studio ADD COLUMN website TEXT",
        "ALTER TABLE studio ADD COLUMN description TEXT",
        "ALTER TABLE studio ADD COLUMN created_at DATETIME",
        "ALTER TABLE studio ADD COLUMN updated_at DATETIME",
    ):
        col_name = ddl.split("ADD COLUMN", 1)[1].strip().split()[0]
        if col_name not in cols:
            conn.execute(ddl)
            cols.add(col_name)

    rows = conn.execute("SELECT id, uuid, created_at, updated_at FROM studio ORDER BY id").fetchall()
    existing_uuids = {
        (r[1] or "").strip()
        for r in rows
        if isinstance(r[1], str) and (r[1] or "").strip()
    }

    for row_id, row_uuid, created_at, updated_at in rows:
        next_uuid = (row_uuid or "").strip() if isinstance(row_uuid, str) else ""
        need_update = False

        if not next_uuid:
            next_uuid = str(uuid.uuid4())
            while next_uuid in existing_uuids:
                next_uuid = str(uuid.uuid4())
            existing_uuids.add(next_uuid)
            stats.studio_uuid_filled += 1
            need_update = True

        if not created_at:
            created_at = now_text
            need_update = True

        if not updated_at:
            updated_at = now_text
            need_update = True

        if need_update:
            conn.execute(
                """
                UPDATE studio
                SET uuid = ?, created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_uuid, created_at, updated_at, row_id),
            )

    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_studio_uuid ON studio(uuid)")


def migrate_album(conn: sqlite3.Connection, stats: MigrationStats, now_text: str) -> None:
    if not table_exists(conn, "album"):
        create_album_table(conn)
        return

    old_cols = get_columns(conn, "album")
    rows = conn.execute("SELECT * FROM album ORDER BY id").fetchall()
    col_names = [d[0] for d in conn.execute("SELECT * FROM album LIMIT 0").description]

    conn.execute("DROP TABLE IF EXISTS album_new")
    create_album_table(conn, "album_new")

    existing_uuids: set[str] = set()

    def col(row: sqlite3.Row, name: str):
        if name not in old_cols:
            return None
        return row[col_names.index(name)]

    for row in rows:
        original_uuid = col(row, "uuid")
        final_uuid = (original_uuid or "").strip() if isinstance(original_uuid, str) else None
        if not final_uuid:
            final_uuid = str(uuid.uuid4())
            while final_uuid in existing_uuids:
                final_uuid = str(uuid.uuid4())
            stats.album_uuid_filled += 1
        existing_uuids.add(final_uuid)

        title = col(row, "title")
        if not title:
            title = col(row, "name")

        created_at = col(row, "created_at") or now_text
        updated_at = col(row, "updated_at") or now_text

        conn.execute(
            """
            INSERT INTO album_new (
                id, uuid, studio_id, status_id, title, description, scene, location,
                capture_date, publish_date, rating, current_path, expected_path,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                col(row, "id"),
                final_uuid,
                col(row, "studio_id"),
                col(row, "status_id"),
                title,
                col(row, "description"),
                col(row, "scene"),
                col(row, "location"),
                col(row, "capture_date"),
                col(row, "publish_date"),
                col(row, "rating"),
                col(row, "current_path"),
                col(row, "expected_path"),
                created_at,
                updated_at,
            ),
        )

    conn.execute("DROP TABLE album")
    conn.execute("ALTER TABLE album_new RENAME TO album")


def summarize(conn: sqlite3.Connection) -> str:
    lines: list[str] = []
    for table in ("model", "studio", "status", "album", "photo", "album_model"):
        if not table_exists(conn, table):
            lines.append(f"- {table}: <missing>")
            continue
        cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        lines.append(f"- {table}: rows={count}, columns={', '.join(cols)}")
    return "\n".join(lines)


def backup_db(db_path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}.backup_before_model_v01_{ts}{db_path.suffix}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate Curator DB schema to DatabaseModel v0.1")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})")
    parser.add_argument("--apply", action="store_true", help="Persist migration changes")
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not create database backup before apply",
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
    now_text = now_iso()

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")

        create_status_table(conn)
        migrate_model(conn, stats, now_text)
        migrate_studio(conn, stats, now_text)
        migrate_album(conn, stats, now_text)
        create_photo_table(conn)
        create_album_model_table(conn)

        if args.apply:
            conn.commit()
            action = "APPLIED"
        else:
            conn.rollback()
            action = "DRY-RUN (ROLLED BACK)"

        print(f"[INFO] Migration status: {action}")
        print("[INFO] UUID fill summary:")
        print(f"  model.uuid filled: {stats.model_uuid_filled}")
        print(f"  studio.uuid filled: {stats.studio_uuid_filled}")
        print(f"  album.uuid filled: {stats.album_uuid_filled}")

        # Reopen for summary if dry-run rolled back.
        with sqlite3.connect(db_path) as read_conn:
            print("[INFO] Current schema summary:")
            print(summarize(read_conn))

        return 0
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        print(f"ERROR: migration failed: {exc}")
        return 1
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
