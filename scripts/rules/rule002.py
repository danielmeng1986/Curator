from __future__ import annotations

from pathlib import Path
from typing import List

from .types import Violation

RULE_ID = "rule002"
ALLOWED_MEDIA_DIRS = {"p", "v"}


def _is_ignored(path: Path) -> bool:
    return path.name.startswith(".")


def validate(model_dir: Path, expected_letter: str) -> List[Violation]:
    del expected_letter

    violations: List[Violation] = []
    children = [p for p in model_dir.iterdir() if not _is_ignored(p)]
    dirs = [p for p in children if p.is_dir()]
    files = [p for p in children if p.is_file()]

    if files:
        violations.append(Violation(RULE_ID, "model folder contains files; only p/v folders are allowed"))

    if not dirs:
        violations.append(Violation(RULE_ID, "model folder is empty"))

    if len(dirs) > 2:
        violations.append(Violation(RULE_ID, "model folder contains more than two subfolders"))

    invalid_media_dirs = [d.name for d in dirs if d.name not in ALLOWED_MEDIA_DIRS]
    if invalid_media_dirs:
        violations.append(
            Violation(
                RULE_ID,
                f"model folder contains invalid subfolders: {', '.join(sorted(invalid_media_dirs))}",
            )
        )

    return violations
