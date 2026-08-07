#!/usr/bin/env python3
"""Validate workspace_album paths and reconcile current_path/status_id.

Rules:
- Try to access folder from workspace_album.current_path first.
- If current_path is not accessible, try workspace_album.expected_path.
- If expected_path is accessible but current_path is not, set current_path = expected_path.
- If both paths are not accessible, set status_id = 1 (manual verification).

Default mode is dry-run; use --apply to persist updates.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "database" / "Curator.db"
DEFAULT_APP_CONFIG = REPO_ROOT / "workspace" / "curator_base_app" / "app_config.json"
DEFAULT_MANUAL_STATUS_ID = 1


@dataclass(frozen=True)
class AlbumRow:
    row_id: int
    current_path: str
    expected_path: str | None
    status_id: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate workspace_album current_path/expected_path and reconcile status_id."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite database path (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=None,
        help="Archive root for resolving relative paths (default: read from app_config.json)",
    )
    parser.add_argument(
        "--manual-status-id",
        type=int,
        default=DEFAULT_MANUAL_STATUS_ID,
        help=f"status_id used when both paths are inaccessible (default: {DEFAULT_MANUAL_STATUS_ID})",
    )
    parser.add_argument("--apply", action="store_true", help="Persist updates to database")
    parser.add_argument(
        "--preview",
        type=int,
        default=20,
        help="How many changed rows to print as examples (default: 20)",
    )
    return parser.parse_args()


def read_archive_root(app_config_path: Path) -> Path | None:
    if not app_config_path.exists():
        return None
    try:
        raw = json.loads(app_config_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    value = raw.get("archive_root")
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value.strip())


def resolve_candidates(path_value: str, archive_root: Path | None) -> list[Path]:
    raw = Path(path_value)
    candidates: list[Path] = []

    if raw.is_absolute():
        candidates.append(raw)

    if archive_root is not None:
        ar = archive_root.expanduser().resolve()
        candidates.append((ar / path_value).resolve())

        parts = list(raw.parts)
        if parts and parts[0] == ar.name:
            candidates.append((ar / Path(*parts[1:])).resolve())

    candidates.append((REPO_ROOT / path_value).resolve())

    # Keep order while removing duplicates.
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def is_accessible_dir(path_value: str, archive_root: Path | None) -> bool:
    if not path_value or not path_value.strip():
        return False

    for candidate in resolve_candidates(path_value, archive_root):
        try:
            if not candidate.exists() or not candidate.is_dir():
                continue
            if not os.access(candidate, os.R_OK | os.X_OK):
                continue
            return True
        except OSError:
            continue

    return False


def load_rows(conn: sqlite3.Connection) -> list[AlbumRow]:
    rows = conn.execute(
        """
        SELECT id, current_path, expected_path, status_id
        FROM workspace_album
        ORDER BY id
        """
    ).fetchall()

    return [
        AlbumRow(
            row_id=int(row_id),
            current_path=str(current_path or ""),
            expected_path=(str(expected_path) if expected_path is not None and str(expected_path).strip() else None),
            status_id=int(status_id),
        )
        for row_id, current_path, expected_path, status_id in rows
    ]


def process_rows(
    conn: sqlite3.Connection,
    rows: list[AlbumRow],
    archive_root: Path | None,
    manual_status_id: int,
    apply: bool,
    preview: int,
) -> None:
    scanned = 0
    current_ok_count = 0
    fixed_current_path_count = 0
    marked_manual_count = 0
    unchanged_count = 0
    printed = 0

    if apply:
        conn.execute("BEGIN")

    for row in rows:
        scanned += 1
        current_ok = is_accessible_dir(row.current_path, archive_root)

        if current_ok:
            current_ok_count += 1
            unchanged_count += 1
            continue

        expected_ok = bool(row.expected_path) and is_accessible_dir(row.expected_path or "", archive_root)

        if expected_ok and row.expected_path is not None:
            fixed_current_path_count += 1
            if printed < preview:
                print(
                    f"[id={row.row_id}] current_path inaccessible -> current_path updated to expected_path"
                )
                print(f"  old current_path: {row.current_path}")
                print(f"  new current_path: {row.expected_path}")
                printed += 1

            if apply:
                conn.execute(
                    "UPDATE workspace_album SET current_path = ? WHERE id = ?",
                    (row.expected_path, row.row_id),
                )
            continue

        if row.status_id != manual_status_id:
            marked_manual_count += 1
            if printed < preview:
                print(
                    f"[id={row.row_id}] both paths inaccessible -> status_id {row.status_id} -> {manual_status_id}"
                )
                print(f"  current_path: {row.current_path}")
                print(f"  expected_path: {row.expected_path}")
                printed += 1

            if apply:
                conn.execute(
                    "UPDATE workspace_album SET status_id = ? WHERE id = ?",
                    (manual_status_id, row.row_id),
                )
        else:
            unchanged_count += 1

    if apply:
        conn.commit()

    print("Path validation summary")
    print(f"Rows scanned: {scanned}")
    print(f"Rows with accessible current_path: {current_ok_count}")
    print(f"Rows fixed by expected_path -> current_path: {fixed_current_path_count}")
    print(f"Rows marked manual (status_id={manual_status_id}): {marked_manual_count}")
    print(f"Rows unchanged: {unchanged_count}")
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")


def main() -> int:
    args = parse_args()
    archive_root = args.archive_root
    if archive_root is None:
        archive_root = read_archive_root(DEFAULT_APP_CONFIG)

    with sqlite3.connect(args.db) as conn:
        rows = load_rows(conn)
        process_rows(
            conn=conn,
            rows=rows,
            archive_root=archive_root,
            manual_status_id=args.manual_status_id,
            apply=args.apply,
            preview=max(args.preview, 0),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
