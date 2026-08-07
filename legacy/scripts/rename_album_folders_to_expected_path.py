#!/usr/bin/env python3
"""Rename album folders from current_path to expected_path in batch.

Rules:
- Select rows where current_path != expected_path and expected_path is not empty.
- Rename folder under Archive from current_path to expected_path.
- Dry-run by default; pass --apply to actually rename.
- After apply, rescan archive paths using the same p-scan structure as
  import_workspace_albums_to_db.py and verify each renamed row.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3


DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
DEFAULT_ARCHIVE = Path("/Volumes/NAS-RAID5/RAID/Prime_Media/Archive")
DEFAULT_LOG_DIR = Path(__file__).resolve().parents[1] / "outputs"

LETTER_FOLDERS = {chr(i) for i in range(ord("A"), ord("Z") + 1)}


@dataclass(frozen=True)
class RenameJob:
    row_id: int
    current_path: str
    expected_path: str


@dataclass(frozen=True)
class RenameResult:
    job: RenameJob
    success: bool
    message: str


def is_ignored(path: Path) -> bool:
    return path.name.startswith(".")


def rel_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def resolve_archive_root(scan_root: Path) -> Path:
    resolved = scan_root.resolve()
    for candidate in (resolved, *resolved.parents):
        if candidate.name == "Archive":
            return candidate
    return resolved


def normalize_text(value: str | None) -> str:
    return (value or "").strip()


def load_rename_jobs(conn: sqlite3.Connection) -> list[RenameJob]:
    rows = conn.execute(
        """
        SELECT id, current_path, expected_path
        FROM workspace_album
        WHERE expected_path IS NOT NULL
          AND TRIM(expected_path) <> ''
          AND TRIM(current_path) <> TRIM(expected_path)
        ORDER BY id
        """
    ).fetchall()

    return [
        RenameJob(
            row_id=int(row_id),
            current_path=normalize_text(current_path),
            expected_path=normalize_text(expected_path),
        )
        for row_id, current_path, expected_path in rows
        if normalize_text(current_path) and normalize_text(expected_path)
    ]


def iter_album_dirs(scan_root: Path, archive_root: Path):
    stack = [scan_root]

    while stack:
        current = stack.pop()
        if is_ignored(current):
            continue

        rel_parts = current.resolve().relative_to(archive_root.resolve()).parts
        if (
            len(rel_parts) == 5
            and rel_parts[0] in LETTER_FOLDERS
            and len(rel_parts[0]) == 1
            and rel_parts[2] == "p"
        ):
            yield current
            continue

        if len(rel_parts) >= 5:
            continue

        children = sorted(
            (child for child in current.iterdir() if child.is_dir() and not is_ignored(child)),
            reverse=True,
        )
        stack.extend(children)


def scan_current_paths(scan_root: Path) -> set[str]:
    archive_root = resolve_archive_root(scan_root)
    return {rel_path(album_dir, archive_root) for album_dir in iter_album_dirs(scan_root, archive_root)}


def build_log_path(log_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return log_dir / f"rename_album_to_expected_{timestamp}.log"


def ensure_within_archive(archive_root: Path, rel: str) -> Path:
    candidate = (archive_root / rel).resolve()
    archive_resolved = archive_root.resolve()
    if archive_resolved == candidate or archive_resolved in candidate.parents:
        return candidate
    raise ValueError(f"Path escapes archive root: {rel}")


def run_jobs(archive_root: Path, jobs: list[RenameJob], apply: bool) -> list[RenameResult]:
    results: list[RenameResult] = []

    for job in jobs:
        try:
            src = ensure_within_archive(archive_root, job.current_path)
            dst = ensure_within_archive(archive_root, job.expected_path)
        except ValueError as exc:
            results.append(RenameResult(job=job, success=False, message=str(exc)))
            continue

        if not src.exists() or not src.is_dir():
            results.append(RenameResult(job=job, success=False, message=f"Source folder not found: {src}"))
            continue

        if dst.exists():
            results.append(RenameResult(job=job, success=False, message=f"Target already exists: {dst}"))
            continue

        if not apply:
            results.append(RenameResult(job=job, success=True, message=f"PLAN {src} -> {dst}"))
            continue

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            results.append(RenameResult(job=job, success=True, message=f"RENAMED {src} -> {dst}"))
        except OSError as exc:
            results.append(RenameResult(job=job, success=False, message=f"FAILED {src} -> {dst}: {exc}"))

    return results


def mark_failed_rows_status(conn: sqlite3.Connection, failed_ids: list[int], status_id: int = 1) -> int:
    if not failed_ids:
        return 0
    conn.execute("BEGIN")
    conn.executemany(
        "UPDATE workspace_album SET status_id = ? WHERE id = ?",
        [(status_id, row_id) for row_id in failed_ids],
    )
    conn.commit()
    return len(failed_ids)


def verify_apply_result(scan_root: Path, jobs: list[RenameJob]) -> tuple[int, int, list[str]]:
    scanned_paths = scan_current_paths(scan_root)
    success_count = 0
    failed_details: list[str] = []

    for job in jobs:
        # Success criterion aligned with requirement:
        # after rescan, the effective current path equals expected_path.
        if job.expected_path in scanned_paths and job.current_path not in scanned_paths:
            success_count += 1
        else:
            failed_details.append(
                f"id={job.row_id}: current='{job.current_path}', expected='{job.expected_path}', "
                f"seen_current={'yes' if job.current_path in scanned_paths else 'no'}, "
                f"seen_expected={'yes' if job.expected_path in scanned_paths else 'no'}"
            )

    return success_count, len(jobs), failed_details


def write_log(log_path: Path, lines: list[str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rename Archive folders from current_path to expected_path."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})")
    parser.add_argument(
        "--archive",
        type=Path,
        default=DEFAULT_ARCHIVE,
        help=f"Archive root path (default: {DEFAULT_ARCHIVE})",
    )
    parser.add_argument("--apply", action="store_true", help="Actually rename folders")
    parser.add_argument("--preview", type=int, default=20, help="How many jobs to print (default: 20)")
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Optional log path. Default: outputs/rename_album_to_expected_<timestamp>.log",
    )
    args = parser.parse_args()

    if not args.archive.exists() or not args.archive.is_dir():
        print(f"ERROR: Archive path does not exist or is not a folder: {args.archive}", file=sys.stderr)
        return 2

    log_path = args.log if args.log else build_log_path(DEFAULT_LOG_DIR)

    with sqlite3.connect(args.db) as conn:
        jobs = load_rename_jobs(conn)

    print(f"Jobs found (current_path != expected_path): {len(jobs)}")
    if not jobs:
        print("No rename needed.")
        write_log(log_path, ["No rename jobs found."])
        print(f"Log written: {log_path}")
        return 0

    for job in jobs[: max(args.preview, 0)]:
        print(f"[id={job.row_id}] {job.current_path} -> {job.expected_path}")

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"Mode: {mode}")

    results = run_jobs(args.archive.resolve(), jobs, apply=args.apply)
    ok_count = sum(1 for r in results if r.success)
    fail_count = len(results) - ok_count
    failed_ids = [r.job.row_id for r in results if not r.success]

    log_lines = [
        f"Mode: {mode}",
        f"Archive: {args.archive.resolve()}",
        f"DB: {args.db.resolve()}",
        f"Jobs: {len(jobs)}",
        f"Success: {ok_count}",
        f"Failed: {fail_count}",
        "",
        "Details:",
    ]
    log_lines.extend(result.message for result in results)

    print(f"Run summary: success={ok_count}, failed={fail_count}")

    marked_count = 0
    if args.apply and failed_ids:
        with sqlite3.connect(args.db) as conn:
            marked_count = mark_failed_rows_status(conn, failed_ids, status_id=1)
        print(f"Failed rows status updated to 1: {marked_count}")
        log_lines.append(f"Failed rows status updated to 1: {marked_count}")

    if args.apply:
        # Only jobs that executed successfully are checked for final success.
        succeeded_jobs = [result.job for result in results if result.success]
        verify_ok, verify_total, verify_failed = verify_apply_result(args.archive.resolve(), succeeded_jobs)
        print(f"Verify summary: success={verify_ok}/{verify_total}")
        log_lines.append("")
        log_lines.append(f"Verify success: {verify_ok}/{verify_total}")
        if verify_failed:
            log_lines.append("Verify failed details:")
            log_lines.extend(verify_failed)

    write_log(log_path, log_lines)
    print(f"Log written: {log_path}")

    # Return non-zero on apply failures or verification failures.
    if args.apply:
        if fail_count > 0:
            return 1
        succeeded_jobs = [result.job for result in results if result.success]
        verify_ok, verify_total, _ = verify_apply_result(args.archive.resolve(), succeeded_jobs)
        if verify_ok != verify_total:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())