#!/usr/bin/env python3
"""Merge two model records by moving all albums from a source model into a target model.

Steps:
1. Compute expected_path for each source album (replace source model name with target).
2. Detect path conflicts against target model's existing albums (DB + filesystem).
3. Print Rename Plan (dry-run by default).
4. With --apply:
   - Update workspace_album rows (primary_model, current_path, expected_path, status_id).
   - Delete source model from model table (after verifying no remaining FK refs).
   - Move album folders on disk.
   - Remove empty source model directory.

Usage:
    python merge_models.py --source "Blake Bartelli" --target "Blake Eden"
    python merge_models.py --source "Blake Bartelli" --target "Blake Eden" --apply
    python merge_models.py --source 123 --target 456 --apply
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from entity_ref_resolver import resolve_entity_ref

DEFAULT_DB = Path("/Volumes/NAS-RAID5/RAID/Curator/database/Curator.db")
DEFAULT_ARCHIVE = Path("/Volumes/NAS-RAID5/RAID/Prime_Media/Archive")

CONFLICT_STATUS_ID = 1  # status that flags manual review


@dataclass
class AlbumMigration:
    album_id: int
    current_path: str
    new_path: str          # new current_path after rebasing under target model
    expected_path: str     # value to write into expected_path column (empty string = NULL)
    primary_model: str
    status_id: int | None
    has_conflict: bool = False
    conflict_note: str = ""


def model_letter(model_name: str) -> str:
    """Return the single uppercase letter prefix for a model name."""
    return model_name[0].upper()


def rebase_path(path: str, source_model: str, target_model: str) -> str:
    """Replace the model-name segment of a path with the target model name.

    Expected path structure: {Letter}/{model_name}/{media_type}/{studio}/{album}
    """
    parts = path.split("/")
    if len(parts) >= 2 and parts[1] == source_model:
        parts[0] = model_letter(target_model)
        parts[1] = target_model
    return "/".join(parts)


def existing_target_paths(conn: sqlite3.Connection, target_model: str) -> set[str]:
    """Return all current_path values for albums already owned by the target model."""
    rows = conn.execute(
        "SELECT current_path FROM workspace_album WHERE primary_model = ?",
        (target_model,),
    ).fetchall()
    return {r[0] for r in rows}


def resolve_conflict(desired: str, occupied: set[str], archive: Path) -> tuple[str, str]:
    """Return a unique path and a note if a suffix was applied."""
    if desired not in occupied and not (archive / desired).exists():
        return desired, ""

    # Try numeric suffixes
    suffix = 2
    while True:
        candidate = f"{desired}_{suffix}"
        if candidate not in occupied and not (archive / candidate).exists():
            return candidate, f"conflict → renamed to suffix _{suffix}"
        suffix += 1


def build_migration_plan(
    conn: sqlite3.Connection,
    source_model: str,
    target_model: str,
    archive: Path,
) -> list[AlbumMigration]:
    rows = conn.execute(
        """
        SELECT id, current_path, expected_path, primary_model, status_id
        FROM workspace_album
        WHERE primary_model = ?
        ORDER BY id
        """,
        (source_model,),
    ).fetchall()

    if not rows:
        return []

    occupied = existing_target_paths(conn, target_model)
    plan: list[AlbumMigration] = []

    for album_id, current_path, expected_path, primary_model, status_id in rows:
        desired = rebase_path(current_path, source_model, target_model)
        resolved, note = resolve_conflict(desired, occupied, archive)

        # Mark the resolved path as occupied so later albums don't collide with it
        occupied.add(resolved)

        has_conflict = bool(note)
        migration = AlbumMigration(
            album_id=album_id,
            current_path=current_path,
            new_path=resolved,
            expected_path=expected_path or "",
            primary_model=primary_model,
            status_id=status_id,
            has_conflict=has_conflict,
            conflict_note=note,
        )
        plan.append(migration)

    return plan


def print_plan(plan: list[AlbumMigration], source_model: str, target_model: str) -> None:
    conflicts = sum(1 for m in plan if m.has_conflict)
    print(f"\nRename Plan: '{source_model}'  →  '{target_model}'")
    print(f"Albums to migrate: {len(plan)}  |  Conflicts requiring review: {conflicts}\n")
    print(f"{'ID':>6}  {'CONFLICT':8}  {'CURRENT PATH':<60}  NEW PATH")
    print("-" * 140)
    for m in plan:
        flag = "⚠ YES" if m.has_conflict else "OK"
        print(f"{m.album_id:>6}  {flag:<8}  {m.current_path:<60}  {m.new_path}")
        if m.has_conflict:
            print(f"{'':>6}  {'':8}  {m.conflict_note}")
    print()


def apply_db_changes(
    conn: sqlite3.Connection,
    plan: list[AlbumMigration],
    source_model_id: int,
    source_model: str,
    target_model: str,
) -> None:
    for m in plan:
        new_status = CONFLICT_STATUS_ID if m.has_conflict else m.status_id
        conn.execute(
            """
            UPDATE workspace_album
            SET primary_model = ?,
                current_path  = ?,
                status_id     = ?
            WHERE id = ?
            """,
            (target_model, m.new_path, new_status, m.album_id),
        )
        print(f"  DB updated id={m.album_id}: '{m.current_path}' → '{m.new_path}'" +
              (" [flagged for review]" if m.has_conflict else ""))

    # Verify no remaining FK references to source model
    remaining = conn.execute(
        "SELECT COUNT(*) FROM workspace_album WHERE primary_model = ?",
        (source_model,),
    ).fetchone()[0]

    if remaining > 0:
        print(f"\n⚠ WARNING: {remaining} album(s) still reference '{source_model}'. "
              "Source model NOT deleted. Please investigate.")
        conn.rollback()
        return

    # Delete source model
    row = conn.execute("SELECT id FROM model WHERE id = ?", (source_model_id,)).fetchone()
    if row:
        conn.execute("DELETE FROM model WHERE id = ?", (source_model_id,))
        print(f"\n  Model deleted: id={source_model_id} '{source_model}'")
    else:
        print(f"\n  Model id={source_model_id} ('{source_model}') not found in model table (already removed?).")

    conn.commit()
    print("  Database changes committed.")


def is_effectively_empty(directory: Path) -> bool:
    """Return True if the directory contains only hidden files/dirs or is empty."""
    for item in directory.iterdir():
        if not item.name.startswith("."):
            if item.is_dir():
                if not is_effectively_empty(item):
                    return False
            else:
                return False
    return True


def apply_filesystem_moves(plan: list[AlbumMigration], archive: Path, source_model: str) -> None:
    print("\n--- Filesystem operations ---")
    errors: list[str] = []

    for m in plan:
        src = archive / m.current_path
        dst = archive / m.new_path

        if not src.exists():
            msg = f"SKIP (source not found on disk): {src}"
            print(f"  !! {msg}")
            errors.append(msg)
            continue

        if dst.exists():
            msg = f"SKIP (destination already exists): {dst}"
            print(f"  !! {msg}")
            errors.append(msg)
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dst))
            print(f"  MOVED: {m.current_path}")
            print(f"      → {m.new_path}")
        except OSError as exc:
            msg = f"FAILED to move {src} → {dst}: {exc}"
            print(f"  !! {msg}")
            errors.append(msg)

    # Remove empty source model directory
    source_letter = model_letter(source_model)
    source_dir = archive / source_letter / source_model
    if source_dir.exists():
        if is_effectively_empty(source_dir):
            shutil.rmtree(str(source_dir))
            print(f"\n  Removed empty source directory: {source_dir}")
        else:
            print(f"\n  ⚠ Source directory is NOT empty, left in place: {source_dir}")

    if errors:
        print(f"\n  Completed with {len(errors)} error(s):")
        for e in errors:
            print(f"    {e}")
    else:
        print("\n  All filesystem moves completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge a source model into a target model (DB + filesystem)."
    )
    parser.add_argument("--source", required=True, help="Model name/id to merge FROM (will be deleted)")
    parser.add_argument("--target", required=True, help="Model name/id to merge INTO (kept)")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to Curator SQLite database (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=DEFAULT_ARCHIVE,
        help=f"Path to Archive root (default: {DEFAULT_ARCHIVE})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute the plan (default is dry-run / plan display only)",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERROR: Database not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(args.db))

    source_ref = resolve_entity_ref(conn, "model", args.source)
    target_ref = resolve_entity_ref(conn, "model", args.target)
    if not source_ref:
        print(f"ERROR: Source model '{args.source}' not found by id or name.", file=sys.stderr)
        conn.close()
        sys.exit(1)
    if not target_ref:
        print(f"ERROR: Target model '{args.target}' not found by id or name.", file=sys.stderr)
        conn.close()
        sys.exit(1)
    if source_ref.row_id == target_ref.row_id:
        print("ERROR: Source and target resolve to the same model.", file=sys.stderr)
        conn.close()
        sys.exit(1)

    source_model_id = source_ref.row_id
    target_model_id = target_ref.row_id
    source_model = source_ref.name
    target_model = target_ref.name

    if args.source.strip() != source_model:
        print(f"Resolved source '{args.source}' -> id={source_model_id}, name='{source_model}'")
    if args.target.strip() != target_model:
        print(f"Resolved target '{args.target}' -> id={target_model_id}, name='{target_model}'")

    plan = build_migration_plan(conn, source_model, target_model, args.archive)

    if not plan:
        print(f"No albums found for model '{source_model}'. Nothing to do.")
        conn.close()
        return

    print_plan(plan, source_model, target_model)

    if not args.apply:
        print("Dry-run complete. Add --apply to execute the plan.")
        conn.close()
        return

    print("--- Applying database changes ---")
    apply_db_changes(conn, plan, source_model_id, source_model, target_model)
    apply_filesystem_moves(plan, args.archive, source_model)

    conn.close()


if __name__ == "__main__":
    main()
