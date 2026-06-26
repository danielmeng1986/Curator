#!/usr/bin/env python3
"""Validate DAM archive folder structure and print non-compliant model paths.

Rules validated:
1. First level must be A-Z folder and model name should match first letter folder.
2. Model folder can contain only up to two folders: p and/or v.
3. Studio folder naming must follow: "<Model-Name> in <Studio Name>".
4. Under p-studio there should be album folders (4th level). Under v-studio,
   files and/or folders are allowed, but studio should not be empty.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List

try:
    from rules import RULE_VALIDATORS, Violation, invalid_first_level_violation
except ModuleNotFoundError:
    from scripts.rules import RULE_VALIDATORS, Violation, invalid_first_level_violation

DEFAULT_ARCHIVE = Path("/Volumes/NAS-RAID5/RAID/Prime_Media/Archive")
LETTER_FOLDERS = {chr(i) for i in range(ord("A"), ord("Z") + 1)}


def is_ignored(path: Path) -> bool:
    """Ignore hidden/system entries such as .DS_Store."""
    return path.name.startswith(".")


def format_output_path(path: Path, archive_root: Path) -> str:
    """Return a path string without DEFAULT_ARCHIVE/root prefix when possible."""
    resolved_path = path.resolve()
    candidate_roots = [DEFAULT_ARCHIVE.resolve(), archive_root.resolve()]

    for root in candidate_roots:
        try:
            return str(resolved_path.relative_to(root))
        except ValueError:
            continue

    return str(resolved_path)


def collect_invalid_models(archive_root: Path, show_progress: bool = True) -> Dict[Path, List[Violation]]:
    invalid: Dict[Path, List[Violation]] = {}

    if not archive_root.exists() or not archive_root.is_dir():
        raise FileNotFoundError(f"Archive path does not exist or is not a folder: {archive_root}")

    first_level_dirs = [p for p in archive_root.iterdir() if p.is_dir() and not is_ignored(p)]

    for letter_dir in first_level_dirs:
        if letter_dir.name in LETTER_FOLDERS and len(letter_dir.name) == 1:
            model_dirs = [p for p in letter_dir.iterdir() if p.is_dir() and not is_ignored(p)]
            for model_dir in model_dirs:
                if show_progress:
                    print(f"[SCAN] {model_dir}")
                violations: List[Violation] = []
                for rule_validator in RULE_VALIDATORS:
                    violations.extend(rule_validator(model_dir, letter_dir.name))
                if violations:
                    invalid[model_dir] = violations
            continue

        # Non A-Z first-level folder: mark all second-level model folders as invalid.
        model_dirs = [p for p in letter_dir.iterdir() if p.is_dir() and not is_ignored(p)]
        for model_dir in model_dirs:
            if show_progress:
                print(f"[SCAN] {model_dir}")
            invalid[model_dir] = [invalid_first_level_violation(letter_dir.name)]

    return invalid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate DAM archive structure and print invalid model-level paths."
    )
    parser.add_argument(
        "archive",
        nargs="?",
        default=str(DEFAULT_ARCHIVE),
        help=f"Archive root path (default: {DEFAULT_ARCHIVE})",
    )
    parser.add_argument(
        "--with-reasons",
        action="store_true",
        help="Print validation reasons for each invalid model folder.",
    )
    parser.add_argument(
        "--output",
        default="outputs/invalid_model_paths.txt",
        help="Output file path for invalid model folder list (default: outputs/invalid_model_paths.txt)",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable scan progress output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_root = Path(args.archive).expanduser().resolve()
    output_file = Path(args.output).expanduser().resolve()

    try:
        invalid = collect_invalid_models(archive_root, show_progress=not args.no_progress)
    except FileNotFoundError as exc:
        print(exc)
        return 2

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        if args.with_reasons:
            for index, model_path in enumerate(sorted(invalid.keys()), start=1):
                display_path = format_output_path(model_path, archive_root)
                f.write(f"{index}. {display_path}\n\n")
                violations = sorted(
                    {(v.rule_id, v.message) for v in invalid[model_path]},
                    key=lambda item: (item[0], item[1]),
                )
                for rule_id, message in violations:
                    f.write(f"- {rule_id}: {message}\n")
                f.write("\n")
        else:
            f.write("model_path\trules\n")
            for model_path in sorted(invalid.keys()):
                display_path = format_output_path(model_path, archive_root)
                rule_ids = sorted({v.rule_id for v in invalid[model_path]})
                f.write(f"{display_path}\t{','.join(rule_ids)}\n")

    print(f"[INFO] Invalid model path list written to: {output_file}")

    if not invalid:
        return 0

    if args.with_reasons:
        for index, model_path in enumerate(sorted(invalid.keys()), start=1):
            display_path = format_output_path(model_path, archive_root)
            print(f"{index}. {display_path}")
            print()
            for violation in sorted(
                {(v.rule_id, v.message) for v in invalid[model_path]},
                key=lambda item: (item[0], item[1]),
            ):
                print(f"- {violation[0]}: {violation[1]}")
            print()
    else:
        print("model_path\trules")
        for model_path in sorted(invalid.keys()):
            display_path = format_output_path(model_path, archive_root)
            rule_ids = sorted({v.rule_id for v in invalid[model_path]})
            print(f"{display_path}\t{','.join(rule_ids)}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
