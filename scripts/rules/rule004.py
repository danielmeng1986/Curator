from __future__ import annotations

from pathlib import Path
from typing import List

from .types import Violation

RULE_ID = "rule004"
ALLOWED_MEDIA_DIRS = {"p", "v"}


def _is_ignored(path: Path) -> bool:
    return path.name.startswith(".")


def validate(model_dir: Path, expected_letter: str) -> List[Violation]:
    del expected_letter

    violations: List[Violation] = []

    media_dirs = [
        p
        for p in model_dir.iterdir()
        if p.is_dir() and not _is_ignored(p) and p.name in ALLOWED_MEDIA_DIRS
    ]

    for media_dir in sorted(media_dirs, key=lambda p: p.name):
        studio_dirs = [p for p in media_dir.iterdir() if p.is_dir() and not _is_ignored(p)]

        for studio_dir in studio_dirs:
            level4_children = [p for p in studio_dir.iterdir() if not _is_ignored(p)]
            if not level4_children:
                violations.append(Violation(RULE_ID, f"studio folder is empty: {studio_dir.name}"))
                continue

            if media_dir.name == "p":
                if any(p.is_file() for p in level4_children):
                    violations.append(Violation(RULE_ID, f"p-studio contains files directly: {studio_dir.name}"))
                if not any(p.is_dir() for p in level4_children):
                    violations.append(Violation(RULE_ID, f"p-studio has no album folders: {studio_dir.name}"))

    return violations
