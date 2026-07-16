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
    prompt_template: str


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

    prompt_template = section.get("prompt_template")
    if not isinstance(prompt_template, str) or not prompt_template.strip():
        raise ValueError(f"[describe_album].prompt_template must be a non-empty string in {ai_config_path}")

    return DescribeConfig(default_sample_count=sample_count, prompt_template=prompt_template.strip())


def load_album_row(conn: sqlite3.Connection, album_id: int) -> AlbumRow:
    row = conn.execute(
        """
        SELECT id, current_path, expected_path, primary_model, studio_name, album_name
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
        studio_name=str(row[4]),
        album_name=str(row[5]),
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


def build_prompt(album: AlbumRow, template: str) -> str:
    schema = {
        "album_summary": "...",
        "tags": ["...", "..."],
        "scene": "...",
        "subjects": ["..."],
        "mood": "...",
        "suggested_names": ["...", "...", "..."],
    }
    rendered = template
    rendered = rendered.replace("__ALBUM_ID__", str(album.album_id))
    rendered = rendered.replace("__STUDIO_NAME__", album.studio_name)
    rendered = rendered.replace("__PRIMARY_MODEL__", album.primary_model)
    rendered = rendered.replace("__ALBUM_NAME__", album.album_name)
    rendered = rendered.replace("__SCHEMA_EXAMPLE__", json.dumps(schema, ensure_ascii=True))
    return rendered


def extract_json_object(text: str) -> dict:
    text = text.strip()
    if not text:
        raise ValueError("llama output is empty")

    for match in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL):
        candidate = match.group(1)
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

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
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Failed to decode any JSON object candidate from llama output")


def run_llama(
    llama: LlamaConfig,
    prompt_template: str,
    album: AlbumRow,
    sample_images: list[Path],
    max_tokens: int,
    temperature: float,
    image_max_tokens: int,
    ctx_size: int | None,
    threads: int | None,
    gpu_layers: int | None,
) -> dict:
    prompt = build_prompt(album, prompt_template)
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

    for text in (result.stdout, result.stderr, f"{result.stdout}\n{result.stderr}"):
        try:
            return extract_json_object(text)
        except Exception:
            continue

    stdout_tail = result.stdout.strip()[-3000:]
    stderr_tail = result.stderr.strip()[-3000:]
    raise ValueError(
        "Failed to parse JSON from llama output.\n"
        f"stdout_tail:\n{stdout_tail}\n\n"
        f"stderr_tail:\n{stderr_tail}\n"
    )


def validate_output_schema(data: dict) -> dict:
    expected = {
        "album_summary": str,
        "tags": list,
        "scene": str,
        "subjects": list,
        "mood": str,
        "suggested_names": list,
    }
    fixed = dict(data)
    for key, typ in expected.items():
        if key not in fixed:
            fixed[key] = [] if typ is list else ""
            continue
        if not isinstance(fixed[key], typ):
            fixed[key] = [] if typ is list else str(fixed[key])

    for key in ("tags", "subjects", "suggested_names"):
        fixed[key] = [str(x).strip() for x in fixed.get(key, []) if str(x).strip()]
    return fixed


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

    result = run_llama(
        llama=llama_cfg,
        prompt_template=describe_cfg.prompt_template,
        album=album,
        sample_images=sampled,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        image_max_tokens=args.image_max_tokens,
        ctx_size=args.ctx_size,
        threads=args.threads,
        gpu_layers=args.gpu_layers,
    )
    result = validate_output_schema(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())