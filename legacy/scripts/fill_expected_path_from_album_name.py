#!/usr/bin/env python3
"""Populate expected_path from current_path parent + album_name for selected statuses.

Rules:
- Process rows where status_id in (2, 8).
- expected_path = <parent of current_path> + "/" + <album_name>
- If status_id == 2, update to 3 after expected_path is written.
- If status_id == 8, keep status_id as 8.

Default mode is dry-run. Use --apply to persist updates.
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"


@dataclass(frozen=True)
class RowChange:
    row_id: int
    old_status: int
    new_status: int
    current_path: str
    old_expected_path: str | None
    new_expected_path: str


def normalize_text(value: str | None) -> str:
    return (value or "").strip()


def build_expected_path(current_path: str, album_name: str) -> str:
    current = normalize_text(current_path)
    album = normalize_text(album_name)
    if not album:
        return ""
    if "/" not in current:
        return album
    parent = current.rsplit("/", 1)[0]
    return f"{parent}/{album}"


def collect_changes(conn: sqlite3.Connection) -> list[RowChange]:
    rows = conn.execute(
        """
        SELECT id, status_id, current_path, album_name, expected_path
        FROM workspace_album
        WHERE status_id IN (2, 8)
        ORDER BY id
        """
    ).fetchall()

    changes: list[RowChange] = []
    for row_id, status_id, current_path, album_name, expected_path in rows:
        new_expected = build_expected_path(current_path or "", album_name or "")
        if not new_expected:
            continue

        old_expected = normalize_text(expected_path)
        new_status = 3 if int(status_id) == 2 else 8

        if old_expected == new_expected and int(status_id) == new_status:
            continue

        changes.append(
            RowChange(
                row_id=int(row_id),
                old_status=int(status_id),
                new_status=int(new_status),
                current_path=normalize_text(current_path),
                old_expected_path=expected_path,
                new_expected_path=new_expected,
            )
        )

    return changes


def apply_changes(conn: sqlite3.Connection, changes: list[RowChange]) -> None:
    conn.execute("BEGIN")
    for item in changes:
        conn.execute(
            """
            UPDATE workspace_album
            SET expected_path = ?, status_id = ?
            WHERE id = ?
            """,
            (item.new_expected_path, item.new_status, item.row_id),
        )
    conn.commit()


def print_preview(changes: list[RowChange], preview: int) -> None:
    print(f"Rows to update: {len(changes)}")
    print(f"Preview shown: {min(len(changes), preview)}")
    for item in changes[:preview]:
        print(f"[id={item.row_id}] status: {item.old_status} -> {item.new_status}")
        print(f"  current_path:  {item.current_path}")
        print(f"  expected_path: {item.old_expected_path!r} -> {item.new_expected_path!r}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fill expected_path for status_id 2/8 and normalize status transitions."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})")
    parser.add_argument("--apply", action="store_true", help="Persist updates")
    parser.add_argument("--preview", type=int, default=20, help="How many changed rows to print (default: 20)")
    args = parser.parse_args()

    with sqlite3.connect(args.db) as conn:
        changes = collect_changes(conn)
        print_preview(changes, max(args.preview, 0))
        if args.apply:
            apply_changes(conn, changes)
            print("Mode: APPLY")
        else:
            print("Mode: DRY-RUN")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())