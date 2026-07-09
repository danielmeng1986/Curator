#!/usr/bin/env python3
"""Delete workspace_album rows by IDs, optionally deleting album folders too.

Examples:
  python3 scripts/delete_workspace_albums.py 18253,18249,18243,18241
  python3 scripts/delete_workspace_albums.py 18253,18249 --apply
  python3 scripts/delete_workspace_albums.py 18253,18249 --apply --delete
  python3 scripts/delete_workspace_albums.py 18253,18249 -ad

Notes:
- Default mode is dry-run (no database or filesystem changes).
- --delete only takes effect together with --apply.
- When --delete is enabled, filesystem cleanup is attempted first.
  If a folder delete fails, that album row is kept in DB to avoid inconsistency.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
DEFAULT_ARCHIVE = Path("/Volumes/NAS-RAID5/RAID/Prime_Media/Archive")


def parse_ids(value: str) -> list[int]:
    if not value:
        raise argparse.ArgumentTypeError("ids cannot be empty")

    ids: list[int] = []
    invalid: list[str] = []
    for token in value.split(","):
        raw = token.strip()
        if not raw:
            continue
        if not raw.isdigit():
            invalid.append(raw)
            continue
        row_id = int(raw)
        if row_id <= 0:
            invalid.append(raw)
            continue
        ids.append(row_id)

    if invalid:
        raise argparse.ArgumentTypeError(f"invalid ids: {', '.join(invalid)}")
    if not ids:
        raise argparse.ArgumentTypeError("no valid id found")

    # Keep input order while deduplicating.
    unique_ids = list(dict.fromkeys(ids))
    return unique_ids


def resolve_disk_path(current_path: str, archive_root: Path) -> Path:
    p = Path(current_path)
    if p.is_absolute():
        return p
    return archive_root / p


def delete_folder(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return True, "missing on disk (treated as already clean)"
    if not path.is_dir():
        return False, "path exists but is not a directory"

    try:
        shutil.rmtree(path)
        return True, "deleted"
    except OSError as exc:
        return False, f"delete failed: {exc}"


def fetch_rows(conn: sqlite3.Connection, ids: list[int]) -> list[tuple[int, str]]:
    placeholders = ",".join("?" for _ in ids)
    sql = f"SELECT id, current_path FROM workspace_album WHERE id IN ({placeholders}) ORDER BY id"
    return list(conn.execute(sql, ids).fetchall())


def delete_rows(conn: sqlite3.Connection, ids: list[int]) -> int:
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    sql = f"DELETE FROM workspace_album WHERE id IN ({placeholders})"
    cur = conn.execute(sql, ids)
    return cur.rowcount if cur.rowcount is not None else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete workspace_album rows by comma-separated IDs."
    )
    parser.add_argument(
        "ids",
        type=parse_ids,
        help="Comma-separated IDs, e.g. 18253,18249,18243,18241",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"SQLite database path (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=DEFAULT_ARCHIVE,
        help=f"Archive root used to resolve relative current_path (default: {DEFAULT_ARCHIVE})",
    )
    parser.add_argument(
        "-a",
        "--apply",
        action="store_true",
        help="Apply changes (default is dry-run)",
    )
    parser.add_argument(
        "-d",
        "--delete",
        action="store_true",
        help="Also delete folder at current_path (effective only with --apply)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERROR: database not found: {args.db}", file=sys.stderr)
        return 1

    with sqlite3.connect(args.db) as conn:
        rows = fetch_rows(conn, args.ids)

        found_by_id = {row_id: current_path for row_id, current_path in rows}
        missing_ids = [row_id for row_id in args.ids if row_id not in found_by_id]

        print(f"Input IDs: {len(args.ids)}")
        print(f"Found rows: {len(rows)}")
        if missing_ids:
            print(f"Missing IDs: {','.join(str(i) for i in missing_ids)}")

        if not rows:
            print("Nothing to do.")
            return 0

        print("\nPlan:")
        for row_id, current_path in rows:
            print(f"  id={row_id} current_path={current_path}")

        if args.delete and not args.apply:
            print("\nNOTE: --delete is ignored in dry-run mode (add --apply).")

        if not args.apply:
            print("\nMode: DRY-RUN")
            return 0

        deletable_ids: list[int] = []
        failed_folder_ids: list[int] = []

        if args.delete:
            print("\nFilesystem cleanup:")
            for row_id, current_path in rows:
                disk_path = resolve_disk_path(current_path, args.archive)
                ok, message = delete_folder(disk_path)
                print(f"  id={row_id} path={disk_path} -> {message}")
                if ok:
                    deletable_ids.append(row_id)
                else:
                    failed_folder_ids.append(row_id)
        else:
            deletable_ids = [row_id for row_id, _ in rows]

        deleted_count = 0
        if deletable_ids:
            conn.execute("BEGIN")
            deleted_count = delete_rows(conn, deletable_ids)
            conn.commit()

        print("\nResult:")
        print(f"  DB rows deleted: {deleted_count}")
        if args.delete:
            print(f"  Folder delete failed IDs: {','.join(str(i) for i in failed_folder_ids) if failed_folder_ids else 'none'}")
            if failed_folder_ids:
                print("  NOTE: failed folder IDs were NOT deleted from DB.")

        return 0 if not failed_folder_ids else 2


if __name__ == "__main__":
    raise SystemExit(main())
