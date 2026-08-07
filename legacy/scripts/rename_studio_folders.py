#!/usr/bin/env python3
"""Rename studio folders from '<model_name> in <studio_name>' to '<studio_name>'.

Archive structure:
  Archive/{Letter}/{model_name}/p|v/{model_name} in {studio_name}/

Dry-run by default; pass --apply to actually rename.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_ARCHIVE = Path("/Volumes/NAS-RAID5/RAID/Prime_Media/Archive")
LETTER_FOLDERS = {chr(i) for i in range(ord("A"), ord("Z") + 1)}
MEDIA_DIRS = {"p", "v"}


def is_ignored(path: Path) -> bool:
    return path.name.startswith(".")


def collect_renames(archive_root: Path) -> list[tuple[Path, Path]]:
    """Return list of (src, dst) pairs that need renaming."""
    renames: list[tuple[Path, Path]] = []

    for letter_dir in sorted(p for p in archive_root.iterdir() if p.is_dir() and not is_ignored(p)):
        if letter_dir.name not in LETTER_FOLDERS or len(letter_dir.name) != 1:
            continue

        for model_dir in sorted(p for p in letter_dir.iterdir() if p.is_dir() and not is_ignored(p)):
            model_name = model_dir.name.strip()
            if not model_name:
                continue

            expected_prefix = f"{model_name} in "

            for media_dir in sorted(
                p for p in model_dir.iterdir()
                if p.is_dir() and not is_ignored(p) and p.name in MEDIA_DIRS
            ):
                for studio_dir in sorted(p for p in media_dir.iterdir() if p.is_dir() and not is_ignored(p)):
                    folder_name = studio_dir.name

                    if not folder_name.startswith(expected_prefix):
                        continue

                    studio_name = folder_name[len(expected_prefix):].strip()
                    if not studio_name:
                        continue

                    dst = studio_dir.parent / studio_name
                    if studio_dir != dst:
                        renames.append((studio_dir, dst))

    return renames


def main() -> None:
    parser = argparse.ArgumentParser(description="Rename studio folders to remove '<model_name> in ' prefix.")
    parser.add_argument(
        "--archive",
        type=Path,
        default=DEFAULT_ARCHIVE,
        help=f"Path to Archive root (default: {DEFAULT_ARCHIVE})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually rename folders (default is dry-run only)",
    )
    args = parser.parse_args()

    if not args.archive.exists() or not args.archive.is_dir():
        print(f"ERROR: Archive path does not exist or is not a folder: {args.archive}", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning: {args.archive}")
    renames = collect_renames(args.archive)

    if not renames:
        print("No folders to rename.")
        return

    mode_label = "APPLY" if args.apply else "DRY-RUN"
    print(f"\n[{mode_label}] {len(renames)} folder(s) to rename:\n")

    errors: list[str] = []
    renamed = 0

    for src, dst in renames:
        print(f"  {src.relative_to(args.archive)}")
        print(f"    -> {dst.relative_to(args.archive)}")

        if args.apply:
            if dst.exists():
                msg = f"SKIP (target already exists): {dst}"
                print(f"    !! {msg}")
                errors.append(msg)
                continue
            try:
                src.rename(dst)
                renamed += 1
            except OSError as exc:
                msg = f"FAILED to rename {src} -> {dst}: {exc}"
                print(f"    !! {msg}")
                errors.append(msg)

    print()
    if args.apply:
        print(f"Done. Renamed: {renamed}, Skipped/Failed: {len(errors)}")
    else:
        print("Dry-run complete. Run with --apply to perform the renames.")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
