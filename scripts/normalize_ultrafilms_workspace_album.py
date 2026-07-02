#!/usr/bin/env python3
"""Normalize Ultrafilms album names in workspace_album.

Naming pattern handled:
  <album-slug>_<model-slug>[_<model-slug>...]_[<resolution>]

Examples:
  beautiful-blonde_jenny-wild_4000px
  two-to-tango_aislin_sienna-kim_4000px

Rules:
- Only rows where studio_name == 'Ultrafilms' are scanned.
- Only album_name values matching the underscore-based pattern are processed.
- Skip numeric-only legacy names like: 4000, 4000-2.
- The first segment is the real album name.
- Resolution suffixes (e.g. 4000px/2000px) are removed.
- Segments after album name and before resolution are treated as model candidates:
  - If matches primary_model: ignore.
  - If found in model table: append to additional_models.
  - If not found: write to remark.

Default mode is dry-run; use --apply to persist updates.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
DEFAULT_STUDIO = "Ultrafilms"
RESOLUTION_RE = re.compile(r"^\d{3,5}px$", re.IGNORECASE)
NUMERIC_LEGACY_RE = re.compile(r"^\d+(?:-\d+)?$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedResult:
    album_name: str
    additional_models: str | None
    remark: str | None


def normalize_key(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def slug_to_title(slug: str) -> str:
    words = [part for part in slug.split("-") if part]
    return " ".join(word.capitalize() for word in words)


def strip_resolution_suffix(parts: list[str]) -> list[str]:
    trimmed = list(parts)
    while trimmed and RESOLUTION_RE.match(trimmed[-1] or ""):
        trimmed.pop()
    return trimmed


def should_process_album_name(album_name: str) -> bool:
    if not album_name:
        return False
    if NUMERIC_LEGACY_RE.match(album_name):
        return False

    parts = [part.strip() for part in album_name.split("_") if part.strip()]
    if len(parts) < 2:
        return False

    if not SLUG_RE.match(parts[0]):
        return False

    core_parts = strip_resolution_suffix(parts)
    if len(core_parts) < 2:
        return False

    for token in core_parts[1:]:
        if not SLUG_RE.match(token):
            return False

    return True


def load_model_map(conn: sqlite3.Connection) -> dict[str, str]:
    model_key_to_name: dict[str, str] = {}
    for (name,) in conn.execute("SELECT name FROM model"):
        if not name:
            continue
        key = normalize_key(name)
        if key and key not in model_key_to_name:
            model_key_to_name[key] = name
    return model_key_to_name


def parse_ultrafilms_album(
    album_name_raw: str,
    primary_model: str,
    model_key_to_name: dict[str, str],
) -> ParsedResult:
    parts = [part.strip() for part in album_name_raw.split("_") if part.strip()]
    parts = strip_resolution_suffix(parts)

    album_slug = parts[0]
    candidate_model_tokens = parts[1:]

    primary_key = normalize_key(primary_model)
    additional_models: list[str] = []
    unknown_models: list[str] = []

    for token in candidate_model_tokens:
        token_key = normalize_key(token)
        if not token_key:
            continue

        if token_key == primary_key:
            continue

        matched_name = model_key_to_name.get(token_key)
        if matched_name:
            additional_models.append(matched_name)
        else:
            unknown_models.append(slug_to_title(token))

    seen: set[str] = set()
    dedup_additional: list[str] = []
    for name in additional_models:
        key = normalize_key(name)
        if key in seen:
            continue
        seen.add(key)
        dedup_additional.append(name)

    album_name = slug_to_title(album_slug)
    if not album_name:
        album_name = album_name_raw

    add_models_text = ", ".join(dedup_additional) if dedup_additional else None
    unknown_text = ", ".join(dict.fromkeys(unknown_models)) if unknown_models else None
    remark = f"Unmatched model tokens: {unknown_text}" if unknown_text else None

    return ParsedResult(album_name=album_name, additional_models=add_models_text, remark=remark)


def normalize_rows(conn: sqlite3.Connection, studio_name: str, apply: bool, preview: int) -> int:
    model_map = load_model_map(conn)

    rows = list(
        conn.execute(
            """
            SELECT id, primary_model, album_name, additional_models, remark
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

    for row_id, primary_model, old_album, old_additional, old_remark in rows:
        if not should_process_album_name(old_album):
            continue

        eligible += 1
        parsed = parse_ultrafilms_album(old_album, primary_model, model_map)

        old_additional_norm = old_additional.strip() if isinstance(old_additional, str) else None
        if old_additional_norm == "":
            old_additional_norm = None

        old_remark_norm = old_remark.strip() if isinstance(old_remark, str) else None
        if old_remark_norm == "":
            old_remark_norm = None

        if (
            parsed.album_name == old_album
            and parsed.additional_models == old_additional_norm
            and parsed.remark == old_remark_norm
        ):
            continue

        changed += 1
        if samples < preview:
            print(f"[id={row_id}] {old_album!r}")
            print(f"  album_name:      {old_album!r} -> {parsed.album_name!r}")
            print(f"  additional:      {old_additional_norm!r} -> {parsed.additional_models!r}")
            print(f"  remark:          {old_remark_norm!r} -> {parsed.remark!r}")
            samples += 1

        if apply:
            conn.execute(
                """
                UPDATE workspace_album
                SET album_name = ?, additional_models = ?, remark = ?
                WHERE id = ?
                """,
                (parsed.album_name, parsed.additional_models, parsed.remark, row_id),
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
        description="Normalize Ultrafilms workspace_album names by underscore naming pattern."
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
