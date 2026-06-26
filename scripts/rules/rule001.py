from __future__ import annotations

from pathlib import Path
from typing import List

from .types import Violation

RULE_ID = "rule001"


def first_letter(name: str) -> str:
    for ch in name:
        if ch.isalpha():
            return ch.upper()
    return ""


def validate(model_dir: Path, expected_letter: str) -> List[Violation]:
    if first_letter(model_dir.name) != expected_letter:
        return [Violation(RULE_ID, "model name does not match first-letter folder")]
    return []


def invalid_first_level_violation(letter_dir_name: str) -> Violation:
    return Violation(RULE_ID, f"first-level folder is not A-Z: {letter_dir_name}")
