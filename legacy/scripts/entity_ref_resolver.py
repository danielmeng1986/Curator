#!/usr/bin/env python3
"""Resolve table references by id or name for Curator scripts.

Supported logical tables:
- model
- studio
- status (alias: state)
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class EntityRef:
    table: str
    row_id: int
    name: str


_TABLE_CONFIG = {
    "model": {"table": "model", "id_col": "id", "name_col": "name"},
    "studio": {"table": "studio", "id_col": "id", "name_col": "name"},
    "status": {"table": "status", "id_col": "id", "name_col": "name"},
    # Backward-friendly alias requested by user wording.
    "state": {"table": "status", "id_col": "id", "name_col": "name"},
}


def _get_config(table_key: str) -> dict[str, str]:
    key = table_key.strip().lower()
    if key not in _TABLE_CONFIG:
        supported = ", ".join(sorted(_TABLE_CONFIG.keys()))
        raise ValueError(f"Unsupported table key: {table_key}. Supported: {supported}")
    return _TABLE_CONFIG[key]


def resolve_entity_ref(conn: sqlite3.Connection, table_key: str, value: str) -> EntityRef | None:
    """Resolve an entity from a configured table by id or name.

    Rules:
    - Numeric input prefers id lookup.
    - If numeric id is not found, fall back to exact name lookup.
    - Non-numeric input uses exact name lookup.
    """
    cfg = _get_config(table_key)
    table = cfg["table"]
    id_col = cfg["id_col"]
    name_col = cfg["name_col"]

    raw = value.strip()
    if not raw:
        return None

    if raw.isdigit():
        row = conn.execute(
            f"SELECT {id_col}, {name_col} FROM {table} WHERE {id_col} = ?",
            (int(raw),),
        ).fetchone()
        if row:
            return EntityRef(table=table, row_id=row[0], name=row[1])

    row = conn.execute(
        f"SELECT {id_col}, {name_col} FROM {table} WHERE {name_col} = ?",
        (raw,),
    ).fetchone()
    if row:
        return EntityRef(table=table, row_id=row[0], name=row[1])

    return None
