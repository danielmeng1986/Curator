#!/usr/bin/env python3
"""Describe a workspace album by sampling images and calling llama.cpp.

Features:
- Input a workspace_album id and a requested sample count.
- Resolve album directory from workspace_album.current_path.
- Pick images with even sampling across the album.
- Re-select sampled images if their file sizes are outliers compared to the
  album average.
- Use llama.cpp multimodal model configured in config/ai.toml.
- Print a structured JSON result.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("Python 3.11+ is required (tomllib not available).") from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = REPO_ROOT / "database" / "Curator.db"
DEFAULT_AI_CONFIG = REPO_ROOT / "config" / "ai.toml"
DEFAULT_APP_CONFIG = REPO_ROOT / "workspace" / "curator_base_app" / "app_config.json"

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".heic",
}


@dataclass(frozen=True)
class AlbumRow:
    album_id: int
    current_path: str
    expected_path: str | None
    primary_model: str
    additional_models: str | None
    studio_name: str
    album_name: str


@dataclass(frozen=True)
class LlamaConfig:
    cli: Path
    model: Path | None
    mmproj: Path | None
    hf_repo: str | None
    hf_file: str | None


@dataclass(frozen=True)
class DescribeConfig:
    default_sample_count: int
    vision_prompt_template: str
    writer_prompt_template: str


@dataclass(frozen=True)
class LlamaRunResult:
    data: dict
    used_fallback: bool
    fallback_source: str | None
    raw_stdout: str
    raw_stderr: str


@dataclass(frozen=True)
class ResponseAdapterResult:
    data: dict
    defaulted_fields: list[str]


@dataclass(frozen=True)
class PipelineResult:
    vision: dict
    writer: dict
    final: dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sample album images by workspace_album id and generate structured JSON with llama.cpp."
    )
    parser.add_argument("album_id", type=int, help="workspace_album.id")
    parser.add_argument(
        "sample_count",
        nargs="?",
        type=int,
        default=None,
        help="Requested sample image count. Default: [describe_album].default_sample_count in ai.toml",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite DB path (default: {DEFAULT_DB})")
    parser.add_argument(
        "--ai-config",
        type=Path,
        default=DEFAULT_AI_CONFIG,
        help=f"AI config TOML path (default: {DEFAULT_AI_CONFIG})",
    )
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=None,
        help="Archive root used to resolve relative current_path. Default: read from app_config.json",
    )
    parser.add_argument(
        "--size-outlier-threshold",
        type=float,
        default=0.6,
        help="Outlier threshold by |size-avg|/avg (default: 0.6)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=800,
        help="Max generation tokens for llama-cli (default: 800)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Generation temperature for llama-cli (default: 0.2)",
    )
    parser.add_argument(
        "--image-max-tokens",
        type=int,
        default=384,
        help="Max vision tokens per image for llama-cli (default: 384)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print sampled image details to stderr",
    )
    parser.add_argument(
        "--ctx-size",
        type=int,
        default=None,
        help="Optional llama.cpp context size (-c)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help="Optional llama.cpp CPU threads (-t)",
    )
    parser.add_argument(
        "--gpu-layers",
        type=int,
        default=None,
        help="Optional llama.cpp GPU layers (--n-gpu-layers)",
    )
    parser.add_argument(
        "--output",
        nargs="?",
        const="auto",
        default=None,
        help=(
            "Write result JSON to outputs/. Optional value is a filename token "
            "(for example: --output s8)."
        ),
    )
    return parser.parse_args()


def read_archive_root(app_config_path: Path) -> Path | None:
    if not app_config_path.exists():
        return None
    try:
        raw = json.loads(app_config_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    value = raw.get("archive_root")
    if not isinstance(value, str) or not value.strip():
        return None
    return Path(value.strip())


def load_llama_config(ai_config_path: Path) -> LlamaConfig:
    if not ai_config_path.exists():
        raise FileNotFoundError(f"AI config not found: {ai_config_path}")

    parsed = tomllib.loads(ai_config_path.read_text(encoding="utf-8"))
    section = parsed.get("llama")
    if not isinstance(section, dict):
        raise ValueError(f"[llama] section missing in {ai_config_path}")

    def as_path(key: str) -> Path:
        value = section.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing [llama].{key} in {ai_config_path}")
        return Path(value.strip())

    def optional_path(key: str) -> Path | None:
        value = section.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            return None
        return Path(value.strip())

    def optional_str(key: str) -> str | None:
        value = section.get(key)
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            return None
        return value.strip()

    cfg = LlamaConfig(
        cli=as_path("cli"),
        model=optional_path("model"),
        mmproj=optional_path("mmproj"),
        hf_repo=optional_str("hf_repo"),
        hf_file=optional_str("hf_file"),
    )

    if (cfg.hf_repo is None) != (cfg.hf_file is None):
        raise ValueError(
            f"[llama].hf_repo and [llama].hf_file must both be set together in {ai_config_path}"
        )

    if cfg.hf_repo is None and cfg.model is None:
        raise ValueError(
            f"Either [llama].model or [llama].hf_repo + [llama].hf_file must be configured in {ai_config_path}"
        )

    for label, path in (("cli", cfg.cli), ("model", cfg.model), ("mmproj", cfg.mmproj)):
        if path is None:
            continue
        if not path.exists():
            raise FileNotFoundError(f"Configured {label} path does not exist: {path}")
    return cfg


def load_describe_config(ai_config_path: Path) -> DescribeConfig:
    parsed = tomllib.loads(ai_config_path.read_text(encoding="utf-8"))
    section = parsed.get("describe_album")
    if not isinstance(section, dict):
        raise ValueError(f"[describe_album] section missing in {ai_config_path}")

    sample_count = section.get("default_sample_count")
    if not isinstance(sample_count, int) or sample_count <= 0:
        raise ValueError(f"[describe_album].default_sample_count must be a positive integer in {ai_config_path}")

    vision_section = parsed.get("vision")
    if not isinstance(vision_section, dict):
        raise ValueError(f"[vision] section missing in {ai_config_path}")

    writer_section = parsed.get("writer")
    if not isinstance(writer_section, dict):
        raise ValueError(f"[writer] section missing in {ai_config_path}")

    vision_prompt = vision_section.get("prompt_template")
    if not isinstance(vision_prompt, str) or not vision_prompt.strip():
        raise ValueError(f"[vision].prompt_template must be a non-empty string in {ai_config_path}")

    writer_prompt = writer_section.get("prompt_template")
    if not isinstance(writer_prompt, str) or not writer_prompt.strip():
        raise ValueError(f"[writer].prompt_template must be a non-empty string in {ai_config_path}")

    return DescribeConfig(
        default_sample_count=sample_count,
        vision_prompt_template=vision_prompt.strip(),
        writer_prompt_template=writer_prompt.strip(),
    )


def load_album_row(conn: sqlite3.Connection, album_id: int) -> AlbumRow:
    row = conn.execute(
        """
        SELECT id, current_path, expected_path, primary_model, additional_models, studio_name, album_name
        FROM workspace_album
        WHERE id = ?
        """,
        (album_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"workspace_album id not found: {album_id}")

    return AlbumRow(
        album_id=int(row[0]),
        current_path=str(row[1]),
        expected_path=(str(row[2]) if row[2] is not None and str(row[2]).strip() else None),
        primary_model=str(row[3]),
        additional_models=(str(row[4]) if row[4] is not None and str(row[4]).strip() else None),
        studio_name=str(row[5]),
        album_name=str(row[6]),
    )


def resolve_candidates(path_value: str, archive_root: Path | None) -> list[Path]:
    raw = Path(path_value)
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)

    if archive_root is not None:
        candidates.append((archive_root / path_value).resolve())
        parts = list(Path(path_value).parts)
        if parts and parts[0] == archive_root.name:
            candidates.append((archive_root / Path(*parts[1:])).resolve())

    candidates.append((REPO_ROOT / path_value).resolve())

    # Preserve order while removing duplicates.
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def resolve_album_dir(current_path: str, expected_path: str | None, archive_root: Path | None) -> Path:
    paths_to_try: list[tuple[str, str]] = [("current_path", current_path)]
    if expected_path and expected_path != current_path:
        paths_to_try.append(("expected_path", expected_path))

    all_tried: list[tuple[str, Path]] = []
    for source, path_value in paths_to_try:
        for candidate in resolve_candidates(path_value, archive_root):
            all_tried.append((source, candidate))
            if candidate.exists() and candidate.is_dir():
                return candidate

    tried = "\n".join(f"- [{source}] {path}" for source, path in all_tried)
    raise FileNotFoundError(
        "Unable to resolve album directory. Tried:\n"
        f"{tried}\n"
        f"current_path={current_path!r}, expected_path={expected_path!r}"
    )


def list_images(album_dir: Path) -> list[Path]:
    images = [
        path
        for path in sorted(album_dir.rglob("*"))
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    if not images:
        raise ValueError(f"No image files found in album directory: {album_dir}")
    return images


def even_target_indexes(total: int, count: int) -> list[int]:
    if count <= 0:
        raise ValueError("sample_count must be >= 1")
    if total <= 0:
        return []
    count = min(count, total)
    if count == 1:
        return [0]

    # Inclusive endpoints (first and last images are always considered).
    idx = [round(i * (total - 1) / (count - 1)) for i in range(count)]

    # Guarantee uniqueness/monotonicity for small totals.
    out: list[int] = []
    seen: set[int] = set()
    for value in idx:
        value = min(max(value, 0), total - 1)
        if value in seen:
            continue
        seen.add(value)
        out.append(value)

    next_candidate = 0
    while len(out) < count:
        while next_candidate in seen and next_candidate < total:
            next_candidate += 1
        if next_candidate >= total:
            break
        seen.add(next_candidate)
        out.append(next_candidate)

    return sorted(out)


def pick_with_resample(
    image_paths: list[Path],
    count: int,
    outlier_threshold: float,
) -> list[Path]:
    sizes = [path.stat().st_size for path in image_paths]
    avg_size = sum(sizes) / max(len(sizes), 1)
    if avg_size <= 0:
        return [image_paths[i] for i in even_target_indexes(len(image_paths), count)]

    targets = even_target_indexes(len(image_paths), count)
    chosen: list[int] = []
    used: set[int] = set()

    for target in targets:
        selected = None
        max_delta = max(target, len(image_paths) - 1 - target)

        for delta in range(0, max_delta + 1):
            for sign in (0, -1, 1):
                if sign == 0 and delta != 0:
                    continue
                idx = target if sign == 0 else target + sign * delta
                if idx < 0 or idx >= len(image_paths) or idx in used:
                    continue

                ratio = abs(sizes[idx] - avg_size) / avg_size
                if ratio <= outlier_threshold:
                    selected = idx
                    break
            if selected is not None:
                break

        if selected is None:
            best_idx = None
            best_dist = math.inf
            for idx in range(len(image_paths)):
                if idx in used:
                    continue
                dist = abs(idx - target)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
            if best_idx is None:
                continue
            selected = best_idx

        used.add(selected)
        chosen.append(selected)

    chosen = sorted(chosen)
    return [image_paths[i] for i in chosen]


def base_prompt_replacements(album: AlbumRow) -> dict[str, str]:
    return {
        "__ALBUM_ID__": str(album.album_id),
        "__STUDIO_NAME__": album.studio_name,
        "__PRIMARY_MODEL__": album.primary_model,
        "__ADDITIONAL_MODELS__": album.additional_models or "none",
        "__ALBUM_NAME__": album.album_name,
    }


def apply_prompt_replacements(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def build_vision_prompt(album: AlbumRow, template: str) -> str:
    schema = {
        "scene": "...",
        "subjects": ["..."],
        "objects": ["..."],
        "actions": ["..."],
        "lighting": "...",
        "environment": "...",
        "summary": "...",
        "confidence": 0.92,
    }
    replacements = base_prompt_replacements(album)
    replacements["__SCHEMA_EXAMPLE__"] = json.dumps(schema, ensure_ascii=True)
    return apply_prompt_replacements(template, replacements)


def build_writer_prompt(album: AlbumRow, vision_data: dict, template: str) -> str:
    schema = {
        "album_summary": "...",
        "description": "...",
        "suggested_names": ["...", "...", "..."],
    }
    replacements = base_prompt_replacements(album)
    replacements["__VISION_JSON__"] = json.dumps(vision_data, ensure_ascii=False)
    replacements["__SCHEMA_EXAMPLE__"] = json.dumps(schema, ensure_ascii=True)
    return apply_prompt_replacements(template, replacements)


def split_additional_models(value: str | None) -> list[str]:
    if value is None:
        return []
    parts = re.split(r"[,;/|]+", value)
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        name = part.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def model_names(album: AlbumRow) -> list[str]:
    names = [album.primary_model.strip()] + split_additional_models(album.additional_models)
    out: list[str] = []
    seen: set[str] = set()
    for name in names:
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def human_join(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def first_name(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    return parts[0] if parts else ""


def dedupe_keep_order(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(value.strip())
    return out


def remove_model_names_from_summary(summary: str, album: AlbumRow) -> str:
    fixed = summary
    for name in model_names(album):
        fixed = re.sub(re.escape(name), "the model", fixed, flags=re.IGNORECASE)
    fixed = re.sub(r"\s+", " ", fixed).strip()
    return fixed


def normalize_list_field(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        parsed = parse_list_like(raw)
        if parsed:
            return parsed
    return []


def normalize_actions_lightweight(actions: list[str]) -> list[str]:
    canonical_order: list[str] = []
    canonical_map: dict[str, str] = {}

    def canonicalize(action: str) -> str:
        text = action.strip().lower()
        text = re.sub(r"[_\-]+", " ", text)
        text = re.sub(r"\s+", " ", text)

        # Light clustering only: keep broad meaning, merge obvious variants.
        if "walk" in text:
            return "walking"
        if "sit" in text or "seated" in text:
            return "sitting"
        if "kneel" in text:
            return "kneeling"
        if "stand" in text:
            return "standing"
        if "lean" in text:
            return "leaning"
        if "lie" in text or "lay" in text:
            return "lying"
        if "floor" in text:
            return "floor posing"
        if "sink" in text:
            return "sink posing"
        if "bathtub" in text or "tub" in text:
            return "bathtub posing"
        if "pose" in text:
            return "posing"

        words = re.findall(r"[a-z0-9]+", text)
        return " ".join(words[:3]) if words else "posing"

    for action in actions:
        if not action.strip():
            continue
        key = canonicalize(action)
        if key not in canonical_map:
            canonical_map[key] = key
            canonical_order.append(key)

    return canonical_order


def to_title_words(value: str) -> str:
    if not value:
        return ""
    text = re.sub(r"([A-Za-z])'s\b", r"\1", value)
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    words = re.findall(r"[A-Za-z0-9]+", text)
    if not words:
        return ""
    return " ".join(word[:1].upper() + word[1:].lower() for word in words)


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", text))


def limit_title_words(text: str, max_words: int = 5) -> str:
    words = re.findall(r"[A-Za-z0-9]+", to_title_words(text))
    if not words:
        return ""
    return " ".join(words[:max_words])


def model_full_names_lower(album: AlbumRow) -> set[str]:
    return {to_title_words(name).lower() for name in model_names(album) if name.strip()}


def model_name_present(description: str, name: str) -> bool:
    full = to_title_words(name)
    first = to_title_words(first_name(name))
    d = description.lower()
    return (full and full.lower() in d) or (first and first.lower() in d)


def parse_float_like(raw: object, default: float = 0.5) -> float:
    if isinstance(raw, (int, float)):
        value = float(raw)
    elif isinstance(raw, str):
        m = re.search(r"[-+]?\d*\.?\d+", raw.strip())
        value = float(m.group(0)) if m else default
    else:
        value = default
    return min(max(value, 0.0), 1.0)


def ensure_exact_count(values: list[str], count: int, fillers: list[str]) -> list[str]:
    out = dedupe_keep_order(values)
    seen_lower = {v.lower() for v in out}
    for filler in fillers:
        if len(out) >= count:
            break
        key = filler.strip().lower()
        if not key or key in seen_lower:
            continue
        out.append(filler)
        seen_lower.add(key)
    return out[:count]


def build_writer_name_fillers(album: AlbumRow, vision: dict) -> list[str]:
    scene = limit_title_words(str(vision.get("scene", "")), 4)
    environment = limit_title_words(str(vision.get("environment", "")), 4)
    studio = to_title_words(album.studio_name)
    album_name = to_title_words(album.album_name)
    primary_first = to_title_words(first_name(album.primary_model))
    primary_full = to_title_words(album.primary_model)
    base = [
        scene,
        environment,
        studio,
        album_name,
        f"{primary_first} {environment}" if primary_first and environment else "",
        f"{primary_full} {environment}" if primary_full and environment else "",
        f"{studio} {album_name}",
        to_title_words(f"{studio} {album_name}"),
        "Curated Album",
        "Curated Series",
        "Modern Indoor Set",
        "Studio Pose Series",
    ]
    out: list[str] = []
    for item in base:
        v = limit_title_words(item, 5)
        if not v:
            continue
        wc = word_count(v)
        if wc < 2 or wc > 5:
            continue
        out.append(v)
    return dedupe_keep_order(out)


def build_description_fallback(album: AlbumRow, vision: dict) -> str:
    names_text = human_join(model_names(album)) or "the model"
    scene_text = str(vision.get("scene", "")).strip().rstrip(".")
    environment_text = str(vision.get("environment", "")).strip().rstrip(".")
    summary_text = str(vision.get("summary", "")).strip().rstrip(".")
    core = scene_text or environment_text or "a curated indoor setting"
    if summary_text:
        return f"{names_text} is featured in {core.lower()}, with {summary_text.lower()}."
    return f"{names_text} is featured in {core.lower()}, with consistent posing and visual continuity across the album."


def ensure_description_has_model_names(description: str, album: AlbumRow) -> str:
    text = description.strip()
    names = model_names(album)
    names_text = human_join(names)
    if not text:
        return text
    if not names_text:
        return text
    if text and all(model_name_present(text, name) for name in names):
        return text
    replacements = [
        r"(?i)^\s*(?:a|an)\s+nude\s+female\s+model\s+",
        r"(?i)^\s*(?:a|an)\s+female\s+model\s+",
        r"(?i)^\s*(?:a|an)\s+nude\s+model\s+",
        r"(?i)^\s*(?:a|an)\s+model\s+",
        r"(?i)^\s*the\s+model\s+",
        r"(?i)^\s*one\s+adult\s+woman\s+",
    ]
    for pattern in replacements:
        replaced = re.sub(pattern, names_text + " ", text, count=1)
        if replaced != text:
            merged = replaced.strip()
            if all(model_name_present(merged, name) for name in names):
                return merged

    # Force names as sentence subject when replacement is not possible.
    if text:
        merged = f"{names_text} {text[0].lower() + text[1:] if len(text) > 1 else text.lower()}"
        merged = re.sub(r"\s+", " ", merged).strip()
        return merged
    return f"{names_text} is featured in a curated indoor set."


def normalize_writer_suggested_names(raw_values: list[str], album: AlbumRow, fillers: list[str]) -> tuple[list[str], bool]:
    full_names = model_full_names_lower(album)
    banned_words = {"photo", "photos", "collection", "session", "gallery"}
    values: list[str] = []

    def accept(name: str) -> None:
        n = limit_title_words(name, 5)
        if not n:
            return
        wc = word_count(n)
        if wc < 2 or wc > 5:
            return
        if n.lower() in full_names:
            return
        tokens_lower = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", n)}
        if tokens_lower & banned_words:
            return
        values.append(n)

    for item in raw_values:
        accept(item)

    raw_valid = len(dedupe_keep_order(values)) >= 6

    for item in fillers:
        if len(dedupe_keep_order(values)) >= 6:
            break
        accept(item)

    final = ensure_exact_count(dedupe_keep_order(values), 6, fillers)
    # Final strict pass for constraints.
    final = [x for x in final if 2 <= word_count(x) <= 5 and x.lower() not in full_names]
    final = ensure_exact_count(dedupe_keep_order(final), 6, fillers)
    return final, raw_valid


def vision_response_adapter(raw_data: dict, album: AlbumRow) -> ResponseAdapterResult:
    defaulted: list[str] = []
    out = dict(raw_data)

    scene = str(out.get("scene", "")).strip()
    if not scene:
        scene = "Indoor studio environment with recurring visual elements."
        defaulted.append("scene")

    subjects = dedupe_keep_order(normalize_list_field(out.get("subjects")))
    if not subjects:
        subjects = ["one adult model"]
        defaulted.append("subjects")

    objects = dedupe_keep_order(normalize_list_field(out.get("objects")))
    if not objects:
        objects = ["indoor setting"]
        defaulted.append("objects")

    actions = dedupe_keep_order(normalize_list_field(out.get("actions")))
    actions = normalize_actions_lightweight(actions)
    if not actions:
        actions = ["posing"]
        defaulted.append("actions")

    lighting = str(out.get("lighting", "")).strip()
    if not lighting:
        lighting = "Natural indoor lighting."
        defaulted.append("lighting")

    environment = str(out.get("environment", "")).strip()
    if not environment:
        environment = "Indoor environment with recurring visual elements."
        defaulted.append("environment")

    summary = str(out.get("summary", "")).strip()
    if not summary:
        summary = "Recurring indoor poses with a consistent visual theme across the album."
        defaulted.append("summary")

    confidence_raw = out.get("confidence")
    confidence = parse_float_like(confidence_raw, 0.5)
    if confidence_raw is None:
        defaulted.append("confidence")

    final = {
        "scene": scene,
        "subjects": subjects,
        "objects": objects,
        "actions": actions,
        "lighting": lighting,
        "environment": environment,
        "summary": summary,
        "confidence": confidence,
    }
    return ResponseAdapterResult(data=final, defaulted_fields=dedupe_keep_order(defaulted))


def writer_response_adapter(raw_data: dict, album: AlbumRow, vision_data: dict) -> ResponseAdapterResult:
    defaulted: list[str] = []
    out = dict(raw_data)

    album_summary = str(out.get("album_summary", "")).strip()
    if not album_summary:
        album_summary = str(vision_data.get("summary", "")).strip()
    if not album_summary:
        album_summary = "A cohesive album set featuring recurring posing in a consistent indoor environment."
        defaulted.append("album_summary")
    album_summary = remove_model_names_from_summary(album_summary, album)

    description = str(out.get("description", "")).strip()
    if not description:
        description = build_description_fallback(album, vision_data)
        defaulted.append("description")
    description = ensure_description_has_model_names(description, album)

    raw_names = normalize_list_field(out.get("suggested_names"))
    fillers = build_writer_name_fillers(album, vision_data)
    suggested_names, raw_valid = normalize_writer_suggested_names(raw_names, album, fillers)
    if not raw_valid:
        defaulted.append("suggested_names")

    final = {
        "album_summary": album_summary,
        "description": description,
        "suggested_names": suggested_names,
    }
    return ResponseAdapterResult(data=final, defaulted_fields=dedupe_keep_order(defaulted))


def try_parse_json_candidate(candidate: str, list_keys: set[str] | None = None) -> dict | None:
    list_keys = list_keys or set()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    repaired = candidate
    for key in list_keys:
        # Some model outputs wrap JSON arrays as a quoted string like:
        # "subjects": "[\"one adult woman\"]"
        pattern = rf'("{key}"\s*:\s*)"\[(.*?)\]"'
        repaired = re.sub(pattern, r"\1[\2]", repaired, flags=re.DOTALL)

    if repaired != candidate:
        try:
            parsed = json.loads(repaired)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed

    return None


def strip_terminal_control_sequences(text: str) -> str:
    # Remove ANSI CSI sequences, e.g. "\x1b[31m".
    text = re.sub(r"\x1B\[[0-?]*[ -/]*[@-~]", "", text)
    # Remove ANSI OSC sequences.
    text = re.sub(r"\x1B\][^\x07\x1B]*(?:\x07|\x1B\\)", "", text)
    # Remove other C0 controls except common whitespace.
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    return text


def extract_json_object(text: str) -> dict:
    text = strip_terminal_control_sequences(text).strip()
    if not text:
        raise ValueError("llama output is empty")

    for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL):
        candidate = match.group(1)
        parsed = try_parse_json_candidate(candidate)
        if parsed is not None:
            return parsed

    parsed = try_parse_json_candidate(text)
    if parsed is not None:
        return parsed

    # Fallback: evaluate all balanced JSON object blocks and return the first
    # successfully decoded JSON object.
    candidates: list[str] = []
    stack = 0
    start = -1
    for idx, ch in enumerate(text):
        if ch == "{":
            if stack == 0:
                start = idx
            stack += 1
        elif ch == "}":
            if stack > 0:
                stack -= 1
                if stack == 0 and start >= 0:
                    candidates.append(text[start : idx + 1])

    if not candidates:
        raise ValueError("Failed to find JSON object in llama output")

    for candidate in candidates:
        parsed = try_parse_json_candidate(candidate)
        if parsed is not None:
            return parsed

    raise ValueError("Failed to decode any JSON object candidate from llama output")


def parse_string_like(value: str) -> str:
    value = value.strip().rstrip(",").strip()
    if not value:
        return ""

    if value.startswith('"'):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, str):
                return parsed.strip()
        except json.JSONDecodeError:
            pass

    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("\\'", "'").strip()

    return value.strip('"').strip()


def parse_list_like(value: str) -> list[str]:
    value = value.strip().rstrip(",").strip()
    if not value:
        return []

    # Handle list encoded as string, e.g. "[\"one adult woman\"]".
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        inner = parse_string_like(value)
        if inner.startswith("[") and inner.endswith("]"):
            value = inner

    if value.startswith("[") and value.endswith("]"):
        candidate = re.sub(r",\s*\]", "]", value)
        parsed = try_parse_json_candidate('{"k": ' + candidate + "}")
        if isinstance(parsed, dict) and isinstance(parsed.get("k"), list):
            return [str(x).strip() for x in parsed["k"] if str(x).strip()]

        # Recover single-quoted list items.
        single_quoted_fixed = re.sub(
            r"'([^'\\]*(?:\\.[^'\\]*)*)'",
            lambda m: json.dumps(m.group(1)),
            candidate,
        )
        parsed = try_parse_json_candidate('{"k": ' + single_quoted_fixed + "}")
        if isinstance(parsed, dict) and isinstance(parsed.get("k"), list):
            return [str(x).strip() for x in parsed["k"] if str(x).strip()]

        # Last resort: split by commas.
        raw_items = [part.strip().strip('"').strip("'") for part in candidate[1:-1].split(",")]
        return [item for item in raw_items if item]

    return []


def extract_field_value_blob(text: str, key: str, known_keys: list[str]) -> str | None:
    key_pattern = rf'["\']{re.escape(key)}["\']\s*:\s*'
    m = re.search(key_pattern, text, flags=re.IGNORECASE)
    if not m:
        return None

    start = m.end()
    tail = text[start:]

    next_key_pattern = r",\s*[" + '"\'' + r"](?:" + "|".join(re.escape(k) for k in known_keys) + r")[" + '"\'' + r"]\s*:"
    next_match = re.search(next_key_pattern, tail, flags=re.IGNORECASE)
    end = next_match.start() if next_match else len(tail)
    return tail[:end].strip()


def strict_jsonize_output(text: str) -> dict | None:
    return strict_jsonize_output_with_schema(
        text=text,
        keys=["album_summary"],
        list_keys=set(),
        number_keys=set(),
    )


def strict_jsonize_output_with_schema(
    text: str,
    keys: list[str],
    list_keys: set[str],
    number_keys: set[str],
) -> dict | None:
    cleaned = strip_terminal_control_sequences(text)

    rebuilt: dict[str, object] = {}
    for key in keys:
        blob = extract_field_value_blob(cleaned, key, keys)
        if blob is None:
            continue
        if key in list_keys:
            rebuilt[key] = parse_list_like(blob)
        elif key in number_keys:
            rebuilt[key] = parse_float_like(blob)
        else:
            rebuilt[key] = parse_string_like(blob)

    if not rebuilt:
        return None
    return rebuilt


def run_llama(
    llama: LlamaConfig,
    prompt: str,
    sample_images: list[Path],
    max_tokens: int,
    temperature: float,
    image_max_tokens: int,
    ctx_size: int | None,
    threads: int | None,
    gpu_layers: int | None,
    expected_keys: list[str],
    list_keys: set[str],
    number_keys: set[str],
) -> LlamaRunResult:
    cmd = [str(llama.cli)]
    if llama.hf_repo and llama.hf_file:
        cmd.extend(["--hf-repo", llama.hf_repo, "--hf-file", llama.hf_file])
    elif llama.model is not None:
        cmd.extend(["-m", str(llama.model)])
    else:
        raise ValueError("Invalid llama config: missing both local model and hf repo/file")

    if llama.mmproj is not None:
        cmd.extend(["--mmproj", str(llama.mmproj)])

    cmd.extend(
        [
            "--temp",
            str(temperature),
            "-n",
            str(max_tokens),
            "--image-max-tokens",
            str(image_max_tokens),
            "--conversation",
            "--single-turn",
            "--simple-io",
            "-p",
            prompt,
        ]
    )

    if ctx_size is not None:
        cmd.extend(["-c", str(ctx_size)])
    if threads is not None:
        cmd.extend(["-t", str(threads)])
    if gpu_layers is not None:
        cmd.extend(["--n-gpu-layers", str(gpu_layers)])

    for image_path in sample_images:
        cmd.extend(["--image", str(image_path)])

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "llama-cli failed.\n"
            f"exit_code={result.returncode}\n"
            f"stderr:\n{result.stderr.strip()}\n"
        )

    for source, text in (
        ("stdout", result.stdout),
        ("stderr", result.stderr),
        ("stdout+stderr", f"{result.stdout}\n{result.stderr}"),
    ):
        try:
            return LlamaRunResult(
                data=extract_json_object(text),
                used_fallback=False,
                fallback_source=None,
                raw_stdout=result.stdout,
                raw_stderr=result.stderr,
            )
        except Exception:
            repaired = strict_jsonize_output_with_schema(
                text=text,
                keys=expected_keys,
                list_keys=list_keys,
                number_keys=number_keys,
            )
            if isinstance(repaired, dict):
                return LlamaRunResult(
                    data=repaired,
                    used_fallback=True,
                    fallback_source=source,
                    raw_stdout=result.stdout,
                    raw_stderr=result.stderr,
                )

    stdout_tail = result.stdout.strip()[-3000:]
    stderr_tail = result.stderr.strip()[-3000:]
    raise ValueError(
        "Failed to parse JSON from llama output.\n"
        f"stdout_tail:\n{stdout_tail}\n\n"
        f"stderr_tail:\n{stderr_tail}\n"
    )


def validate_output_schema(data: dict) -> dict:
    expected = {
        "scene": str,
        "subjects": list,
        "objects": list,
        "actions": list,
        "lighting": str,
        "environment": str,
        "summary": str,
        "confidence": float,
        "album_summary": str,
        "description": str,
        "suggested_names": list,
    }
    fixed = dict(data)
    for key, typ in expected.items():
        if key not in fixed:
            fixed[key] = [] if typ is list else ""
            continue
        if key == "confidence":
            fixed[key] = parse_float_like(fixed.get(key), 0.5)
            continue
        if not isinstance(fixed[key], typ):
            fixed[key] = [] if typ is list else str(fixed[key])

    for key in ("subjects", "objects", "actions", "suggested_names"):
        fixed[key] = [str(x).strip() for x in fixed.get(key, []) if str(x).strip()]

    fixed["suggested_names"] = [to_title_words(x) for x in fixed.get("suggested_names", []) if to_title_words(x)]
    return fixed


def safe_file_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    token = token.strip("._")
    return token or "auto"


def build_output_path(album_id: int, output_option: str) -> Path:
    outputs_dir = REPO_ROOT / "outputs"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    token = safe_file_token(output_option)
    stem = f"describe_album_{album_id}_{token}_{timestamp}"
    return outputs_dir / f"{stem}.json"


def build_stage_output_path(album_id: int, output_option: str, timestamp: str, stage: str) -> Path:
    outputs_dir = REPO_ROOT / "outputs"
    token = safe_file_token(output_option)
    stage_token = safe_file_token(stage)
    stem = f"describe_album_{album_id}_{token}_{timestamp}_{stage_token}"
    return outputs_dir / f"{stem}.json"


def build_fallback_raw_output_path(result_path: Path) -> Path:
    return result_path.with_name(result_path.stem + "_fallback_raw.json")


def write_json_file(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.size_outlier_threshold < 0:
        raise ValueError("--size-outlier-threshold must be >= 0")
    if args.ctx_size is not None and args.ctx_size <= 0:
        raise ValueError("--ctx-size must be > 0")
    if args.threads is not None and args.threads <= 0:
        raise ValueError("--threads must be > 0")
    if args.gpu_layers is not None and args.gpu_layers < 0:
        raise ValueError("--gpu-layers must be >= 0")

    archive_root = args.archive_root
    if archive_root is None:
        archive_root = read_archive_root(DEFAULT_APP_CONFIG)

    llama_cfg = load_llama_config(args.ai_config)
    describe_cfg = load_describe_config(args.ai_config)

    sample_count = args.sample_count if args.sample_count is not None else describe_cfg.default_sample_count
    if sample_count <= 0:
        raise ValueError("sample_count must be >= 1")

    with sqlite3.connect(args.db) as conn:
        album = load_album_row(conn, args.album_id)

    album_dir = resolve_album_dir(album.current_path, album.expected_path, archive_root)
    images = list_images(album_dir)
    sampled = pick_with_resample(images, sample_count, args.size_outlier_threshold)

    if args.verbose:
        avg_size = sum(p.stat().st_size for p in images) / len(images)
        print(
            f"[INFO] album_id={album.album_id} images={len(images)} sampled={len(sampled)} avg_size={avg_size:.1f}",
            file=sys.stderr,
        )
        for path in sampled:
            size = path.stat().st_size
            print(f"[INFO] sample: {path} ({size} bytes)", file=sys.stderr)

    vision_prompt = build_vision_prompt(album, describe_cfg.vision_prompt_template)
    vision_run = run_llama(
        llama=llama_cfg,
        prompt=vision_prompt,
        sample_images=sampled,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        image_max_tokens=args.image_max_tokens,
        ctx_size=args.ctx_size,
        threads=args.threads,
        gpu_layers=args.gpu_layers,
        expected_keys=["scene", "subjects", "objects", "actions", "lighting", "environment", "summary", "confidence"],
        list_keys={"subjects", "objects", "actions"},
        number_keys={"confidence"},
    )
    vision_adapted = vision_response_adapter(vision_run.data, album)

    writer_prompt = build_writer_prompt(album, vision_adapted.data, describe_cfg.writer_prompt_template)
    writer_run = run_llama(
        llama=llama_cfg,
        prompt=writer_prompt,
        sample_images=[],
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        image_max_tokens=args.image_max_tokens,
        ctx_size=args.ctx_size,
        threads=args.threads,
        gpu_layers=args.gpu_layers,
        expected_keys=["album_summary", "description", "suggested_names"],
        list_keys={"suggested_names"},
        number_keys=set(),
    )
    writer_adapted = writer_response_adapter(writer_run.data, album, vision_adapted.data)

    result = validate_output_schema({**vision_adapted.data, **writer_adapted.data})

    if args.verbose and vision_adapted.defaulted_fields:
        print(f"[INFO] vision_adapter_defaulted_fields={','.join(vision_adapted.defaulted_fields)}", file=sys.stderr)
    if args.verbose and writer_adapted.defaulted_fields:
        print(f"[INFO] writer_adapter_defaulted_fields={','.join(writer_adapted.defaulted_fields)}", file=sys.stderr)

    if args.output is not None:
        run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        vision_path = build_stage_output_path(album.album_id, args.output, run_timestamp, "vision")
        writer_path = build_stage_output_path(album.album_id, args.output, run_timestamp, "writer")

        vision_payload = {
            "stage": "vision",
            "album_id": album.album_id,
            "fallback_used": vision_run.used_fallback,
            "fallback_source": vision_run.fallback_source,
            "raw_response": vision_run.data,
            "adapted_response": vision_adapted.data,
        }
        writer_payload = {
            "stage": "writer",
            "album_id": album.album_id,
            "fallback_used": writer_run.used_fallback,
            "fallback_source": writer_run.fallback_source,
            "raw_response": writer_run.data,
            "adapted_response": writer_adapted.data,
            "final_result": result,
        }

        write_json_file(vision_path, vision_payload)
        write_json_file(writer_path, writer_payload)
        print(f"[INFO] vision_json={vision_path}", file=sys.stderr)
        print(f"[INFO] writer_json={writer_path}", file=sys.stderr)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())