from __future__ import annotations

from pathlib import Path
from typing import List

from .types import Violation

RULE_ID = "rule003"
ALLOWED_MEDIA_DIRS = {"p", "v"}


def _is_ignored(path: Path) -> bool:
    return path.name.startswith(".")


def validate(model_dir: Path, expected_letter: str) -> List[Violation]:
    del expected_letter

    violations: List[Violation] = []
    model_name = model_dir.name

    media_dirs = [
        p
        for p in model_dir.iterdir()
        if p.is_dir() and not _is_ignored(p) and p.name in ALLOWED_MEDIA_DIRS
    ]

    for media_dir in sorted(media_dirs, key=lambda p: p.name):
        media_children = [p for p in media_dir.iterdir() if not _is_ignored(p)]
        studio_dirs = [p for p in media_children if p.is_dir()]
        media_files = [p for p in media_children if p.is_file()]

        if media_files:
            violations.append(
                Violation(
                    RULE_ID,
                    f"{media_dir.name} folder contains files; only studio folders are allowed",
                )
            )

        if not studio_dirs:
            violations.append(Violation(RULE_ID, f"{media_dir.name} folder has no studio folders"))
            continue

        expected_prefix = f"{model_name} in "
        for studio_dir in studio_dirs:
            if not studio_dir.name.startswith(expected_prefix):
                violations.append(Violation(RULE_ID, f"studio folder naming invalid: {studio_dir.name}"))
                continue

            studio_name = studio_dir.name[len(expected_prefix) :].strip()
            if not studio_name:
                violations.append(Violation(RULE_ID, f"studio name is empty in folder: {studio_dir.name}"))

    return violations
