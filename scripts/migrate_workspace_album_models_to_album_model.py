#!/usr/bin/env python3
"""Migrate model references from workspace_album into album_model.

Rules:
- primary_model -> album_model(role='primary')
- additional_models (comma/Chinese comma/semicolon/pipe separated) -> album_model(role='additional')
- model names are resolved from model.primary_name / model.display_name.
- duplicate pairs (album_id, model_id) are deduplicated.

Default mode is dry-run. Use --apply to persist changes.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
SPLIT_PATTERN = re.compile(r"[,，;；|]+")


@dataclass
class Stats:
    workspace_rows: int = 0
    rows_with_album_id: int = 0
    candidate_relations: int = 0
    inserted_relations: int = 0
    existing_relations: int = 0
    unresolved_names: int = 0


def normalize_name(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


def split_additional_models(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in SPLIT_PATTERN.split(raw) if p and p.strip()]
    return parts


def backup_db(db_path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_name(f"{db_path.stem}.backup_before_album_model_migration_{ts}{db_path.suffix}")
    shutil.copy2(db_path, backup_path)
    return backup_path


def build_model_lookup(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT id, primary_name, display_name FROM model").fetchall()
    lookup: dict[str, int] = {}
    for model_id, primary_name, display_name in rows:
        for value in (primary_name, display_name):
            if not isinstance(value, str):
                continue
            key = normalize_name(value)
            if not key:
                continue
            lookup.setdefault(key, int(model_id))
    return lookup


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate workspace_album.primary_model/additional_models into album_model"
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})")
    parser.add_argument("--apply", action="store_true", help="Persist migration changes")
    parser.add_argument("--no-backup", action="store_true", help="Do not create backup before apply")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when unresolved model names exist",
    )
    args = parser.parse_args()

    db_path = args.db.expanduser().resolve()
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}")
        return 1

    if args.apply and not args.no_backup:
        backup_path = backup_db(db_path)
        print(f"[INFO] Backup created: {backup_path}")

    conn = sqlite3.connect(db_path)
    stats = Stats()
    unresolved_counter: Counter[str] = Counter()

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN")

        model_lookup = build_model_lookup(conn)
        if not model_lookup:
            raise RuntimeError("model table has no resolvable names")

        rows = conn.execute(
            """
            SELECT id, album_id, primary_model, additional_models
            FROM workspace_album
            ORDER BY id
            """
        ).fetchall()

        stats.workspace_rows = len(rows)
        role_for_pair: dict[tuple[int, int], str] = {}

        for wa_id, album_id, primary_model, additional_models in rows:
            if album_id is None:
                continue
            stats.rows_with_album_id += 1
            album_id_int = int(album_id)

            primary_name = primary_model if isinstance(primary_model, str) else ""
            primary_key = normalize_name(primary_name) if primary_name else ""
            if primary_key:
                model_id = model_lookup.get(primary_key)
                if model_id is None:
                    unresolved_counter[primary_name.strip()] += 1
                else:
                    role_for_pair[(album_id_int, model_id)] = "primary"
                    stats.candidate_relations += 1

            for additional_name in split_additional_models(additional_models if isinstance(additional_models, str) else None):
                add_key = normalize_name(additional_name)
                if not add_key:
                    continue
                model_id = model_lookup.get(add_key)
                if model_id is None:
                    unresolved_counter[additional_name] += 1
                    continue

                key = (album_id_int, model_id)
                # primary role has higher precedence.
                if key in role_for_pair and role_for_pair[key] == "primary":
                    continue
                role_for_pair.setdefault(key, "additional")
                stats.candidate_relations += 1

        stats.unresolved_names = sum(unresolved_counter.values())
        if args.strict and stats.unresolved_names > 0:
            top = ", ".join(f"{name}({cnt})" for name, cnt in unresolved_counter.most_common(20))
            raise RuntimeError(f"unresolved model names exist: {top}")

        for (album_id, model_id), role in role_for_pair.items():
            before = conn.total_changes
            conn.execute(
                """
                INSERT OR IGNORE INTO album_model (album_id, model_id, role)
                VALUES (?, ?, ?)
                """,
                (album_id, model_id, role),
            )
            changed = conn.total_changes - before
            if changed:
                stats.inserted_relations += 1
            else:
                stats.existing_relations += 1
                # Keep role consistent when relation already exists.
                if role == "primary":
                    conn.execute(
                        """
                        UPDATE album_model
                        SET role = 'primary'
                        WHERE album_id = ? AND model_id = ?
                          AND (role IS NULL OR role <> 'primary')
                        """,
                        (album_id, model_id),
                    )

        if args.apply:
            conn.commit()
            print("[INFO] Migration status: APPLIED")
        else:
            conn.rollback()
            print("[INFO] Migration status: DRY-RUN (ROLLED BACK)")

        print(f"[INFO] workspace_album rows: {stats.workspace_rows}")
        print(f"[INFO] workspace_album with album_id: {stats.rows_with_album_id}")
        print(f"[INFO] candidate relations: {len(role_for_pair)}")
        print(f"[INFO] inserted relations: {stats.inserted_relations}")
        print(f"[INFO] existing relations: {stats.existing_relations}")
        print(f"[INFO] unresolved name occurrences: {stats.unresolved_names}")

        if unresolved_counter:
            print("[WARN] Top unresolved model names:")
            for name, cnt in unresolved_counter.most_common(20):
                print(f"  - {name}: {cnt}")

        with sqlite3.connect(db_path) as read_conn:
            total_rel = read_conn.execute("SELECT COUNT(*) FROM album_model").fetchone()[0]
            print(f"[INFO] post-check album_model rows: {total_rel}")

        return 0
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        print(f"ERROR: migration failed: {exc}")
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
