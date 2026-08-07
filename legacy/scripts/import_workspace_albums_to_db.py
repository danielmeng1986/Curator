#!/usr/bin/env python3
"""Scan album folders under Archive/*/*/p/* and import them into workspace_album.

Rules:
- Scan only image album folders under p/.
- The scan root may be the Archive root or any nested path under it.
- current_path is always the path relative to the containing Archive root.
- expected_path is set to current_path for album folders that already exist at the
    renamed target path recorded in the rename logs.
- Matched albums are marked RENAMED (status_id=3).
- Unmatched albums are marked WAIT_MANUAL (status_id=1).
- additional_models is left empty.
- remark stores a short note for unmatched or suspicious entries.

The script is idempotent by default: it appends only new rows and skips existing
records by current_path or model/studio/album tuple.

Use --replace to rebuild workspace_album from scan results.
Use --restore-by-id-path to rebuild while recovering status/annotations by
matching old rows with (id + current_path) first, then current_path.
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


@dataclass(frozen=True)
class ExistingWorkspaceAlbumRow:
    id: int
    current_path: str
    expected_path: str | None
    additional_models: str | None
    status_id: int | None
    remark: str | None


def is_ignored(path: Path) -> bool:
    return path.name.startswith(".")


def rel_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def resolve_archive_root(scan_root: Path) -> Path:
    resolved = scan_root.resolve()

    for candidate in (resolved, *resolved.parents):
        if candidate.name == "Archive":
            return candidate

    return resolved


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


def iter_album_dirs(scan_root: Path, archive_root: Path) -> Iterable[tuple[Path, str, str]]:
    stack = [scan_root]

    while stack:
        current = stack.pop()
        if is_ignored(current):
            continue

        rel_parts = current.resolve().relative_to(archive_root.resolve()).parts
        if (
            len(rel_parts) == 5
            and rel_parts[0] in LETTER_FOLDERS
            and len(rel_parts[0]) == 1
            and rel_parts[2] == "p"
        ):
            yield current, rel_parts[1].strip(), rel_parts[3].strip()
            continue

        if len(rel_parts) >= 5:
            continue

        children = sorted(
            (child for child in current.iterdir() if child.is_dir() and not is_ignored(child)),
            reverse=True,
        )
        stack.extend(children)


def collect_rows(scan_root: Path, archive_root: Path, renamed_targets: set[str]) -> list[WorkspaceAlbumRow]:
    if not scan_root.exists() or not scan_root.is_dir():
        raise FileNotFoundError(f"Archive path does not exist or is not a folder: {scan_root}")

    rows: list[WorkspaceAlbumRow] = []

    for album_dir, primary_model, studio_name in sorted(iter_album_dirs(scan_root, archive_root)):
        album_name = album_dir.name.strip()
        if not album_name or not primary_model or not studio_name:
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


def existing_identity(row: WorkspaceAlbumRow) -> tuple[str, str, str]:
    return (
        row.primary_model.casefold(),
        row.studio_name.casefold(),
        row.album_name.casefold(),
    )


def append_rows(conn: sqlite3.Connection, rows: Iterable[WorkspaceAlbumRow]) -> tuple[int, int]:
    existing_paths = {row[0] for row in conn.execute("SELECT current_path FROM workspace_album")}
    existing_identity_keys = {
        (
            row[0].casefold(),
            row[1].casefold(),
            row[2].casefold(),
        )
        for row in conn.execute("SELECT primary_model, studio_name, album_name FROM workspace_album")
    }

    pending: list[WorkspaceAlbumRow] = []
    skipped = 0
    for row in rows:
        if row.current_path in existing_paths or existing_identity(row) in existing_identity_keys:
            skipped += 1
            continue

        pending.append(row)
        existing_paths.add(row.current_path)
        existing_identity_keys.add(existing_identity(row))

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
    return len(pending), skipped


def load_existing_rows(conn: sqlite3.Connection) -> tuple[dict[int, ExistingWorkspaceAlbumRow], dict[str, ExistingWorkspaceAlbumRow]]:
    rows = [
        ExistingWorkspaceAlbumRow(
            id=row[0],
            current_path=row[1],
            expected_path=row[2],
            additional_models=row[3],
            status_id=row[4],
            remark=row[5],
        )
        for row in conn.execute(
            """
            SELECT
                id,
                current_path,
                expected_path,
                additional_models,
                status_id,
                remark
            FROM workspace_album
            """
        )
    ]
    return ({row.id: row for row in rows}, {row.current_path: row for row in rows})


def rebuild_rows_with_restore(
    conn: sqlite3.Connection,
    rows: list[WorkspaceAlbumRow],
) -> tuple[int, int, int]:
    existing_by_id, existing_by_path = load_existing_rows(conn)

    restored_by_id_and_path = 0
    restored_by_path = 0
    rows_to_insert: list[tuple[str, str | None, str, str, str, str | None, int, str | None]] = []

    for row_index, row in enumerate(rows, start=1):
        matched = None
        previous = existing_by_id.get(row_index)
        if previous and previous.current_path == row.current_path:
            matched = previous
            restored_by_id_and_path += 1
        else:
            previous = existing_by_path.get(row.current_path)
            if previous is not None:
                matched = previous
                restored_by_path += 1

        if matched is not None:
            effective_expected_path = matched.expected_path if matched.expected_path else row.expected_path
            effective_additional_models = matched.additional_models
            effective_status_id = matched.status_id if matched.status_id is not None else STATUS_WAIT_MANUAL
            effective_remark = matched.remark if matched.remark else row.remark
        else:
            effective_expected_path = row.expected_path
            effective_additional_models = row.additional_models
            effective_status_id = STATUS_WAIT_MANUAL
            effective_remark = row.remark

        rows_to_insert.append(
            (
                row.current_path,
                effective_expected_path,
                row.primary_model,
                row.studio_name,
                row.album_name,
                effective_additional_models,
                effective_status_id,
                effective_remark,
            )
        )

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
        rows_to_insert,
    )
    return len(rows_to_insert), restored_by_id_and_path, restored_by_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Import album folders into workspace_album.")
    parser.add_argument(
        "--archive",
        type=Path,
        default=DEFAULT_ARCHIVE,
        help=f"Archive root or nested scan path (default: {DEFAULT_ARCHIVE})",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite database path (default: {DEFAULT_DB})")
    parser.add_argument(
        "--rename-log",
        action="append",
        type=Path,
        help="Rename log file to use when identifying renamed targets. Can be passed multiple times.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--replace",
        action="store_true",
        help="Rebuild workspace_album directly from the current scan result",
    )
    mode_group.add_argument(
        "--restore-by-id-path",
        action="store_true",
        help="Rebuild table while restoring existing rows by (id+current_path) then current_path; unmatched rows are WAIT_MANUAL",
    )
    args = parser.parse_args()

    archive_root = resolve_archive_root(args.archive)
    log_paths = args.rename_log if args.rename_log else DEFAULT_RENAME_LOGS
    renamed_targets = load_renamed_targets(log_paths, archive_root)
    rows = collect_rows(args.archive, archive_root, renamed_targets)

    with sqlite3.connect(args.db) as conn:
        ensure_schema(conn)
        conn.execute("BEGIN")

        if args.replace:
            replace_rows(conn, rows)
            inserted = len(rows)
            skipped = 0
            restored_by_id_and_path = 0
            restored_by_path = 0
        elif args.restore_by_id_path:
            inserted, restored_by_id_and_path, restored_by_path = rebuild_rows_with_restore(conn, rows)
            skipped = 0
        else:
            inserted, skipped = append_rows(conn, rows)
            restored_by_id_and_path = 0
            restored_by_path = 0

        conn.commit()

    with sqlite3.connect(args.db) as conn:
        status_counts = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT status_id, COUNT(*) FROM workspace_album GROUP BY status_id"
            )
            if row[0] is not None
        }

    renamed = status_counts.get(STATUS_RENAMED, 0)
    manual = status_counts.get(STATUS_WAIT_MANUAL, 0)
    needs_confirm = status_counts.get(2, 0)

    print(f"Archive: {args.archive}")
    print(f"Database: {args.db}")
    print(f"Rows scanned: {len(rows)}")
    print(f"Rows written: {inserted}")
    if skipped:
        print(f"Rows skipped (already in table): {skipped}")
    if restored_by_id_and_path or restored_by_path:
        print(f"Rows restored by id+path: {restored_by_id_and_path}")
        print(f"Rows restored by current_path: {restored_by_path}")
    print(f"RENAMED: {renamed}")
    print(f"WAIT_MANUAL: {manual}")
    if needs_confirm:
        print(f"NEED_CONFIRM: {needs_confirm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
