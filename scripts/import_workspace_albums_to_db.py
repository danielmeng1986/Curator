#!/usr/bin/env python3
"""Scan album folders under Archive/*/*/p/* and import them into workspace_album.

Rules:
- Scan only image album folders under p/.
- current_path is the archive-relative album path.
- expected_path is set to current_path for album folders that already exist at the
    renamed target path recorded in the rename logs.
- Matched albums are marked RENAMED (status_id=3).
- Unmatched albums are marked WAIT_MANUAL (status_id=1).
- additional_models is left empty.
- remark stores a short note for unmatched or suspicious entries.

The script is idempotent by default: it rebuilds workspace_album on each run.
Use --no-replace to append only new rows.
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_ARCHIVE = Path("/Volumes/NAS-RAID5/RAID/Prime_Media/Archive")
DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
LETTER_FOLDERS = {chr(i) for i in range(ord("A"), ord("Z") + 1)}

STATUS_WAIT_MANUAL = 1
STATUS_RENAMED = 3
DEFAULT_RENAME_LOGS = [
    Path(__file__).resolve().parents[1] / "outputs" / "rename_album_folders_apply.log",
    Path(__file__).resolve().parents[1] / "outputs" / "rename_album_folders_apply_2.log",
]


@dataclass(frozen=True)
class WorkspaceAlbumRow:
    current_path: str
    expected_path: str | None
    primary_model: str
    studio_name: str
    album_name: str
    additional_models: str | None
    status_id: int
    remark: str | None


def is_ignored(path: Path) -> bool:
    return path.name.startswith(".")


def rel_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def load_renamed_targets(log_paths: Iterable[Path], archive_root: Path) -> set[str]:
    """Load successful rename targets from prior rename logs.

    Each rename entry is logged as a source line followed by a target line that
    starts with '    -> '. We collect the target paths because those are the
    normalized folders that should be marked RENAMED in workspace_album.
    """
    targets: set[str] = set()

    for log_path in log_paths:
        if not log_path.exists() or not log_path.is_file():
            continue

        with log_path.open("r", encoding="utf-8") as handle:
            lines = [line.rstrip("\n") for line in handle]

        for index, line in enumerate(lines[:-1]):
            if not line.startswith("  ") or line.startswith("    -> ") or line.startswith("    !! "):
                continue

            next_line = lines[index + 1]
            if not next_line.startswith("    -> "):
                continue

            target_abs = next_line[len("    -> ") :].strip()
            if not target_abs:
                continue

            target_path = Path(target_abs)
            if target_path.is_absolute():
                try:
                    targets.add(rel_path(target_path, archive_root))
                except ValueError:
                    continue
            else:
                targets.add(target_path.as_posix())

    return targets


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workspace_album (
            id INTEGER PRIMARY KEY,
            current_path TEXT NOT NULL,
            expected_path TEXT,
            primary_model TEXT NOT NULL,
            studio_name TEXT NOT NULL,
            album_name TEXT NOT NULL,
            additional_models TEXT,
            status_id INTEGER REFERENCES status (id),
            remark TEXT
        )
        """
    )

    # Backward-compatible migrations for older local databases.
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(workspace_album)")}
    required_columns = {
        "current_path": "TEXT",
        "expected_path": "TEXT",
        "primary_model": "TEXT",
        "studio_name": "TEXT",
        "album_name": "TEXT",
        "additional_models": "TEXT",
        "status_id": "INTEGER",
        "remark": "TEXT",
    }
    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE workspace_album ADD COLUMN {column_name} {column_type}")


def collect_rows(archive_root: Path, renamed_targets: set[str]) -> list[WorkspaceAlbumRow]:
    if not archive_root.exists() or not archive_root.is_dir():
        raise FileNotFoundError(f"Archive path does not exist or is not a folder: {archive_root}")

    rows: list[WorkspaceAlbumRow] = []

    for letter_dir in sorted(p for p in archive_root.iterdir() if p.is_dir() and not is_ignored(p)):
        if letter_dir.name not in LETTER_FOLDERS or len(letter_dir.name) != 1:
            continue

        for model_dir in sorted(p for p in letter_dir.iterdir() if p.is_dir() and not is_ignored(p)):
            primary_model = model_dir.name.strip()
            if not primary_model:
                continue

            p_dir = model_dir / "p"
            if not p_dir.is_dir():
                continue

            for studio_dir in sorted(p for p in p_dir.iterdir() if p.is_dir() and not is_ignored(p)):
                studio_name = studio_dir.name.strip()
                if not studio_name:
                    continue

                for album_dir in sorted(p for p in studio_dir.iterdir() if p.is_dir() and not is_ignored(p)):
                    album_name = album_dir.name.strip()
                    if not album_name:
                        continue

                    current_path = rel_path(album_dir, archive_root)
                    prefix = f"{primary_model} in "

                    if current_path in renamed_targets:
                        expected_path = current_path
                        status_id = STATUS_RENAMED
                        remark = None
                    else:
                        expected_path = None
                        status_id = STATUS_WAIT_MANUAL
                        if album_name.startswith(prefix):
                            remark = "Still matches '<model_name> in <album_name>' pattern"
                        else:
                            remark = None

                    # Keep the field empty for now, but normalize to NULL in the database.
                    rows.append(
                        WorkspaceAlbumRow(
                            current_path=current_path,
                            expected_path=expected_path,
                            primary_model=primary_model,
                            studio_name=studio_name,
                            album_name=album_name,
                            additional_models=None,
                            status_id=status_id,
                            remark=remark,
                        )
                    )

    return rows


def replace_rows(conn: sqlite3.Connection, rows: Iterable[WorkspaceAlbumRow]) -> None:
    conn.execute("DELETE FROM workspace_album")
    conn.executemany(
        """
        INSERT INTO workspace_album (
            current_path,
            expected_path,
            primary_model,
            studio_name,
            album_name,
            additional_models,
            status_id,
            remark
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.current_path,
                row.expected_path,
                row.primary_model,
                row.studio_name,
                row.album_name,
                row.additional_models,
                row.status_id,
                row.remark,
            )
            for row in rows
        ],
    )


def append_rows(conn: sqlite3.Connection, rows: Iterable[WorkspaceAlbumRow]) -> int:
    existing = {row[0] for row in conn.execute("SELECT current_path FROM workspace_album")}
    pending = [row for row in rows if row.current_path not in existing]
    conn.executemany(
        """
        INSERT INTO workspace_album (
            current_path,
            expected_path,
            primary_model,
            studio_name,
            album_name,
            additional_models,
            status_id,
            remark
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row.current_path,
                row.expected_path,
                row.primary_model,
                row.studio_name,
                row.album_name,
                row.additional_models,
                row.status_id,
                row.remark,
            )
            for row in pending
        ],
    )
    return len(pending)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import album folders into workspace_album.")
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE, help=f"Archive root (default: {DEFAULT_ARCHIVE})")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite database path (default: {DEFAULT_DB})")
    parser.add_argument(
        "--rename-log",
        action="append",
        type=Path,
        help="Rename log file to use when identifying renamed targets. Can be passed multiple times.",
    )
    parser.add_argument(
        "--no-replace",
        action="store_true",
        help="Append only new rows instead of rebuilding workspace_album",
    )
    args = parser.parse_args()

    log_paths = args.rename_log if args.rename_log else DEFAULT_RENAME_LOGS
    renamed_targets = load_renamed_targets(log_paths, args.archive)
    rows = collect_rows(args.archive, renamed_targets)

    with sqlite3.connect(args.db) as conn:
        ensure_schema(conn)
        conn.execute("BEGIN")

        if args.no_replace:
            inserted = append_rows(conn, rows)
        else:
            replace_rows(conn, rows)
            inserted = len(rows)

        conn.commit()

    renamed = sum(1 for row in rows if row.status_id == STATUS_RENAMED)
    manual = sum(1 for row in rows if row.status_id == STATUS_WAIT_MANUAL)

    print(f"Archive: {args.archive}")
    print(f"Database: {args.db}")
    print(f"Rows scanned: {len(rows)}")
    print(f"Rows written: {inserted}")
    print(f"RENAMED: {renamed}")
    print(f"WAIT_MANUAL: {manual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
