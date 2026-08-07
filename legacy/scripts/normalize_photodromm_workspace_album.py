#!/usr/bin/env python3
"""Normalize Photodromm album names and set parent album linkage.

Rules:
- Only rows where studio_name == 'Photodromm' are scanned.
- Ensure workspace_album has column: belongs_to_album_id INTEGER.
- In same primary_model, if album b differs from album a only by suffix '_<index>'
    (index >= 2), then b.belongs_to_album_id = a.id.
    Examples:
        cameron_greenanatomy      -> belongs_to_album_id = self id
        cameron_greenanatomy_2    -> belongs_to_album_id = id(cameron_greenanatomy)
- Rows not matching this split-release pattern fall back to self id.
- Normalize album_name by pattern:
    <model_name>_<album_name>_<index>
  where index is shown only when > 1.
- Then remove '<primary_model> ' prefix from normalized name.

Default mode is dry-run; use --apply to persist changes.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
DEFAULT_STUDIO = "Photodromm"

SUFFIX_SEP_INDEX_RE = re.compile(r"^(.*?)[_-](\d+)$")
SUFFIX_DIRECT_INDEX_RE = re.compile(r"^(.*?)(\d+)$")
SPLIT_RELEASE_UNDERSCORE_RE = re.compile(r"^(.*?)_(\d+)$")
SEP_WORD_RE = re.compile(r"[_-]+")


@dataclass(frozen=True)
class ParsedAlbum:
    base_slug: str
    index: int


def normalize_key(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def slug_to_title(text: str) -> str:
    words = [w for w in SEP_WORD_RE.split(text.strip()) if w]
    return " ".join(word.capitalize() for word in words)


def split_base_and_index(album_name: str) -> ParsedAlbum:
    name = (album_name or "").strip()
    if not name:
        return ParsedAlbum(base_slug=name, index=1)

    m = SUFFIX_SEP_INDEX_RE.match(name)
    if m:
        base = m.group(1).strip("_-").strip()
        index = int(m.group(2))
        if base:
            return ParsedAlbum(base_slug=base, index=max(index, 1))

    m = SUFFIX_DIRECT_INDEX_RE.match(name)
    if m:
        base = m.group(1).strip("_-").strip()
        index = int(m.group(2))
        if base:
            return ParsedAlbum(base_slug=base, index=max(index, 1))

    return ParsedAlbum(base_slug=name, index=1)


def strip_model_slug_prefix(base_slug: str, primary_model: str) -> str:
    if not base_slug:
        return base_slug

    primary_first_name = (primary_model or "").strip().split(" ", 1)[0].lower()
    if not primary_first_name:
        return base_slug

    prefix = f"{primary_first_name}_"
    if base_slug.lower().startswith(prefix):
        remainder = base_slug[len(prefix) :].strip("_-").strip()
        if remainder:
            return remainder

    return base_slug


def ensure_column_exists(conn: sqlite3.Connection, table_name: str, column_name: str, column_sql_type: str) -> bool:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")]
    if column_name in cols:
        return False

    conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql_type}")
    return True


def split_release_parent_album_name(album_name: str) -> str | None:
    """Return parent album name for '<base>_<index>' where index >= 2."""
    name = (album_name or "").strip()
    if not name:
        return None

    m = SPLIT_RELEASE_UNDERSCORE_RE.match(name)
    if not m:
        return None

    base = m.group(1).strip()
    index = int(m.group(2))
    if not base or index < 2:
        return None

    return base


def build_normalized_album_name(primary_model: str, album_core_slug: str, index: int) -> str:
    album_core_title = slug_to_title(album_core_slug)
    if not album_core_title:
        album_core_title = album_core_slug.strip()

    normalized_with_model = primary_model.strip()
    if album_core_title:
        normalized_with_model = f"{normalized_with_model} {album_core_title}".strip()

    if index > 1:
        normalized_with_model = f"{normalized_with_model} {index}".strip()

    primary_prefix = f"{primary_model.strip()} "
    if primary_prefix.strip() and normalized_with_model.startswith(primary_prefix):
        stripped = normalized_with_model[len(primary_prefix) :].strip()
        if stripped:
            return stripped

    return normalized_with_model


def normalize_rows(conn: sqlite3.Connection, studio_name: str, apply: bool, preview: int) -> int:
    rows = list(
        conn.execute(
            """
            SELECT id, primary_model, album_name, belongs_to_album_id
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

    parsed_rows: list[tuple[int, str, str, int | None, str]] = []

    # Exact base album id by (model, album_name) for split-release linkage.
    base_album_id_map: dict[tuple[str, str], int] = {}
    for row_id, primary_model, album_name, _old_belongs_to in rows:
        key = (normalize_key(primary_model), (album_name or "").strip())
        if key[1] and key not in base_album_id_map:
            base_album_id_map[key] = row_id

    for row_id, primary_model, album_name, old_belongs_to in rows:
        parsed = split_base_and_index(album_name)
        core_slug = strip_model_slug_prefix(parsed.base_slug, primary_model)
        new_album_name = build_normalized_album_name(primary_model, core_slug, parsed.index)

        parent_base_name = split_release_parent_album_name(album_name)
        if parent_base_name:
            parent_key = (normalize_key(primary_model), parent_base_name)
            new_belongs_to = base_album_id_map.get(parent_key, row_id)
        else:
            new_belongs_to = row_id

        parsed_rows.append((row_id, album_name, old_belongs_to, new_album_name, new_belongs_to))

    if apply:
        conn.execute("BEGIN")

    for row_id, old_album_name, old_belongs_to, new_album_name, new_belongs_to in parsed_rows:

        if (new_album_name == old_album_name) and (new_belongs_to == old_belongs_to):
            continue

        changed += 1
        if samples < preview:
            print(f"[id={row_id}] {old_album_name!r}")
            print(f"  belongs_to:      {old_belongs_to!r} -> {new_belongs_to!r}")
            print(f"  album_name:      {old_album_name!r} -> {new_album_name!r}")
            samples += 1

        if apply:
            conn.execute(
                """
                UPDATE workspace_album
                SET album_name = ?, belongs_to_album_id = ?
                WHERE id = ?
                """,
                (new_album_name, new_belongs_to, row_id),
            )

    if apply:
        conn.commit()

    print(f"Studio: {studio_name}")
    print(f"Rows scanned: {total}")
    print(f"Rows changed: {changed}")
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN'}")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize Photodromm workspace_album names and set belongs_to_album_id."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite database path (default: {DEFAULT_DB})")
    parser.add_argument("--studio", default=DEFAULT_STUDIO, help=f"Studio name filter (default: {DEFAULT_STUDIO})")
    parser.add_argument("--apply", action="store_true", help="Persist updates to database")
    parser.add_argument("--preview", type=int, default=20, help="How many changed examples to print (default: 20)")
    args = parser.parse_args()

    with sqlite3.connect(args.db) as conn:
        added = ensure_column_exists(conn, "workspace_album", "belongs_to_album_id", "INTEGER")
        if added:
            print("Schema change: added workspace_album.belongs_to_album_id (INTEGER)")
            if not args.apply:
                print("Note: schema change is persisted immediately by SQLite DDL.")

        normalize_rows(conn, args.studio, apply=args.apply, preview=max(args.preview, 0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
