"""Shared isolated fixtures and observable-state assertions for workflow tests.

Workflow tests use this module instead of the production database, Archive,
snapshot directory, or quarantine directory.  The helpers intentionally expose
only durable database rows and filesystem state; scenarios should invoke public
service or API boundaries rather than assert private implementation calls.
"""

from __future__ import annotations

import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable


_WORKFLOW_SCHEMA_SQL = """
CREATE TABLE status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT
);
CREATE TABLE model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL DEFAULT '',
    display_name TEXT,
    primary_name TEXT,
    description TEXT,
    country TEXT,
    ethnicity TEXT,
    eye_color TEXT,
    natural_hair_color TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE studio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL DEFAULT '',
    name TEXT,
    website TEXT,
    description TEXT,
    media_scope TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE album (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL DEFAULT '',
    studio_id INTEGER,
    status_id INTEGER,
    title TEXT,
    description TEXT,
    scene TEXT,
    location TEXT,
    capture_date TEXT,
    publish_date TEXT,
    rating REAL,
    path TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE album_model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id INTEGER,
    model_id INTEGER,
    age_when_shot REAL,
    role TEXT,
    remarks TEXT
);
CREATE TABLE album_relation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id INTEGER,
    related_album_id INTEGER,
    relation_type TEXT,
    remarks TEXT
);
CREATE TABLE photo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL DEFAULT '',
    album_id INTEGER,
    filename TEXT,
    relative_path TEXT,
    hash TEXT,
    width INTEGER,
    height INTEGER,
    capture_time TEXT,
    created_at TEXT
);
CREATE TABLE workspace_album (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT,
    status_id INTEGER,
    studio_name TEXT,
    album_name TEXT,
    primary_model TEXT,
    additional_models TEXT,
    remark TEXT,
    current_path TEXT,
    expected_path TEXT,
    ai_result TEXT,
    belongs_to_album_id INTEGER,
    album_id INTEGER,
    lifecycle_state TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE repair_case (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    operation_uuid TEXT,
    album_uuid TEXT,
    expected_path TEXT,
    state TEXT NOT NULL DEFAULT 'NeedsRepair',
    category TEXT NOT NULL DEFAULT 'Assisted',
    confirmation TEXT,
    failure_reason TEXT,
    verification_result TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE issue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    affected_operation TEXT,
    suggested_resolution TEXT,
    state TEXT NOT NULL DEFAULT 'Open',
    source_workflow TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    priority TEXT DEFAULT 'Normal',
    owner TEXT,
    due_date TEXT
);
CREATE TABLE operation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    initiator TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending',
    summary TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    entity_uuid TEXT,
    import_uuid TEXT,
    batch_uuid TEXT,
    repair_uuid TEXT,
    related_operation_uuid TEXT,
    parent_operation_uuid TEXT,
    issue_uuid TEXT,
    error_category TEXT,
    error_code TEXT,
    error_details TEXT,
    repair_state TEXT,
    recovery_context TEXT
);
"""


class WorkflowSandbox:
    """Disposable database and filesystem roots for one workflow scenario."""

    def __init__(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory(prefix="curator-workflow-")
        self.root = Path(self._temporary_directory.name).resolve()
        self.database_path = self.root / "Curator-Workflow-Sandbox.db"
        self.source_root = self.root / "source"
        self.archive_root = self.root / "archive"
        self.snapshot_root = self.root / "snapshots"
        self.quarantine_root = self.root / "quarantine"
        for path in (
            self.source_root,
            self.archive_root,
            self.snapshot_root,
            self.quarantine_root,
        ):
            path.mkdir()
        conn = self.connect()
        try:
            conn.executescript(_WORKFLOW_SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    def __enter__(self) -> "WorkflowSandbox":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        self._temporary_directory.cleanup()

    def connect(self) -> sqlite3.Connection:
        """Return a new connection to this scenario's disposable database."""
        conn = sqlite3.connect(self.database_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def db_factory(self):
        """Return the repository-compatible factory for the sandbox database."""
        @contextmanager
        def connection_scope():
            conn = self.connect()
            try:
                yield conn
            finally:
                conn.close()

        return connection_scope

    def path_under(self, root: Path, relative_path: str | Path) -> Path:
        """Resolve a relative scenario path and reject paths outside its root."""
        relative = Path(relative_path)
        if relative.is_absolute():
            raise ValueError("Workflow fixtures require a relative path.")
        candidate = (root / relative).resolve()
        if candidate != root and root not in candidate.parents:
            raise ValueError("Workflow fixture path escapes its sandbox root.")
        return candidate

    def create_source_directory(
        self, relative_path: str | Path, files: Iterable[str] = ()
    ) -> Path:
        """Create a source directory with optional placeholder files."""
        directory = self.path_under(self.source_root, relative_path)
        directory.mkdir(parents=True, exist_ok=False)
        for filename in files:
            file_path = self.path_under(directory, filename)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.touch()
        return directory

    def assert_path_exists(self, root: Path, relative_path: str | Path) -> Path:
        path = self.path_under(root, relative_path)
        if not path.exists():
            raise AssertionError(f"Expected sandbox path to exist: {path}")
        return path

    def assert_path_missing(self, root: Path, relative_path: str | Path) -> None:
        path = self.path_under(root, relative_path)
        if path.exists():
            raise AssertionError(f"Expected sandbox path to be absent: {path}")

    def assert_row_count(self, table: str, expected: int) -> None:
        if table not in {"album", "issue", "operation", "repair_case", "workspace_album"}:
            raise ValueError(f"Unsupported workflow assertion table: {table}")
        conn = self.connect()
        try:
            actual = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()
        if actual != expected:
            raise AssertionError(
                f"Expected {expected} durable {table} record(s), found {actual}."
            )

    def assert_operation(self, operation_uuid: str, **expected: object) -> dict:
        return self._assert_row("operation", operation_uuid, expected)

    def assert_operation_for_import(
        self, target_import_uuid: str, **expected: object
    ) -> dict:
        """Return the unique durable Operation associated with an import."""
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM operation WHERE import_uuid = ?", (target_import_uuid,)
            ).fetchall()
        finally:
            conn.close()
        if len(rows) != 1:
            raise AssertionError(
                f"Expected one Operation for import {target_import_uuid!r}, found {len(rows)}."
            )
        result = dict(rows[0])
        for field, value in expected.items():
            if result.get(field) != value:
                raise AssertionError(
                    f"Expected operation.{field}={value!r}, got {result.get(field)!r}."
                )
        return result

    def assert_issue(self, issue_uuid: str, **expected: object) -> dict:
        return self._assert_row("issue", issue_uuid, expected)

    def assert_repair_case(self, repair_uuid: str, **expected: object) -> dict:
        return self._assert_row("repair_case", repair_uuid, expected)

    def _assert_row(self, table: str, record_uuid: str, expected: dict[str, object]) -> dict:
        conn = self.connect()
        try:
            row = conn.execute(
                f"SELECT * FROM {table} WHERE uuid = ?", (record_uuid,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise AssertionError(f"Expected durable {table} record {record_uuid!r}.")
        result = dict(row)
        for field, value in expected.items():
            if result.get(field) != value:
                raise AssertionError(
                    f"Expected {table}.{field}={value!r}, got {result.get(field)!r}."
                )
        return result
