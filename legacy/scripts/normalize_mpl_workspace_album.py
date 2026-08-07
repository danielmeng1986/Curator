#!/usr/bin/env python3
"""Normalize MPL album names in workspace_album.

Rule:
- Only rows where studio_name == 'MPL' are scanned.
- If album_name matches '<primary_model> <album_name>', remove the
  '<primary_model> ' prefix and keep the remainder as the new album_name.
- Only album_name is updated.

Default mode is dry-run; use --apply to persist changes.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
DEFAULT_STUDIO = "MPL"


def strip_primary_model_prefix(album_name: str, primary_model: str) -> str | None:
    if not album_name or not primary_model:
        return None

    prefix = f"{primary_model.strip()} "
    if not prefix.strip() or not album_name.startswith(prefix):
        return None

    remainder = album_name[len(prefix) :].strip()
    if not remainder:
        return None

    return remainder


def normalize_rows(conn: sqlite3.Connection, studio_name: str, apply: bool, preview: int) -> int:
    rows = list(
        conn.execute(
            """
            SELECT id, primary_model, album_name
            FROM workspace_album
            WHERE studio_name = ?
            ORDER BY id
            """,
            (studio_name,),
        )
    )

    total = len(rows)
    eligible = 0
    changed = 0
    samples = 0

    if apply:
        conn.execute("BEGIN")

    for row_id, primary_model, old_album_name in rows:
        new_album_name = strip_primary_model_prefix(old_album_name, primary_model)
        if new_album_name is None:
            continue

        eligible += 1
        if new_album_name == old_album_name:
            continue

        changed += 1
        if samples < preview:
            print(f"[id={row_id}] {old_album_name!r}")
            print(f"  primary_model:   {primary_model!r}")
            print(f"  album_name:      {old_album_name!r} -> {new_album_name!r}")
            samples += 1

        if apply:
            conn.execute(
                """
                UPDATE workspace_album
                SET album_name = ?
                WHERE id = ?
                """,
                (new_album_name, row_id),
            )

    if apply:
        conn.commit()

    print(f"Studio: {studio_name}")
    print(f"Rows scanned: {total}")
    print(f"Rows eligible: {eligible}")
    print(f"Rows changed: {changed}")
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize MPL workspace_album names by removing '<primary_model> ' prefix."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite database path (default: {DEFAULT_DB})")
    parser.add_argument("--studio", default=DEFAULT_STUDIO, help=f"Studio name filter (default: {DEFAULT_STUDIO})")
    parser.add_argument("--apply", action="store_true", help="Persist updates to database")
    parser.add_argument("--preview", type=int, default=20, help="How many changed examples to print (default: 20)")
    args = parser.parse_args()

    with sqlite3.connect(args.db) as conn:
        normalize_rows(conn, args.studio, apply=args.apply, preview=max(args.preview, 0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())