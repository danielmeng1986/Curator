#!/usr/bin/env python3
"""Normalize Eternal Desire album names in workspace_album.

Rules:
- Only rows where studio_name = 'Eternal Desire' are processed.
- Only transform album_name by converting each word to title case
  (first letter uppercase, remaining letters lowercase).
- Preserve separators/punctuation; only adjust capitalization.

Default mode is dry-run; use --apply to persist updates.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
DEFAULT_STUDIO = "Eternal Desire"


def title_case_words(text: str) -> str:
    if not text:
        return text

    tokens = re.findall(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)?|[^A-Za-z0-9]+", text.strip())
    result: list[str] = []
    for token in tokens:
        if not token:
            continue
        if re.fullmatch(r"[^A-Za-z0-9]+", token):
            result.append(token)
            continue

        parts = []
        for part in token.split("-"):
            if not part:
                parts.append("")
            else:
                parts.append(part[0].upper() + part[1:].lower())
        result.append("-".join(parts))

    return "".join(result)


def normalize_album_name(album_name: Optional[str]) -> Optional[str]:
    if not album_name:
        return None

    normalized = title_case_words(album_name)
    return normalized if normalized else album_name


def normalize_rows(conn: sqlite3.Connection, studio_name: str, apply: bool, preview: int) -> int:
    rows = list(
        conn.execute(
            """
            SELECT id, album_name
            FROM workspace_album
            WHERE studio_name = ?
            ORDER BY id
            """,
            (studio_name,),
        )
    )

    total = len(rows)
    changed = 0
    samples = 0

    if apply:
        conn.execute("BEGIN")

    for row_id, old_album_name in rows:
        new_album_name = normalize_album_name(old_album_name)
        if new_album_name is None or new_album_name == old_album_name:
            continue

        changed += 1
        if samples < preview:
            print(f"[id={row_id}] {old_album_name!r} -> {new_album_name!r}")
            samples += 1

        if apply:
            conn.execute(
                "UPDATE workspace_album SET album_name = ? WHERE id = ?",
                (new_album_name, row_id),
            )

    if apply:
        conn.commit()

    print(f"Studio: {studio_name}")
    print(f"Rows scanned: {total}")
    print(f"Rows changed: {changed}")
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize Eternal Desire album names in workspace_album.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite database path (default: {DEFAULT_DB})")
    parser.add_argument("--studio", default=DEFAULT_STUDIO, help=f"Studio name filter (default: {DEFAULT_STUDIO})")
    parser.add_argument("--apply", action="store_true", help="Persist updates to the database")
    parser.add_argument("--preview", type=int, default=20, help="How many changed examples to print (default: 20)")
    args = parser.parse_args()

    with sqlite3.connect(args.db) as conn:
        normalize_rows(conn, args.studio, apply=args.apply, preview=max(args.preview, 0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())