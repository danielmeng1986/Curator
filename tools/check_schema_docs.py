#!/usr/bin/env python3
"""Verify documented schema inventory against a disposable canonical database."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.backend.migrations.runner import MIGRATION_FILES, migrate


INVENTORY_PATH = ROOT / "Docs" / "Database" / "schema-inventory.json"
CATALOG_PATH = ROOT / "Docs" / "Database" / "Schema-Catalog.md"
EXCLUDED_TABLES = {"sqlite_sequence"}


def _rows(conn: sqlite3.Connection, query: str):
    return [dict(row) for row in conn.execute(query)]


def inspect_schema(database: Path) -> dict:
    """Return stable structural inventory; never includes SQLite internal tables."""
    with closing(sqlite3.connect(database)) as conn:
        conn.row_factory = sqlite3.Row
        table_names = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ) if row[0] not in EXCLUDED_TABLES]
        tables = {}
        for table in table_names:
            quoted = table.replace('"', '""')
            columns = [{
                "name": row["name"], "type": row["type"],
                "not_null": bool(row["notnull"]), "default": row["dflt_value"],
                "primary_key_position": row["pk"],
            } for row in conn.execute(f'PRAGMA table_info("{quoted}")')]
            foreign_keys = sorted(({
                "from": row["from"], "table": row["table"], "to": row["to"],
                "on_update": row["on_update"], "on_delete": row["on_delete"],
            } for row in conn.execute(f'PRAGMA foreign_key_list("{quoted}")')),
                key=lambda value: (value["from"], value["table"], value["to"] or ""))
            indexes = []
            for index in conn.execute(f'PRAGMA index_list("{quoted}")'):
                index_name = index["name"].replace('"', '""')
                columns_in_index = [row["name"] for row in conn.execute(
                    f'PRAGMA index_info("{index_name}")'
                )]
                indexes.append({
                    "name": index["name"] if index["origin"] == "c" else None,
                    "columns": columns_in_index, "unique": bool(index["unique"]),
                    "origin": index["origin"], "partial": bool(index["partial"]),
                })
            indexes.sort(key=lambda value: (
                value["name"] or "", value["origin"], value["columns"]
            ))
            tables[table] = {
                "columns": columns, "foreign_keys": foreign_keys, "indexes": indexes,
            }
    return {
        "format_version": 1,
        "migrations": [source.stem for source in MIGRATION_FILES],
        "excluded_tables": sorted(EXCLUDED_TABLES),
        "unsupported": [
            "CHECK expression text is not compared independently; SQLite does not expose it through a stable PRAGMA."
        ],
        "tables": tables,
    }


def build_canonical_inventory() -> dict:
    with tempfile.TemporaryDirectory(prefix="curator-schema-docs-") as temporary:
        root = Path(temporary)
        database = root / "Curator.db"
        migrate(database, root / "backups")
        return inspect_schema(database)


def differences(expected: dict, actual: dict) -> list[str]:
    messages = []
    expected_tables, actual_tables = expected.get("tables", {}), actual.get("tables", {})
    for name in sorted(actual_tables.keys() - expected_tables.keys()):
        messages.append(f"undocumented table: {name}")
    for name in sorted(expected_tables.keys() - actual_tables.keys()):
        messages.append(f"documented table missing from schema: {name}")
    for name in sorted(expected_tables.keys() & actual_tables.keys()):
        for section in ("columns", "foreign_keys", "indexes"):
            if expected_tables[name].get(section) != actual_tables[name].get(section):
                messages.append(f"changed {section}: {name}")
    if expected.get("migrations") != actual.get("migrations"):
        messages.append("changed ordered migration inventory")
    return messages


def catalog_gaps(inventory: dict, catalog_text: str) -> list[str]:
    return [name for name in inventory["tables"] if f"`{name}`" not in catalog_text]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true",
        help="replace the committed inventory after a reviewed schema/catalog change",
    )
    args = parser.parse_args(argv)
    actual = build_canonical_inventory()
    if args.write:
        INVENTORY_PATH.write_text(
            json.dumps(actual, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"wrote {INVENTORY_PATH.relative_to(ROOT)}")
        return 0
    try:
        expected = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"missing inventory: {INVENTORY_PATH.relative_to(ROOT)}")
        return 1
    failures = differences(expected, actual)
    gaps = catalog_gaps(actual, CATALOG_PATH.read_text(encoding="utf-8"))
    failures.extend(f"table absent from Schema Catalog: {name}" for name in gaps)
    if failures:
        print("Schema documentation drift detected:")
        for failure in failures:
            print(f"- {failure}")
        print("Review schema and documentation, then run --write intentionally.")
        return 1
    print(
        f"Schema documentation gate: OK "
        f"({len(actual['tables'])} tables, {len(actual['migrations'])} migrations)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
