#!/usr/bin/env python3
import json
import re
import shutil
import sqlite3
import socket
import threading
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent
STATIC_DIR = BASE_DIR / "static"
DATABASE_PATH = REPO_ROOT / "database" / "Curator.db"
QUERY_DIR = REPO_ROOT / "database"
ARCHIVE_ROOT = Path("/Volumes/NAS-RAID5/RAID/Prime_Media/Archive")
LOG_PATH = BASE_DIR / "logs" / "changes.log"
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_LOG_PATH = BASE_DIR / "logs" / "backup.log"
ROLLBACK_LOG_PATH = BASE_DIR / "logs" / "rollback.log"

APP_BASE_PATH = "/normalize"
API_PREFIX = "/api"

STOP_EVENT = threading.Event()

RETENTION_DAYS = 15
BACKUP_NAME_RE = re.compile(r"^Curator_(\d{8}_\d{6})_(.+)\.db$")
ALBUM_FOLDER_RE = re.compile(r"^(.+?)\s+in\s+(.+)$", re.IGNORECASE)

ALLOWED_TABLES = {"workspace_album"}
EXCLUDED_QUERY_FILES = {"Curator.db"}
DEFAULT_IMPORT_STUDIO = "MetArt"
STATUS_RENAMED = 3
STATUS_IMPORTED = 4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def local_now() -> datetime:
    return datetime.now().astimezone()


def next_local_midnight(now: datetime | None = None) -> datetime:
    current = now or local_now()
    return current.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)


def sanitize_ts(value: datetime) -> str:
    return value.strftime("%Y%m%d_%H%M%S")


def sanitize_label(value: str, default: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip())
    cleaned = cleaned.strip("_")
    return cleaned or default


def normalize_tag(tag: str) -> str:
    return sanitize_label(tag, "")


def parse_iso_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=local_now().tzinfo)
    return dt.astimezone(local_now().tzinfo)


def append_json_log(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            rows.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return rows


def append_backup_log(entry: dict) -> None:
    append_json_log(BACKUP_LOG_PATH, entry)


def append_rollback_log(entry: dict) -> None:
    append_json_log(ROLLBACK_LOG_PATH, entry)


def create_db_snapshot(reason: str = "scheduled", tag: str = "") -> Path:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = local_now()
    safe_reason = sanitize_label(reason, "manual")
    normalized_tag = normalize_tag(tag)
    tag_suffix = f"_tag-{normalized_tag}" if normalized_tag else ""
    backup_path = BACKUP_DIR / f"Curator_{sanitize_ts(ts)}_{safe_reason}{tag_suffix}.db"

    src = sqlite3.connect(DATABASE_PATH, timeout=15)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    return backup_path


def parse_snapshot_created_at(path: Path) -> datetime | None:
    matched = BACKUP_NAME_RE.match(path.name)
    if not matched:
        return None
    try:
        naive = datetime.strptime(matched.group(1), "%Y%m%d_%H%M%S")
    except ValueError:
        return None
    return naive.replace(tzinfo=local_now().tzinfo)


def parse_tag_from_name(path: Path) -> str:
    marker = "_tag-"
    if marker not in path.stem:
        return ""
    return path.stem.split(marker, 1)[1]


def load_backup_metadata() -> dict[str, dict]:
    rows = read_jsonl(BACKUP_LOG_PATH)
    meta: dict[str, dict] = {}
    for row in rows:
        snapshot = row.get("snapshot")
        if not snapshot:
            continue
        snapshot_key = str(Path(snapshot).resolve())
        meta[snapshot_key] = row
    return meta


def build_backup_catalog() -> list[dict]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    metadata = load_backup_metadata()
    entries: list[dict] = []

    for path in sorted(BACKUP_DIR.glob("*.db")):
        resolved = str(path.resolve())
        meta = metadata.get(resolved, {})
        created_at_dt = parse_snapshot_created_at(path)
        if created_at_dt is None:
            stat_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=local_now().tzinfo)
            created_at_dt = stat_dt
        tag = str(meta.get("tag") or "").strip() or parse_tag_from_name(path)
        entry = {
            "snapshot": resolved,
            "filename": path.name,
            "created_at": created_at_dt.isoformat(),
            "tag": tag,
            "protected": bool(tag),
            "size_bytes": path.stat().st_size,
            "reason": str(meta.get("reason") or ""),
            "_created_at_dt": created_at_dt,
        }
        entries.append(entry)

    entries.sort(key=lambda item: item["_created_at_dt"], reverse=True)
    return entries


def cleanup_expired_snapshots(retention_days: int = RETENTION_DAYS) -> dict:
    cutoff = local_now() - timedelta(days=retention_days)
    catalog = build_backup_catalog()
    deleted: list[str] = []
    kept_protected: list[str] = []
    failed: list[dict] = []

    for item in catalog:
        snapshot = Path(item["snapshot"])
        created_at = item["_created_at_dt"]
        if item["protected"]:
            kept_protected.append(str(snapshot))
            continue
        if created_at > cutoff:
            continue
        try:
            snapshot.unlink(missing_ok=True)
            deleted.append(str(snapshot))
        except Exception as ex:
            failed.append({"snapshot": str(snapshot), "error": str(ex)})

    event = {
        "timestamp": utc_now_iso(),
        "reason": "retention_cleanup",
        "ok": len(failed) == 0,
        "retention_days": retention_days,
        "deleted": deleted,
        "protected_kept": len(kept_protected),
        "failed": failed,
    }
    append_backup_log(event)
    return event


def find_snapshot_before_or_at(target: datetime) -> dict | None:
    catalog = build_backup_catalog()
    for item in catalog:
        if item["_created_at_dt"] <= target:
            return item
    return None


def public_backup_item(item: dict) -> dict:
    return {k: v for k, v in item.items() if not k.startswith("_")}


def find_snapshot_by_tag(tag: str) -> dict | None:
    if not tag:
        return None
    normalized = normalize_tag(tag)
    if not normalized:
        return None
    catalog = build_backup_catalog()
    for item in catalog:
        if normalize_tag(str(item.get("tag") or "")) == normalized:
            return item
    return None


def get_last_success_change_entry() -> dict | None:
    rows = read_jsonl(LOG_PATH)
    for row in reversed(rows):
        if not row.get("success"):
            continue
        return row
    return None


def restore_database_from_snapshot(snapshot_path: Path) -> None:
    if not snapshot_path.exists() or not snapshot_path.is_file():
        raise FileNotFoundError(f"snapshot not found: {snapshot_path}")

    src = sqlite3.connect(snapshot_path)
    dst = sqlite3.connect(DATABASE_PATH, timeout=15)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def run_daily_backup() -> None:
    while not STOP_EVENT.is_set():
        now = local_now()
        run_at = next_local_midnight(now)
        wait_seconds = max(1.0, (run_at - now).total_seconds())

        # Wake up at next midnight or exit early when stop is requested.
        interrupted = STOP_EVENT.wait(timeout=wait_seconds)
        if interrupted:
            break

        log_entry: dict = {
            "timestamp": utc_now_iso(),
            "reason": "scheduled_daily",
            "ok": True,
            "tag": "",
        }
        try:
            snapshot = create_db_snapshot("daily")
            log_entry["snapshot"] = str(snapshot)
            cleanup = cleanup_expired_snapshots(RETENTION_DAYS)
            log_entry["cleanup_deleted"] = len(cleanup.get("deleted", []))
        except Exception as ex:
            log_entry["ok"] = False
            log_entry["error"] = str(ex)
        append_backup_log(log_entry)


def next_backup_time_iso() -> str:
    return next_local_midnight().isoformat()


def normalize_api_path(path: str) -> str:
    if path == API_PREFIX:
        return API_PREFIX
    if path.startswith(APP_BASE_PATH + API_PREFIX + "/"):
        return path[len(APP_BASE_PATH) :]
    return path


def build_rollback_sql(table_name: str, pk_column: str, pk_value, changed_fields: dict) -> str:
    if not changed_fields:
        return ""
    set_expr = ", ".join([f"{col} = ?" for col in changed_fields.keys()])
    params = [changed_fields[col]["before"] for col in changed_fields.keys()]
    params.append(pk_value)
    return f"UPDATE {table_name} SET {set_expr} WHERE {pk_column} = {repr(pk_value)} -- params: {json.dumps(params, ensure_ascii=True)}"


def get_table_schema(table_name: str) -> list[dict]:
    with open_db() as conn:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [
        {
            "cid": row["cid"],
            "name": row["name"],
            "type": row["type"],
            "notnull": bool(row["notnull"]),
            "default": row["dflt_value"],
            "pk": bool(row["pk"]),
        }
        for row in rows
    ]


def list_query_files() -> list[dict]:
    queries: list[dict] = []
    if not QUERY_DIR.exists():
        return queries

    for path in sorted(QUERY_DIR.iterdir()):
        if not path.is_file() or path.name in EXCLUDED_QUERY_FILES:
            continue
        try:
            sql = path.read_text(encoding="utf-8").strip()
        except UnicodeDecodeError:
            continue

        if not sql:
            continue
        queries.append({"name": path.name, "sql": sql})

    return queries


def load_query_sql(query_name: str) -> str:
    if not query_name:
        raise ValueError("query_name is required")
    if "/" in query_name or ".." in query_name:
        raise ValueError("invalid query_name")

    query_path = QUERY_DIR / query_name
    if not query_path.exists() or not query_path.is_file():
        raise ValueError(f"query file not found: {query_name}")
    if query_path.name in EXCLUDED_QUERY_FILES:
        raise ValueError("query file is not allowed")

    sql = query_path.read_text(encoding="utf-8").strip()
    if not sql:
        raise ValueError("query file is empty")

    normalized = sql.lstrip().lower()
    if not normalized.startswith("select"):
        raise ValueError("only SELECT statements are supported")
    return sql


def query_rows(sql: str, params: tuple = ()) -> tuple[list[str], list[dict]]:
    with open_db() as conn:
        cur = conn.execute(sql, params)
        columns = [desc[0] for desc in (cur.description or [])]
        rows = [dict(row) for row in cur.fetchall()]
    return columns, rows


def get_status_options() -> list[dict]:
    with open_db() as conn:
        cur = conn.execute("SELECT id, name, description FROM status ORDER BY id")
        return [{"id": row["id"], "name": row["name"], "description": row["description"]} for row in cur.fetchall()]


def get_studio_names() -> list[str]:
    with open_db() as conn:
        cur = conn.execute(
            "SELECT name FROM studio WHERE media_scope IN ('p', 'p+v') ORDER BY name"
        )
        return [row["name"] for row in cur.fetchall()]


def parse_album_folder_name(folder_name: str) -> tuple[str, str]:
    cleaned = " ".join(str(folder_name or "").strip().split())
    matched = ALBUM_FOLDER_RE.match(cleaned)
    if not matched:
        raise ValueError("folder name must use '{model_name} in {album_name}' format")

    model_name = matched.group(1).strip()
    album_name = matched.group(2).strip()
    if not model_name or not album_name:
        raise ValueError("model_name and album_name are required")
    return model_name, album_name


def alphabet_for_model(model_name: str) -> str:
    for char in model_name.strip():
        if char.isalpha():
            return char.upper()
        if char.isdigit():
            return "0-9"
    return "_"


def build_album_expected_path(model_name: str, studio_name: str, album_name: str) -> str:
    return f"{alphabet_for_model(model_name)}/{model_name}/p/{studio_name}/{album_name}"


def folder_name_from_payload(body: dict) -> str:
    source_path = str(body.get("source_path") or "").strip()
    folder_name = str(body.get("folder_name") or "").strip()
    if source_path:
        return Path(source_path).name
    if folder_name:
        return folder_name
    raise ValueError("source_path or folder_name is required")


def get_import_preview(body: dict) -> dict:
    model_name, album_name = parse_album_folder_name(folder_name_from_payload(body))
    studio_name = str(body.get("studio_name") or DEFAULT_IMPORT_STUDIO).strip() or DEFAULT_IMPORT_STUDIO
    expected_path = build_album_expected_path(model_name, studio_name, album_name)

    with open_db() as conn:
        model_row = conn.execute(
            "SELECT id, name FROM model WHERE lower(name) = lower(?) ORDER BY id LIMIT 1",
            (model_name,),
        ).fetchone()
        studio_row = conn.execute(
            "SELECT id, name, media_scope FROM studio WHERE lower(name) = lower(?) ORDER BY id LIMIT 1",
            (studio_name,),
        ).fetchone()
        existing_workspace = conn.execute(
            """
            SELECT id FROM workspace_album
            WHERE lower(current_path) = lower(?) OR lower(COALESCE(expected_path, '')) = lower(?)
            ORDER BY id LIMIT 1
            """,
            (expected_path, expected_path),
        ).fetchone()

    destination = (ARCHIVE_ROOT / expected_path).resolve()
    return {
        "source_path": str(body.get("source_path") or "").strip(),
        "folder_name": folder_name_from_payload(body),
        "model_name": model_name,
        "album_name": album_name,
        "studio_name": studio_row["name"] if studio_row else studio_name,
        "model_exists": model_row is not None,
        "model_id": model_row["id"] if model_row else None,
        "studio_exists": studio_row is not None,
        "studio_id": studio_row["id"] if studio_row else None,
        "studio_media_scope": studio_row["media_scope"] if studio_row else "p",
        "expected_path": expected_path,
        "destination_path": str(destination),
        "destination_exists": destination.exists(),
        "workspace_album_exists": existing_workspace is not None,
        "workspace_album_id": existing_workspace["id"] if existing_workspace else None,
        "default_studio": DEFAULT_IMPORT_STUDIO,
        "archive_root": str(ARCHIVE_ROOT),
    }


def ensure_casefold_entity(conn: sqlite3.Connection, table: str, name: str, extra: dict | None = None) -> tuple[int, bool]:
    if table not in {"model", "studio"}:
        raise ValueError("unsupported entity table")
    row = conn.execute(
        f"SELECT id FROM {table} WHERE lower(name) = lower(?) ORDER BY id LIMIT 1",
        (name,),
    ).fetchone()
    if row is not None:
        return int(row["id"]), False

    if table == "studio":
        media_scope = str((extra or {}).get("media_scope") or "p").strip() or "p"
        cur = conn.execute("INSERT INTO studio (name, media_scope) VALUES (?, ?)", (name, media_scope))
    else:
        cur = conn.execute("INSERT INTO model (name) VALUES (?)", (name,))
    return int(cur.lastrowid), True


def ensure_destination_is_safe(source_path: Path, destination_path: Path) -> None:
    source_resolved = source_path.resolve()
    destination_resolved = destination_path.resolve()
    archive_resolved = ARCHIVE_ROOT.resolve()

    if not source_resolved.exists() or not source_resolved.is_dir():
        raise FileNotFoundError(f"source folder not found: {source_resolved}")
    if destination_resolved.exists():
        raise FileExistsError(f"destination already exists: {destination_resolved}")
    if archive_resolved not in destination_resolved.parents:
        raise ValueError("destination must be inside Archive")
    if source_resolved == destination_resolved:
        raise ValueError("source and destination are the same folder")
    if source_resolved in destination_resolved.parents:
        raise ValueError("destination cannot be inside source folder")


def import_single_album(body: dict) -> dict:
    preview = get_import_preview(body)
    source_raw = str(body.get("source_path") or "").strip()
    if not source_raw:
        raise ValueError("source_path is required for import")

    model_name = str(body.get("model_name") or preview["model_name"]).strip()
    album_name = str(body.get("album_name") or preview["album_name"]).strip()
    studio_name = str(body.get("studio_name") or preview["studio_name"] or DEFAULT_IMPORT_STUDIO).strip()
    keep_source = bool(body.get("keep_source"))

    if not model_name or not album_name or not studio_name:
        raise ValueError("model_name, album_name and studio_name are required")

    expected_path = build_album_expected_path(model_name, studio_name, album_name)
    source_path = Path(source_raw).expanduser()
    destination_path = ARCHIVE_ROOT / expected_path
    ensure_destination_is_safe(source_path, destination_path)

    pre_update_snapshot = ""
    try:
        snapshot = create_db_snapshot(reason="pre_album_import")
        pre_update_snapshot = str(snapshot)
        append_backup_log(
            {
                "timestamp": utc_now_iso(),
                "reason": "pre_album_import",
                "ok": True,
                "snapshot": pre_update_snapshot,
                "tag": "",
            }
        )
    except Exception as ex:
        raise RuntimeError(f"failed to create pre-import snapshot: {ex}") from ex

    workspace_album_id = None
    created_model = False
    created_studio = False
    try:
        with open_db() as conn:
            conn.execute("BEGIN")
            model_id, created_model = ensure_casefold_entity(conn, "model", model_name)
            studio_id, created_studio = ensure_casefold_entity(
                conn,
                "studio",
                studio_name,
                {"media_scope": "p"},
            )

            existing = conn.execute(
                """
                SELECT id FROM workspace_album
                WHERE lower(current_path) = lower(?) OR lower(COALESCE(expected_path, '')) = lower(?)
                ORDER BY id LIMIT 1
                """,
                (expected_path, expected_path),
            ).fetchone()
            if existing is not None:
                raise ValueError(f"workspace_album already has this path: id={existing['id']}")

            cur = conn.execute(
                """
                INSERT INTO workspace_album (
                    current_path,
                    expected_path,
                    primary_model,
                    studio_name,
                    album_name,
                    additional_models,
                    status_id,
                    remark
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    expected_path,
                    expected_path,
                    model_name,
                    studio_name,
                    album_name,
                    None,
                    STATUS_RENAMED,
                    f"Imported from {source_path.resolve()}",
                ),
            )
            workspace_album_id = int(cur.lastrowid)
            conn.commit()

        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if keep_source:
            shutil.copytree(source_path, destination_path)
        else:
            shutil.move(str(source_path), str(destination_path))

        with open_db() as conn:
            conn.execute(
                "UPDATE workspace_album SET status_id = ? WHERE id = ?",
                (STATUS_IMPORTED, workspace_album_id),
            )
            conn.commit()

        result = {
            "timestamp": utc_now_iso(),
            "operation": "import_single_album",
            "success": True,
            "workspace_album_id": workspace_album_id,
            "source_path": str(source_path.resolve()),
            "destination_path": str(destination_path.resolve()),
            "expected_path": expected_path,
            "model_name": model_name,
            "model_id": model_id,
            "created_model": created_model,
            "studio_name": studio_name,
            "studio_id": studio_id,
            "created_studio": created_studio,
            "keep_source": keep_source,
            "pre_operation_snapshot": pre_update_snapshot,
            "rollback_sql": [
                f"DELETE FROM workspace_album WHERE id = {workspace_album_id}",
            ],
        }
        append_log(result)
        return result
    except Exception as ex:
        destination_exists_after_failure = destination_path.exists()
        cleanup_result = "not_needed"
        if workspace_album_id is not None:
            try:
                with open_db() as conn:
                    if destination_exists_after_failure:
                        conn.execute(
                            """
                            UPDATE workspace_album
                            SET status_id = ?, remark = ?
                            WHERE id = ?
                            """,
                            (
                                1,
                                f"Import failed after filesystem operation: {ex}",
                                workspace_album_id,
                            ),
                        )
                        cleanup_result = "marked_wait_manual"
                    else:
                        conn.execute(
                            "DELETE FROM workspace_album WHERE id = ? AND status_id = ?",
                            (workspace_album_id, STATUS_RENAMED),
                        )
                        cleanup_result = "deleted_incomplete_workspace_row"
                    conn.commit()
            except Exception as cleanup_ex:
                cleanup_result = f"cleanup_failed: {cleanup_ex}"

        failure = {
            "timestamp": utc_now_iso(),
            "operation": "import_single_album",
            "success": False,
            "workspace_album_id": workspace_album_id,
            "source_path": source_raw,
            "expected_path": expected_path,
            "error": str(ex),
            "destination_exists_after_failure": destination_exists_after_failure,
            "cleanup_result": cleanup_result,
            "pre_operation_snapshot": pre_update_snapshot,
        }
        append_log(failure)
        raise


def build_workspace_album_sql(status_id: int, studio_name: str) -> tuple[str, tuple]:
    if studio_name:
        sql = "SELECT * FROM workspace_album WHERE status_id = ? AND studio_name = ? ORDER BY id"
        return sql, (status_id, studio_name)
    sql = "SELECT * FROM workspace_album WHERE status_id = ? ORDER BY id"
    return sql, (status_id,)


def append_log(entry: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        body = self.rfile.read(content_length)
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def _send_json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, socket.error):
            # Client disconnected while response was in flight.
            return

    def do_GET(self):
        parsed = urlparse(self.path)
        api_path = normalize_api_path(parsed.path)

        if parsed.path == APP_BASE_PATH:
            self.send_response(301)
            self.send_header("Location", APP_BASE_PATH + "/")
            self.end_headers()
            return

        if parsed.path in {"/", APP_BASE_PATH + "/"}:
            self.path = "/index.html"
            return super().do_GET()

        if parsed.path.startswith(APP_BASE_PATH + "/") and not parsed.path.startswith(APP_BASE_PATH + API_PREFIX + "/"):
            self.path = parsed.path[len(APP_BASE_PATH) :]
            if parsed.query:
                self.path += "?" + parsed.query
            return super().do_GET()

        if api_path == "/api/health":
            backup_catalog = build_backup_catalog()
            self._send_json(
                200,
                {
                    "ok": True,
                    "database_path": str(DATABASE_PATH),
                    "server_time": utc_now_iso(),
                    "next_backup_at": next_backup_time_iso(),
                    "backup_path": str(BACKUP_DIR),
                    "backup_log_path": str(BACKUP_LOG_PATH),
                    "rollback_log_path": str(ROLLBACK_LOG_PATH),
                    "retention_days": RETENTION_DAYS,
                    "backup_count": len(backup_catalog),
                    "protected_backup_count": len([x for x in backup_catalog if x["protected"]]),
                    "archive_root": str(ARCHIVE_ROOT),
                },
            )
            return

        if api_path == "/api/queries":
            self._send_json(200, {"ok": True, "queries": list_query_files()})
            return

        if api_path == "/api/options":
            try:
                statuses = get_status_options()
                studios = get_studio_names()
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "statuses": statuses,
                        "studios": studios,
                        "default_import_studio": DEFAULT_IMPORT_STUDIO,
                    },
                )
            except Exception as ex:
                self._send_json(500, {"ok": False, "error": str(ex)})
            return

        if api_path == "/api/schema":
            qs = parse_qs(parsed.query)
            table_name = (qs.get("table") or ["workspace_album"])[0]
            if table_name not in ALLOWED_TABLES:
                self._send_json(400, {"ok": False, "error": "table is not allowed"})
                return
            schema = get_table_schema(table_name)
            self._send_json(200, {"ok": True, "table": table_name, "schema": schema})
            return

        if api_path == "/api/backups":
            catalog = build_backup_catalog()
            items = [public_backup_item(item) for item in catalog]
            self._send_json(
                200,
                {
                    "ok": True,
                    "retention_days": RETENTION_DAYS,
                    "items": items,
                },
            )
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        api_path = normalize_api_path(parsed.path)

        try:
            body = self._read_json_body()
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid json body"})
            return

        if api_path == "/api/run-query":
            try:
                raw_status_id = body.get("status_id")
                if raw_status_id is None:
                    raise ValueError("status_id is required")
                status_id = int(raw_status_id)
                studio_name = str(body.get("studio_name", "")).strip()
                sql, params = build_workspace_album_sql(status_id, studio_name)
                columns, rows = query_rows(sql, params)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "status_id": status_id,
                        "studio_name": studio_name,
                        "sql": sql,
                        "columns": columns,
                        "rows": rows,
                        "row_count": len(rows),
                    },
                )
            except Exception as ex:
                self._send_json(400, {"ok": False, "error": str(ex)})
            return

        if api_path == "/api/import-album/preview":
            try:
                preview = get_import_preview(body)
                self._send_json(200, {"ok": True, "preview": preview})
            except Exception as ex:
                self._send_json(400, {"ok": False, "error": str(ex)})
            return

        if api_path == "/api/import-album":
            try:
                result = import_single_album(body)
                self._send_json(200, {"ok": True, "result": result})
            except Exception as ex:
                self._send_json(400, {"ok": False, "error": str(ex)})
            return

        if api_path == "/api/batch-update":
            table_name = str(body.get("table", "workspace_album")).strip()
            pk_column = str(body.get("pk_column", "id")).strip()
            updates = body.get("updates", [])

            if table_name not in ALLOWED_TABLES:
                self._send_json(400, {"ok": False, "error": "table is not allowed"})
                return

            if not isinstance(updates, list) or not updates:
                self._send_json(400, {"ok": False, "error": "updates must be a non-empty list"})
                return

            schema = get_table_schema(table_name)
            schema_names = {col["name"] for col in schema}
            pk_schema = next((col for col in schema if col["pk"]), None)

            if pk_schema is None:
                self._send_json(400, {"ok": False, "error": "table has no primary key"})
                return

            real_pk_column = pk_schema["name"]
            if pk_column != real_pk_column:
                self._send_json(400, {"ok": False, "error": f"pk_column must be {real_pk_column}"})
                return

            invalid_columns = []
            for item in updates:
                changes = item.get("changes", {})
                if not isinstance(changes, dict):
                    invalid_columns.append("<invalid changes payload>")
                    continue
                for col in changes.keys():
                    if col == pk_column or col not in schema_names:
                        invalid_columns.append(col)

            if invalid_columns:
                self._send_json(
                    400,
                    {
                        "ok": False,
                        "error": "invalid columns in changes",
                        "columns": sorted(set(invalid_columns)),
                    },
                )
                return

            results: list[dict] = []
            changed_total = 0
            update_errors: list[str] = []
            pre_update_snapshot = ""

            try:
                pre_snapshot = create_db_snapshot(reason="pre_update")
                pre_update_snapshot = str(pre_snapshot)
                append_backup_log(
                    {
                        "timestamp": utc_now_iso(),
                        "reason": "pre_update",
                        "ok": True,
                        "snapshot": pre_update_snapshot,
                        "tag": "",
                    }
                )
            except Exception as ex:
                self._send_json(500, {"ok": False, "error": f"failed to create pre-update snapshot: {ex}"})
                return

            try:
                with open_db() as conn:
                    conn.execute("BEGIN")
                    for idx, item in enumerate(updates, start=1):
                        pk_value = item.get("pk_value")
                        changes = item.get("changes", {})

                        if pk_value is None:
                            raise ValueError(f"row #{idx}: pk_value is required")
                        if not isinstance(changes, dict) or not changes:
                            continue

                        before = conn.execute(
                            f"SELECT * FROM {table_name} WHERE {pk_column} = ?",
                            (pk_value,),
                        ).fetchone()
                        if before is None:
                            raise ValueError(f"row #{idx}: record with {pk_column}={pk_value} not found")

                        set_columns = [col for col in changes.keys() if col != pk_column]
                        if not set_columns:
                            continue

                        set_expr = ", ".join([f"{col} = ?" for col in set_columns])
                        values = [changes[col] for col in set_columns]
                        values.append(pk_value)

                        conn.execute(
                            f"UPDATE {table_name} SET {set_expr} WHERE {pk_column} = ?",
                            values,
                        )

                        after = conn.execute(
                            f"SELECT * FROM {table_name} WHERE {pk_column} = ?",
                            (pk_value,),
                        ).fetchone()

                        before_dict = dict(before)
                        after_dict = dict(after) if after is not None else {}
                        changed_fields = {
                            col: {"before": before_dict.get(col), "after": after_dict.get(col)}
                            for col in set_columns
                            if before_dict.get(col) != after_dict.get(col)
                        }
                        if changed_fields:
                            changed_total += 1
                            results.append(
                                {
                                    "pk_value": pk_value,
                                    "changed_fields": changed_fields,
                                }
                            )

                    conn.commit()
            except Exception as ex:
                update_errors.append(str(ex))

            log_entry = {
                "timestamp": utc_now_iso(),
                "table": table_name,
                "pk_column": pk_column,
                "requested_updates": len(updates),
                "applied_updates": changed_total,
                "success": not update_errors,
                "errors": update_errors,
                "results": results,
                "pre_operation_snapshot": pre_update_snapshot,
                "rollback_sql": [
                    build_rollback_sql(table_name, pk_column, row["pk_value"], row["changed_fields"])
                    for row in results
                ],
            }
            append_log(log_entry)

            if update_errors:
                self._send_json(
                    500,
                    {
                        "ok": False,
                        "error": "batch update failed",
                        "details": update_errors,
                    },
                )
                return

            self._send_json(
                200,
                {
                    "ok": True,
                    "message": "batch update succeeded",
                    "applied_updates": changed_total,
                    "results": results,
                    "log_path": str(LOG_PATH),
                },
            )
            return

        if api_path == "/api/backup-now":
            reason = str(body.get("reason", "manual")).strip() or "manual"
            tag = str(body.get("tag", "")).strip()
            try:
                snapshot = create_db_snapshot(reason=reason, tag=tag)
                backup_entry = {
                    "timestamp": utc_now_iso(),
                    "reason": f"manual_{reason}",
                    "ok": True,
                    "snapshot": str(snapshot),
                    "tag": normalize_tag(tag),
                }
                append_backup_log(backup_entry)
                cleanup = cleanup_expired_snapshots(RETENTION_DAYS)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "snapshot": str(snapshot),
                        "tag": normalize_tag(tag),
                        "backup_log_path": str(BACKUP_LOG_PATH),
                        "cleanup_deleted": len(cleanup.get("deleted", [])),
                    },
                )
            except Exception as ex:
                append_backup_log(
                    {
                        "timestamp": utc_now_iso(),
                        "reason": f"manual_{reason}",
                        "ok": False,
                        "error": str(ex),
                        "tag": normalize_tag(tag),
                    }
                )
                self._send_json(500, {"ok": False, "error": str(ex)})
            return

        if api_path == "/api/backups/cleanup":
            try:
                cleanup = cleanup_expired_snapshots(RETENTION_DAYS)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "deleted": cleanup.get("deleted", []),
                        "failed": cleanup.get("failed", []),
                        "retention_days": RETENTION_DAYS,
                    },
                )
            except Exception as ex:
                self._send_json(500, {"ok": False, "error": str(ex)})
            return

        if api_path == "/api/backups/delete":
            snapshot = str(body.get("snapshot", "")).strip()
            if not snapshot:
                self._send_json(400, {"ok": False, "error": "snapshot is required"})
                return
            target = Path(snapshot)
            if not target.is_absolute():
                target = BACKUP_DIR / target
            try:
                resolved = target.resolve()
            except Exception:
                self._send_json(400, {"ok": False, "error": "invalid snapshot path"})
                return

            if BACKUP_DIR.resolve() not in resolved.parents:
                self._send_json(400, {"ok": False, "error": "snapshot must be under backup directory"})
                return
            if not resolved.exists() or not resolved.is_file():
                self._send_json(404, {"ok": False, "error": "snapshot not found"})
                return

            try:
                resolved.unlink()
                append_backup_log(
                    {
                        "timestamp": utc_now_iso(),
                        "reason": "manual_delete",
                        "ok": True,
                        "snapshot": str(resolved),
                    }
                )
                self._send_json(200, {"ok": True, "deleted": str(resolved)})
            except Exception as ex:
                self._send_json(500, {"ok": False, "error": str(ex)})
            return

        if api_path == "/api/rollback":
            mode = str(body.get("mode", "before_last_operation")).strip()
            selected: dict | None = None

            try:
                if mode == "before_last_operation":
                    last_change = get_last_success_change_entry()
                    if last_change is None:
                        raise ValueError("no successful operation found in changes log")
                    pre_snapshot = str(last_change.get("pre_operation_snapshot") or "").strip()
                    if pre_snapshot:
                        candidate = Path(pre_snapshot)
                        if candidate.exists() and candidate.is_file():
                            created = parse_snapshot_created_at(candidate)
                            selected = {
                                "snapshot": str(candidate.resolve()),
                                "filename": candidate.name,
                                "created_at": created.isoformat()
                                if created
                                else datetime.fromtimestamp(candidate.stat().st_mtime, tz=local_now().tzinfo).isoformat(),
                                "tag": parse_tag_from_name(candidate),
                                "protected": bool(parse_tag_from_name(candidate)),
                            }

                    if selected is None:
                        ts = last_change.get("timestamp")
                        if not ts:
                            raise ValueError("last change has no timestamp")
                        selected = find_snapshot_before_or_at(parse_iso_datetime(str(ts)))
                        if selected is None:
                            raise ValueError("no snapshot found before last operation")
                elif mode == "timestamp":
                    raw_ts = str(body.get("timestamp", "")).strip()
                    if not raw_ts:
                        raise ValueError("timestamp is required when mode=timestamp")
                    target_ts = parse_iso_datetime(raw_ts)
                    selected = find_snapshot_before_or_at(target_ts)
                    if selected is None:
                        raise ValueError("no snapshot found before the specified timestamp")
                elif mode == "tag":
                    tag = str(body.get("tag", "")).strip()
                    if not tag:
                        raise ValueError("tag is required when mode=tag")
                    selected = find_snapshot_by_tag(tag)
                    if selected is None:
                        raise ValueError(f"no snapshot found for tag: {tag}")
                elif mode == "snapshot":
                    snapshot = str(body.get("snapshot", "")).strip()
                    if not snapshot:
                        raise ValueError("snapshot is required when mode=snapshot")
                    target = Path(snapshot)
                    if not target.is_absolute():
                        target = BACKUP_DIR / target
                    resolved = target.resolve()
                    if not resolved.exists() or not resolved.is_file():
                        raise ValueError("specified snapshot does not exist")
                    selected = {
                        "snapshot": str(resolved),
                        "filename": resolved.name,
                        "created_at": parse_snapshot_created_at(resolved).isoformat()
                        if parse_snapshot_created_at(resolved)
                        else datetime.fromtimestamp(resolved.stat().st_mtime, tz=local_now().tzinfo).isoformat(),
                        "tag": parse_tag_from_name(resolved),
                        "protected": bool(parse_tag_from_name(resolved)),
                    }
                else:
                    raise ValueError("unsupported rollback mode")

                if selected is None:
                    raise ValueError("rollback target snapshot could not be resolved")

                # Always create a safety snapshot before restoring target data.
                safety = create_db_snapshot(reason="pre_rollback", tag="auto_safety")
                append_backup_log(
                    {
                        "timestamp": utc_now_iso(),
                        "reason": "pre_rollback",
                        "ok": True,
                        "snapshot": str(safety),
                        "tag": "auto_safety",
                    }
                )

                restore_database_from_snapshot(Path(selected["snapshot"]))

                rollback_entry = {
                    "timestamp": utc_now_iso(),
                    "mode": mode,
                    "selected_snapshot": public_backup_item(selected),
                    "safety_snapshot": str(safety),
                    "ok": True,
                }
                append_rollback_log(rollback_entry)
                self._send_json(
                    200,
                    {
                        "ok": True,
                        "mode": mode,
                        "selected_snapshot": public_backup_item(selected),
                        "safety_snapshot": str(safety),
                        "rollback_log_path": str(ROLLBACK_LOG_PATH),
                    },
                )
            except Exception as ex:
                append_rollback_log(
                    {
                        "timestamp": utc_now_iso(),
                        "mode": mode,
                        "ok": False,
                        "error": str(ex),
                    }
                )
                self._send_json(400, {"ok": False, "error": str(ex)})
            return

        self._send_json(404, {"ok": False, "error": "endpoint not found"})


def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    if not STATIC_DIR.exists():
        raise FileNotFoundError(f"Static directory not found: {STATIC_DIR}")

    host = "127.0.0.1"
    port = 8787
    backup_thread = threading.Thread(target=run_daily_backup, name="daily-backup", daemon=True)
    backup_thread.start()

    try:
        startup_snapshot = create_db_snapshot("startup")
        append_backup_log(
            {
                "timestamp": utc_now_iso(),
                "reason": "startup",
                "ok": True,
                "snapshot": str(startup_snapshot),
                "tag": "",
            }
        )
    except Exception as ex:
        append_backup_log(
            {
                "timestamp": utc_now_iso(),
                "reason": "startup",
                "ok": False,
                "error": str(ex),
                "tag": "",
            }
        )

    cleanup_expired_snapshots(RETENTION_DAYS)

    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Curator Base App running at http://{host}:{port}{APP_BASE_PATH}")
    print(f"Database: {DATABASE_PATH}")
    print(f"Logs: {LOG_PATH}")
    print(f"Backups: {BACKUP_DIR}")
    print(f"Backup logs: {BACKUP_LOG_PATH}")
    print(f"Rollback logs: {ROLLBACK_LOG_PATH}")
    print(f"Retention days: {RETENTION_DAYS}")

    try:
        server.serve_forever()
    finally:
        STOP_EVENT.set()
        backup_thread.join(timeout=3)


if __name__ == "__main__":
    main()
