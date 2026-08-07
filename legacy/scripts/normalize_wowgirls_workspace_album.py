#!/usr/bin/env python3
"""Normalize Wowgirls rows in workspace_album using folder-name conventions.

Rules implemented from requirement:
- Source rows: workspace_album where studio_name == "Wowgirls".
- Parse album folder name from current_path basename.
- Folder pattern (typical):
    <PrimaryModelCamel>[_<AdditionalModelCamel>...]_<AlbumCamel>[_<Resolution>]
- Trailing resolution tokens like 2000px/4000px are ignored.
- Additional model tokens are validated against model.name.
  - Found in model table and not equal to primary_model -> additional_models
  - Not found -> treated as part of album_name
- Only album_name and additional_models are updated.

Default mode is dry-run; use --apply to persist changes.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
DEFAULT_STUDIO = "Wowgirls"
RESOLUTION_RE = re.compile(r"^\d{3,5}px$", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedAlbum:
    album_name: str
    additional_models: str | None


def normalize_key(value: str) -> str:
    """Normalize a model string for robust equality checks."""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def camel_to_words(token: str) -> str:
    """Split CamelCase-ish token to spaced words."""
    token = token.strip("_")
    if not token:
        return ""

    # Split boundaries like "FunnySunny" -> "Funny Sunny", "JSONData" -> "JSON Data"
    token = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", token)
    token = re.sub(r"([a-z\d])([A-Z])", r"\1 \2", token)
    token = re.sub(r"\s+", " ", token)
    return token.strip()


def strip_resolution_suffix(tokens: list[str]) -> list[str]:
    trimmed = list(tokens)
    while trimmed and RESOLUTION_RE.match(trimmed[-1] or ""):
        trimmed.pop()
    return trimmed


def parse_wowgirls_folder_name(
    folder_name: str,
    primary_model: str,
    model_key_to_name: dict[str, str],
) -> ParsedAlbum:
    tokens = [part for part in folder_name.split("_") if part]
    tokens = strip_resolution_suffix(tokens)
    if not tokens:
        return ParsedAlbum(album_name=folder_name, additional_models=None)

    primary_key = normalize_key(primary_model)
    idx = 0
    if normalize_key(tokens[0]) == primary_key:
        idx = 1

    additional_models: list[str] = []
    album_tokens: list[str] = []
    in_album_part = False

    for token in tokens[idx:]:
        if in_album_part:
            album_tokens.append(token)
            continue

        key = normalize_key(token)
        matched_model = model_key_to_name.get(key)
        if matched_model and normalize_key(matched_model) != primary_key:
            additional_models.append(matched_model)
            continue

        # First non-model token begins album segment. Unknown name-like tokens
        # are intentionally treated as album_name content per requirement.
        in_album_part = True
        album_tokens.append(token)

    if not album_tokens:
        # Fallback: use non-primary suffix if available, else raw folder_name.
        fallback_tokens = tokens[idx:] if idx < len(tokens) else tokens
        album_tokens = fallback_tokens if fallback_tokens else [folder_name]

    album_name = " ".join(filter(None, (camel_to_words(tok) for tok in album_tokens))).strip()
    if not album_name:
        album_name = folder_name

    unique_additional: list[str] = []
    seen: set[str] = set()
    for name in additional_models:
        key = normalize_key(name)
        if key in seen:
            continue
        seen.add(key)
        unique_additional.append(name)

    add_models_str = ", ".join(unique_additional) if unique_additional else None
    return ParsedAlbum(album_name=album_name, additional_models=add_models_str)


def load_model_map(conn: sqlite3.Connection) -> dict[str, str]:
    model_key_to_name: dict[str, str] = {}
    for (name,) in conn.execute("SELECT name FROM model"):
        if not name:
            continue
        key = normalize_key(name)
        if key and key not in model_key_to_name:
            model_key_to_name[key] = name
    return model_key_to_name


def normalize_rows(conn: sqlite3.Connection, studio_name: str, apply: bool, preview: int) -> int:
    model_map = load_model_map(conn)

    rows = list(
        conn.execute(
            """
            SELECT id, current_path, primary_model, album_name, additional_models
            FROM workspace_album
            WHERE studio_name = ?
            ORDER BY id
            """,
            (studio_name,),
        )
    )

    total = len(rows)
    changed = 0
    samples_printed = 0

    if apply:
        conn.execute("BEGIN")

    for row_id, current_path, primary_model, old_album_name, old_additional in rows:
        folder_name = Path(current_path).name
        parsed = parse_wowgirls_folder_name(folder_name, primary_model, model_map)

        new_album = parsed.album_name
        new_additional = parsed.additional_models

        old_additional_norm = old_additional.strip() if isinstance(old_additional, str) else None
        if old_additional_norm == "":
            old_additional_norm = None

        if new_album == old_album_name and new_additional == old_additional_norm:
            continue

        changed += 1
        if samples_printed < preview:
            print(f"[id={row_id}] {folder_name}")
            print(f"  album_name:      {old_album_name!r} -> {new_album!r}")
            print(f"  additional:      {old_additional_norm!r} -> {new_additional!r}")
            samples_printed += 1

        if apply:
            conn.execute(
                """
                UPDATE workspace_album
                SET album_name = ?, additional_models = ?
                WHERE id = ?
                """,
                (new_album, new_additional, row_id),
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
        description="Normalize Wowgirls workspace_album rows using folder naming rules."
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