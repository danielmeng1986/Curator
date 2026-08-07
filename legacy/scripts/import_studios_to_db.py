#!/usr/bin/env python3
"""Scan archive studio folders and import studio names into SQLite."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable, List, Set, Tuple

DEFAULT_ARCHIVE = Path("/Volumes/NAS-RAID5/RAID/Prime_Media/Archive")
DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
LETTER_FOLDERS = {chr(i) for i in range(ord("A"), ord("Z") + 1)}
MEDIA_DIRS = {"p", "v"}


def is_ignored(path: Path) -> bool:
    return path.name.startswith(".")


def collect_studio_names(archive_root: Path) -> Tuple[List[str], int]:
    if not archive_root.exists() or not archive_root.is_dir():
        raise FileNotFoundError(f"Archive path does not exist or is not a folder: {archive_root}")

    studio_names: Set[str] = set()
    skipped_invalid = 0

    for letter_dir in sorted(p for p in archive_root.iterdir() if p.is_dir() and not is_ignored(p)):
        if letter_dir.name not in LETTER_FOLDERS or len(letter_dir.name) != 1:
            continue

        for model_dir in sorted(p for p in letter_dir.iterdir() if p.is_dir() and not is_ignored(p)):
            model_name = model_dir.name.strip()
            if not model_name:
                continue

            expected_prefix = f"{model_name} in "
            for media_dir in sorted(
                p for p in model_dir.iterdir() if p.is_dir() and not is_ignored(p) and p.name in MEDIA_DIRS
            ):
                for studio_dir in sorted(p for p in media_dir.iterdir() if p.is_dir() and not is_ignored(p)):
                    studio_folder_name = studio_dir.name.strip()
                    if not studio_folder_name.startswith(expected_prefix):
                        skipped_invalid += 1
                        continue

                    studio_name = studio_folder_name[len(expected_prefix) :].strip()
                    if not studio_name:
                        skipped_invalid += 1
                        continue

                    studio_names.add(studio_name)

    return sorted(studio_names), skipped_invalid


def ensure_studio_table(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS studio (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        conn.commit()


def insert_studios(db_path: Path, studio_names: Iterable[str], replace: bool = False) -> tuple[int, int]:
    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN")

        if replace:
            conn.execute("DELETE FROM studio")
            to_insert = sorted(set(studio_names))
        else:
            existing = {row[0] for row in conn.execute("SELECT name FROM studio")}
            to_insert = sorted(set(studio_names) - existing)

        if to_insert:
            conn.executemany("INSERT INTO studio(name) VALUES (?)", ((name,) for name in to_insert))

        total = conn.execute("SELECT COUNT(*) FROM studio").fetchone()[0]
        conn.commit()
        return len(to_insert), total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan Archive studio folders and import distinct studio names into SQLite studio table."
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
        "--replace",
        action="store_true",
        help="Replace existing studio table rows before inserting scanned studio names.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_root = Path(args.archive).expanduser().resolve()
    db_path = Path(args.db).expanduser().resolve()

    studio_names, skipped_invalid = collect_studio_names(archive_root)
    if not studio_names:
        print("[WARN] No valid studio folders found under model/p and model/v directories.")
        return 1

    db_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_studio_table(db_path)
    inserted, total = insert_studios(db_path, studio_names, replace=args.replace)

    print(f"[INFO] Database file: {db_path}")
    print(f"[INFO] Scanned distinct studio names: {len(studio_names)}")
    print(f"[INFO] Inserted into database: {inserted}")
    print(f"[INFO] Total rows in studio table: {total}")
    if skipped_invalid:
        print(f"[INFO] Skipped invalid studio folders: {skipped_invalid}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
