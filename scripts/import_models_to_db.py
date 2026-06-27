#!/usr/bin/env python3
"""Scan archive model folders and import model names into SQLite."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable, List, Set

DEFAULT_ARCHIVE = Path("/Volumes/NAS-RAID5/RAID/Prime_Media/Archive")
DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
LETTER_FOLDERS = {chr(i) for i in range(ord("A"), ord("Z") + 1)}


def is_ignored(path: Path) -> bool:
    return path.name.startswith(".")


def collect_model_names(archive_root: Path) -> List[str]:
    if not archive_root.exists() or not archive_root.is_dir():
        raise FileNotFoundError(f"Archive path does not exist or is not a folder: {archive_root}")

    names: Set[str] = set()
    for letter_dir in sorted(p for p in archive_root.iterdir() if p.is_dir() and not is_ignored(p)):
        if letter_dir.name not in LETTER_FOLDERS or len(letter_dir.name) != 1:
            continue

        for model_dir in sorted(p for p in letter_dir.iterdir() if p.is_dir() and not is_ignored(p)):
            model_name = model_dir.name.strip()
            if model_name:
                names.add(model_name)

    return sorted(names)


def ensure_model_table(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS model (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """
        )
        conn.commit()


def insert_models(db_path: Path, model_names: Iterable[str], replace: bool = False) -> tuple[int, int]:
    with sqlite3.connect(db_path) as conn:
        conn.execute("BEGIN")

        if replace:
            conn.execute("DELETE FROM model")
            to_insert = sorted(set(model_names))
        else:
            existing = {row[0] for row in conn.execute("SELECT name FROM model")}
            to_insert = sorted(set(model_names) - existing)

        if to_insert:
            conn.executemany("INSERT INTO model(name) VALUES (?)", ((name,) for name in to_insert))

        total = conn.execute("SELECT COUNT(*) FROM model").fetchone()[0]
        conn.commit()
        return len(to_insert), total


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan Archive model folders and import names into the SQLite model table."
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
        help="Replace existing model table rows before inserting scanned model names.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_root = Path(args.archive).expanduser().resolve()
    db_path = Path(args.db).expanduser().resolve()

    model_names = collect_model_names(archive_root)
    if not model_names:
        print("[WARN] No model folders found under A-Z letter directories.")
        return 1

    db_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_model_table(db_path)
    inserted, total = insert_models(db_path, model_names, replace=args.replace)

    print(f"[INFO] Scanned model names: {len(model_names)}")
    print(f"[INFO] Inserted into database: {inserted}")
    print(f"[INFO] Total rows in model table: {total}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
