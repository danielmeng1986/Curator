#!/usr/bin/env python3
"""Assign temporary album names to workspace_album rows.

Rules:
- Target rows are selected only by status_id.
- Reference titles come from one studio (MetArt by default).
- Generated names reuse title-like MetArt names without an extra prefix.
- Names must stay unique within the same parent folder of current_path.
- On apply, matching rows are also moved to a destination status_id.
- Default mode is dry-run; use --apply to persist updates.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[1] / "database" / "Curator.db"
DEFAULT_REFERENCE_STUDIO = "MetArt"
DEFAULT_STATUS_ID = 5
DEFAULT_PREFIX = ""
DEFAULT_DEST_STATUS_ID = 8

WORD_RE = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
SPACE_RE = re.compile(r"\s+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class TargetRow:
    row_id: int
    primary_model: str
    studio_name: str
    status_id: int
    old_album_name: str | None
    current_path: str
    parent_path: str


def normalize_space(text: str | None) -> str:
    return SPACE_RE.sub(" ", (text or "").strip())


def split_parent_path(current_path: str) -> str:
    current_path = normalize_space(current_path)
    if "/" not in current_path:
        return ""
    return current_path.rsplit("/", 1)[0]


def extract_words(text: str) -> list[str]:
    return [match.group(0) for match in WORD_RE.finditer(text)]


def title_case_token(token: str) -> str:
    hyphen_parts = []
    for hyphen_part in token.split("-"):
        apostrophe_parts = []
        for apostrophe_part in hyphen_part.split("'"):
            if apostrophe_part:
                apostrophe_parts.append(apostrophe_part[0].upper() + apostrophe_part[1:].lower())
            else:
                apostrophe_parts.append("")
        hyphen_parts.append("'".join(apostrophe_parts))
    return "-".join(hyphen_parts)


def title_case_phrase(tokens: list[str]) -> str:
    return " ".join(title_case_token(token) for token in tokens if token)


def cleaned_reference_title(title: str, prefix: str) -> str | None:
    tokens = extract_words(title)
    if not tokens:
        return None

    if len(tokens) < 2 or len(tokens) > 4:
        return None
    if tokens[0].casefold() in STOPWORDS or tokens[-1].casefold() in STOPWORDS:
        return None

    cleaned = title_case_phrase(tokens[:5])
    if not cleaned:
        return None

    if prefix and cleaned.casefold() == prefix.casefold():
        return None
    if prefix and cleaned.casefold().startswith(prefix.casefold() + " "):
        return None
    return cleaned


def stable_int(parts: list[str]) -> int:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def build_candidate_name(prefix: str, title: str) -> str:
    prefix = normalize_space(prefix)
    if not prefix:
        return title
    return f"{prefix} {title}"


def load_reference_titles(conn: sqlite3.Connection, studio_name: str, prefix: str) -> list[str]:
    raw_titles = [
        row[0]
        for row in conn.execute(
            """
            SELECT DISTINCT album_name
            FROM workspace_album
            WHERE studio_name = ?
              AND album_name IS NOT NULL
              AND TRIM(album_name) <> ''
            """,
            (studio_name,),
        )
    ]

    cleaned_titles: list[str] = []
    seen: set[str] = set()
    for raw_title in raw_titles:
        cleaned = cleaned_reference_title(raw_title, prefix)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned_titles.append(cleaned)

    if not cleaned_titles:
        raise ValueError(f"No usable reference titles found for studio {studio_name!r}.")

    token_counts: Counter[str] = Counter()
    first_counts: Counter[str] = Counter()
    last_counts: Counter[str] = Counter()
    bigram_counts: Counter[tuple[str, str]] = Counter()
    title_tokens: dict[str, list[str]] = {}

    for title in cleaned_titles:
        tokens = [token.casefold() for token in extract_words(title)]
        if not tokens:
            continue
        title_tokens[title] = tokens
        token_counts.update(tokens)
        first_counts[tokens[0]] += 1
        last_counts[tokens[-1]] += 1
        for left, right in zip(tokens, tokens[1:]):
            bigram_counts[(left, right)] += 1

    def score_title(title: str) -> tuple[float, str]:
        tokens = title_tokens[title]
        mean_token_score = sum(math.log1p(token_counts[token]) for token in tokens) / len(tokens)
        if len(tokens) > 1:
            mean_bigram_score = sum(
                math.log1p(bigram_counts[(left, right)])
                for left, right in zip(tokens, tokens[1:])
            ) / (len(tokens) - 1)
        else:
            mean_bigram_score = 0.0
        edge_score = math.log1p(first_counts[tokens[0]]) + math.log1p(last_counts[tokens[-1]])
        length_penalty = abs(len(tokens) - 2.5) * 0.35
        diversity_bonus = (len(set(tokens)) / len(tokens)) * 0.2
        score = mean_token_score + mean_bigram_score + edge_score * 0.1 + diversity_bonus - length_penalty
        return (score, title.casefold())

    ranked_titles = sorted(cleaned_titles, key=score_title, reverse=True)
    base_candidates = [build_candidate_name(prefix, title) for title in ranked_titles]

    return base_candidates


def load_target_rows(conn: sqlite3.Connection, status_id: int) -> list[TargetRow]:
    rows = conn.execute(
        """
        SELECT id, primary_model, studio_name, status_id, album_name, current_path
        FROM workspace_album
        WHERE status_id = ?
        ORDER BY id
        """,
        (status_id,),
    ).fetchall()

    return [
        TargetRow(
            row_id=row_id,
            primary_model=primary_model or "",
            studio_name=studio_name or "",
            status_id=int(row_status_id),
            old_album_name=album_name,
            current_path=current_path or "",
            parent_path=split_parent_path(current_path or ""),
        )
        for row_id, primary_model, studio_name, row_status_id, album_name, current_path in rows
    ]


def load_folder_occupancy(
    conn: sqlite3.Connection,
    target_rows: list[TargetRow],
) -> dict[str, set[str]]:
    target_ids = {row.row_id for row in target_rows}
    occupied: dict[str, set[str]] = defaultdict(set)

    for row_id, current_path, album_name in conn.execute(
        "SELECT id, current_path, album_name FROM workspace_album ORDER BY id"
    ):
        if row_id in target_ids:
            continue
        parent_path = split_parent_path(current_path or "")
        cleaned_name = normalize_space(album_name)
        if not cleaned_name:
            continue
        occupied[parent_path].add(cleaned_name.casefold())

    return occupied


def ordered_candidates(candidates: list[str], row: TargetRow) -> list[str]:
    if not candidates:
        return []

    count = len(candidates)
    if count == 1:
        return candidates

    seed = stable_int(
        [
            str(row.row_id),
            row.primary_model,
            row.studio_name,
            row.current_path,
            normalize_space(row.old_album_name),
        ]
    )
    start = seed % count
    step = ((seed // count) % (count - 1)) + 1
    while math.gcd(step, count) != 1:
        step += 1

    return [candidates[(start + index * step) % count] for index in range(count)]


def ensure_unique(candidate: str, used_names: set[str]) -> str:
    if candidate.casefold() not in used_names:
        return candidate

    suffix = 2
    while True:
        renamed = f"{candidate} {suffix}"
        if renamed.casefold() not in used_names:
            return renamed
        suffix += 1


def build_assignments(
    target_rows: list[TargetRow],
    candidates: list[str],
    occupied_by_parent: dict[str, set[str]],
) -> list[tuple[TargetRow, str]]:
    rows_by_parent: dict[str, list[TargetRow]] = defaultdict(list)
    for row in target_rows:
        rows_by_parent[row.parent_path].append(row)

    assignments: list[tuple[TargetRow, str]] = []

    for parent_path, rows in rows_by_parent.items():
        used_names = set(occupied_by_parent.get(parent_path, set()))
        ordered_rows = sorted(
            rows,
            key=lambda row: (
                normalize_space(row.old_album_name).casefold(),
                row.current_path.casefold(),
                row.row_id,
            ),
        )
        for row in ordered_rows:
            chosen = None
            for candidate in ordered_candidates(candidates, row):
                unique_candidate = ensure_unique(candidate, used_names)
                if unique_candidate.casefold() not in used_names:
                    chosen = unique_candidate
                    break

            if chosen is None:
                fallback = f"Temporary Album {row.row_id}"
                chosen = ensure_unique(fallback, used_names)

            used_names.add(chosen.casefold())
            assignments.append((row, chosen))

    assignments.sort(key=lambda item: item[0].row_id)
    return assignments


def apply_assignments(
    conn: sqlite3.Connection,
    assignments: list[tuple[TargetRow, str]],
    apply: bool,
    preview: int,
    destination_status_id: int,
) -> int:
    changed = 0
    shown = 0

    if apply:
        conn.execute("BEGIN")

    for row, new_album_name in assignments:
        old_album_name = normalize_space(row.old_album_name)
        should_change = old_album_name != new_album_name or row.status_id != destination_status_id
        if should_change:
            changed += 1

        if shown < preview:
            print(f"[id={row.row_id}] {row.current_path}")
            print(f"  album_name: {old_album_name!r} -> {new_album_name!r}")
            print(f"  status_id: {row.status_id} -> {destination_status_id}")
            shown += 1

        if apply and should_change:
            conn.execute(
                "UPDATE workspace_album SET album_name = ?, status_id = ? WHERE id = ?",
                (new_album_name, destination_status_id, row.row_id),
            )

    if apply:
        conn.commit()

    return changed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fill temporary album names for workspace_album rows selected by status_id."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite database path (default: {DEFAULT_DB})")
    parser.add_argument(
        "--reference-studio",
        default=DEFAULT_REFERENCE_STUDIO,
        help=f"Reference studio for the naming corpus (default: {DEFAULT_REFERENCE_STUDIO})",
    )
    parser.add_argument(
        "--status-id",
        type=int,
        default=DEFAULT_STATUS_ID,
        help=f"Target status_id to process (default: {DEFAULT_STATUS_ID})",
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help=f"Prefix used for generated names (default: {DEFAULT_PREFIX})",
    )
    parser.add_argument(
        "--destination-status-id",
        type=int,
        default=DEFAULT_DEST_STATUS_ID,
        help=f"status_id to write when applying updates (default: {DEFAULT_DEST_STATUS_ID})",
    )
    parser.add_argument("--apply", action="store_true", help="Persist updates to the database")
    parser.add_argument("--preview", type=int, default=25, help="How many rows to preview (default: 25)")
    args = parser.parse_args()

    with sqlite3.connect(args.db) as conn:
        target_rows = load_target_rows(conn, args.status_id)
        candidate_pool = load_reference_titles(conn, args.reference_studio, args.prefix)
        occupied_by_parent = load_folder_occupancy(conn, target_rows)
        assignments = build_assignments(target_rows, candidate_pool, occupied_by_parent)
        changed = apply_assignments(
            conn,
            assignments,
            apply=args.apply,
            preview=max(args.preview, 0),
            destination_status_id=args.destination_status_id,
        )

    folders_touched = len({row.parent_path for row in target_rows})
    print(f"Reference studio: {args.reference_studio}")
    print(f"Reference titles used: {len(candidate_pool)}")
    print(f"Target status_id: {args.status_id}")
    print(f"Destination status_id: {args.destination_status_id}")
    print(f"Rows scanned: {len(target_rows)}")
    print(f"Rows changed: {changed}")
    print(f"Folders touched: {folders_touched}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())