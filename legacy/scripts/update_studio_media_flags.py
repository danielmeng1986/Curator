#!/usr/bin/env python3
"""Backfill studio media scope flag (p / v / p+v) into existing studio table."""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, Set

DEFAULT_ARCHIVE = Path("/Volumes/NAS-RAID5/RAID/Prime_Media/Archive")
DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
DEFAULT_TABLE = "studio"
DEFAULT_COLUMN = "media_scope"
LETTER_FOLDERS = {chr(i) for i in range(ord("A"), ord("Z") + 1)}
MEDIA_DIRS = {"p", "v"}
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_ignored(path: Path) -> bool:
    return path.name.startswith(".")


def validate_identifier(identifier: str, kind: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Invalid {kind}: {identifier}")
    return identifier


def collect_studio_media_scope(archive_root: Path) -> tuple[Dict[str, Set[str]], int]:
    if not archive_root.exists() or not archive_root.is_dir():
        raise FileNotFoundError(f"Archive path does not exist or is not a folder: {archive_root}")

    studio_media: Dict[str, Set[str]] = {}
    skipped_invalid = 0

    for letter_dir in sorted(p for p in archive_root.iterdir() if p.is_dir() and not is_ignored(p)):
        if letter_dir.name not in LETTER_FOLDERS or len(letter_dir.name) != 1:
            continue

        for model_dir in sorted(p for p in letter_dir.iterdir() if p.is_dir() and not is_ignored(p)):
            model_name = model_dir.name.strip()
            if not model_name:
                continue

            for media_dir in sorted(
                p for p in model_dir.iterdir() if p.is_dir() and not is_ignored(p) and p.name in MEDIA_DIRS
            ):
                media_flag = media_dir.name
                for studio_dir in sorted(p for p in media_dir.iterdir() if p.is_dir() and not is_ignored(p)):
                    studio_folder_name = studio_dir.name.strip()
                    expected_prefix = f"{model_name} in "
                    if studio_folder_name.startswith(expected_prefix):
                        studio_name = studio_folder_name[len(expected_prefix) :].strip()
                    else:
                        studio_name = studio_folder_name
                    if not studio_name:
                        skipped_invalid += 1
                        continue

                    studio_media.setdefault(studio_name, set()).add(media_flag)

    return studio_media, skipped_invalid


def ensure_column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    existing_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column in existing_columns:
        return False

    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
    return True


def scope_value(media_flags: Iterable[str]) -> str | None:
    flags = set(media_flags)
    if flags == {"p"}:
        return "p"
    if flags == {"v"}:
        return "v"
    if flags == {"p", "v"}:
        return "p+v"
    return None


def update_studio_scope(
    db_path: Path,
    table: str,
    column: str,
    studio_media: Dict[str, Set[str]],
    dry_run: bool,
) -> tuple[int, int, int, int, bool]:
    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN")

        added_column = ensure_column_exists(conn, table, column)
        studio_names = [row[0] for row in conn.execute(f"SELECT name FROM {table}")]

        counts = {"p": 0, "v": 0, "p+v": 0, "none": 0}
        for studio_name in studio_names:
            value = scope_value(studio_media.get(studio_name, set()))
            if value is None:
                counts["none"] += 1
            else:
                counts[value] += 1
            conn.execute(f"UPDATE {table} SET {column} = ? WHERE name = ?", (value, studio_name))

        if dry_run:
            conn.rollback()
        else:
            conn.commit()

        total = len(studio_names)
        updated = counts["p"] + counts["v"] + counts["p+v"]
        return total, updated, counts["none"], counts["p+v"], added_column


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill studio table with media scope flag based on Archive p/v folders."
    )
    parser.add_argument(
        "--archive",
        default=str(DEFAULT_ARCHIVE),
        help=f"Archive root path (default: {DEFAULT_ARCHIVE})",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"SQLite DB file path (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--table",
        default=DEFAULT_TABLE,
        help=f"Table name (default: {DEFAULT_TABLE})",
    )
    parser.add_argument(
        "--column",
        default=DEFAULT_COLUMN,
        help=f"Target column name for media scope (default: {DEFAULT_COLUMN})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and calculate updates but rollback database changes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    archive_root = Path(args.archive).expanduser().resolve()
    db_path = Path(args.db).expanduser().resolve()
    table = validate_identifier(args.table, "table name")
    column = validate_identifier(args.column, "column name")

    if not db_path.exists():
        raise FileNotFoundError(f"Database file does not exist: {db_path}")

    studio_media, skipped_invalid = collect_studio_media_scope(archive_root)
    total, updated, no_match, both, added_column = update_studio_scope(
        db_path=db_path,
        table=table,
        column=column,
        studio_media=studio_media,
        dry_run=args.dry_run,
    )

    mode = "DRY RUN" if args.dry_run else "APPLY"
    print(f"[INFO] Mode: {mode}")
    print(f"[INFO] Database file: {db_path}")
    print(f"[INFO] Target: {table}.{column}")
    print(f"[INFO] Added column: {'yes' if added_column else 'no (already exists)'}")
    print(f"[INFO] Distinct studios found in archive: {len(studio_media)}")
    print(f"[INFO] Studio rows processed: {total}")
    print(f"[INFO] Rows matched with p/v or p+v: {updated}")
    print(f"[INFO] Rows with no archive match: {no_match}")
    print(f"[INFO] Rows marked as p+v: {both}")
    if skipped_invalid:
        print(f"[INFO] Skipped invalid studio folders: {skipped_invalid}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
