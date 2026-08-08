"""Disposable Backend composition root for browser workflow acceptance.

The process owns every mutable resource below one temporary root and prints a
single JSON manifest. It never reads Curator's runtime database, media roots,
tokens, backups, logs, or outputs.
"""
from __future__ import annotations

import argparse
import json
import signal
import sqlite3
import sys
import tempfile
import threading
import uuid
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from apps.backend import server
from apps.backend.tests.workflow_support import _WORKFLOW_SCHEMA_SQL


SCENARIOS = {
    "empty": "Base status only.",
    "entities": "Permanent Studio, Model, Album, relationship, and Photo.",
    "workflow-evidence": "Issue, Repair, and Operation records for read-model work.",
    "filesystem": "Disposable Import source, Archive, Snapshot, and Quarantine roots.",
}


def _connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=15, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _initialize_database(database_path: Path, scenario: str) -> None:
    connection = _connect(database_path)
    try:
        connection.executescript(_WORKFLOW_SCHEMA_SQL)
        connection.execute(
            "INSERT INTO status (name, description) VALUES (?, ?)",
            ("Active", "Active albums"),
        )
        if scenario == "entities":
            connection.execute(
                "INSERT INTO studio (uuid, name, website) VALUES (?, ?, ?)",
                ("studio-ui-fixture", "Fixture Studio", "https://example.invalid"),
            )
            connection.execute(
                "INSERT INTO model (uuid, display_name, primary_name) VALUES (?, ?, ?)",
                ("model-ui-fixture", "Fixture Model", "Fixture Model"),
            )
            connection.execute(
                """INSERT INTO album
                   (uuid, studio_id, status_id, title, path)
                   VALUES (?, 1, 1, ?, ?)""",
                ("album-ui-fixture", "Fixture Album", "Fixture Studio/Fixture Album"),
            )
            connection.execute(
                "INSERT INTO album_model (album_id, model_id, role) VALUES (1, 1, ?)",
                ("primary",),
            )
            connection.execute(
                """INSERT INTO photo
                   (uuid, album_id, filename, relative_path)
                   VALUES (?, 1, ?, ?)""",
                ("photo-ui-fixture", "cover.jpg", "cover.jpg"),
            )
        elif scenario == "workflow-evidence":
            operation_uuid = "operation-ui-fixture"
            issue_uuid = "issue-ui-fixture"
            repair_uuid = "repair-ui-fixture"
            connection.execute(
                """INSERT INTO operation
                   (uuid, operation_type, initiator, status, summary, started_at,
                    issue_uuid, repair_uuid, recovery_context)
                   VALUES (?, 'import', 'web_ui', 'NeedsRepair', ?,
                           '2026-08-08T00:00:00+00:00', ?, ?, ?)""",
                (operation_uuid, "Fixture import requires review.", issue_uuid, repair_uuid,
                 "Review the linked Repair before retrying."),
            )
            connection.execute(
                """INSERT INTO issue
                   (uuid, category, description, affected_operation,
                    suggested_resolution, state, source_workflow, created_at, updated_at)
                   VALUES (?, 'Filesystem', ?, ?, ?, 'Open', 'fixture',
                           '2026-08-08T00:00:00+00:00', '2026-08-08T00:00:00+00:00')""",
                (issue_uuid, "Fixture Issue", operation_uuid, "Review fixture repair."),
            )
            connection.execute(
                """INSERT INTO repair_case
                   (uuid, operation_uuid, expected_path, state, category, failure_reason, created_at, updated_at)
                   VALUES (?, ?, 'F/Fixture Model/Fixture Studio/Fixture Album',
                           'NeedsRepair', 'Assisted', 'Fixture filesystem failure',
                           '2026-08-08T00:00:00+00:00', '2026-08-08T00:00:00+00:00')""",
                (repair_uuid, operation_uuid),
            )
        connection.commit()
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--secret", required=True)
    parser.add_argument("--scenario", choices=tuple(SCENARIOS), default="empty")
    args = parser.parse_args()

    temporary = tempfile.TemporaryDirectory(prefix="curator-browser-")
    root = Path(temporary.name).resolve()
    resources = {
        "database": root / "data" / "Curator-Browser-Sandbox.db",
        "source": root / "source",
        "archive": root / "archive",
        "snapshots": root / "snapshots",
        "quarantine": root / "quarantine",
        "backups": root / "backups",
        "logs": root / "logs",
        "outputs": root / "outputs",
    }
    for name, path in resources.items():
        (path.parent if name == "database" else path).mkdir(parents=True, exist_ok=True)
    if args.scenario == "filesystem":
        source_album = resources["source"] / "Fixture Model in Fixture Album"
        source_album.mkdir()
        (source_album / "cover.jpg").touch()

    _initialize_database(resources["database"], args.scenario)
    config_path = root / "backend.json"
    config_path.write_text(
        json.dumps({
            "import_source_root": str(resources["source"]),
            "archive_root": str(resources["archive"]),
            "default_import_studio": "Fixture Studio",
        }),
        encoding="utf-8",
    )

    server.DATABASE_PATH = resources["database"]
    server.CONFIG_PATH = config_path
    server.BACKUP_DIR = resources["backups"]
    server.LOG_DIR = resources["logs"]
    server.LOG_PATH = resources["logs"] / "changes.log"
    server.BACKUP_LOG_PATH = resources["logs"] / "backup.log"
    server.ROLLBACK_LOG_PATH = resources["logs"] / "rollback.log"
    server.AUTH_REGISTRATION_SECRET = args.secret
    server.APP_CONFIG = server.load_app_config()
    server.open_db = lambda: _connect(resources["database"])

    httpd = HTTPServer(("127.0.0.1", args.port), server.AppHandler)
    manifest = {
        "fixture_id": str(uuid.uuid4()),
        "scenario": args.scenario,
        "origin": f"http://127.0.0.1:{httpd.server_address[1]}",
        "root": str(root),
        "resources": {key: str(value) for key, value in resources.items()},
    }
    print(json.dumps(manifest), flush=True)
    signal.signal(
        signal.SIGTERM,
        lambda *_: threading.Thread(target=httpd.shutdown, daemon=True).start(),
    )
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        temporary.cleanup()


if __name__ == "__main__":
    main()
