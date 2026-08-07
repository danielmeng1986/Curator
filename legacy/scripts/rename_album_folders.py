#!/usr/bin/env python3
"""Rename album folders by removing '<model_name> in ' prefix when pattern matches.

Rules:
- Under p/: rename '<model_name> in <album_name>' -> '<album_name>'
- Under v/: rename '<model_name> in <album_name> (year)' -> '<album_name> (year)'
- Non-matching folder names are left unchanged.

Dry-run by default; pass --apply to actually rename.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DEFAULT_ARCHIVE = Path("/Volumes/NAS-RAID5/RAID/Prime_Media/Archive")
LETTER_FOLDERS = {chr(i) for i in range(ord("A"), ord("Z") + 1)}
MEDIA_DIRS = {"p", "v"}
YEAR_SUFFIX_RE = re.compile(r"^.+\s\((\d{4})\)$")


def is_ignored(path: Path) -> bool:
    return path.name.startswith(".")


def extract_new_name(media_kind: str, model_name: str, folder_name: str) -> str | None:
    """Return new folder name if matched; otherwise None."""
    prefix = f"{model_name} in "
    if not folder_name.startswith(prefix):
        return None

    remainder = folder_name[len(prefix):].strip()
    if not remainder:
        return None

    if media_kind == "p":
        # p rule: anything after '<model> in ' is album name.
        return remainder

    if media_kind == "v":
        # v rule: only rename when remainder ends with ' (year)'.
        if YEAR_SUFFIX_RE.match(remainder):
            return remainder
        return None

    return None


def collect_renames(archive_root: Path) -> list[tuple[Path, Path]]:
    """Return list of (src, dst) rename pairs.

    Expected structure after studio normalization:
      Archive/{Letter}/{model}/p|v/{studio}/{album}
    """
    renames: list[tuple[Path, Path]] = []

    for letter_dir in sorted(p for p in archive_root.iterdir() if p.is_dir() and not is_ignored(p)):
        if letter_dir.name not in LETTER_FOLDERS or len(letter_dir.name) != 1:
            continue

        for model_dir in sorted(p for p in letter_dir.iterdir() if p.is_dir() and not is_ignored(p)):
            model_name = model_dir.name.strip()
            if not model_name:
                continue

            for media_dir in sorted(
                p for p in model_dir.iterdir()
                if p.is_dir() and not is_ignored(p) and p.name in MEDIA_DIRS
            ):
                media_kind = media_dir.name

                for studio_dir in sorted(p for p in media_dir.iterdir() if p.is_dir() and not is_ignored(p)):
                    for album_dir in sorted(p for p in studio_dir.iterdir() if p.is_dir() and not is_ignored(p)):
                        new_name = extract_new_name(
                            media_kind=media_kind,
                            model_name=model_name,
                            folder_name=album_dir.name,
                        )
                        if not new_name:
                            continue

                        dst = album_dir.parent / new_name
                        if album_dir != dst:
                            renames.append((album_dir, dst))

    return renames


def main() -> None:
    parser = argparse.ArgumentParser(description="Rename album folders based on naming rules under p/v.")
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
