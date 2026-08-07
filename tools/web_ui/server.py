#!/usr/bin/env python3
import json
import os
import re
import shutil
import sqlite3
import socket
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import api_contract
import repositories as repo
import services as svc

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent  # tools/web_ui/../../ = project root
STATIC_DIR = BASE_DIR / "static"
DATABASE_PATH = REPO_ROOT / "database" / "Curator.db"
CONFIG_PATH = BASE_DIR / "app_config.json"
LOG_PATH = BASE_DIR / "logs" / "changes.log"
BACKUP_DIR = BASE_DIR / "backups"
BACKUP_LOG_PATH = BASE_DIR / "logs" / "backup.log"
ROLLBACK_LOG_PATH = BASE_DIR / "logs" / "rollback.log"

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
DEFAULT_APP_CONFIG = {
    "import_source_root": "/Volumes/NAS-RAID5/RAID/Prime_Media/[Temp]/p",
    "archive_root": "/Volumes/NAS-RAID5/RAID/Prime_Media/Archive",
    "default_import_studio": "MetArt",
}

# ---------------------------------------------------------------------------
# Global constants
# ---------------------------------------------------------------------------
STOP_EVENT = threading.Event()
RETENTION_DAYS = 15
BACKUP_NAME_RE = re.compile(r"^Curator_(\d{8}_\d{6})_(.+)\.db$")
ALBUM_FOLDER_RE = re.compile(r"^(.+?)\s+in\s+(.+)$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_app_config() -> dict:
    cfg = dict(DEFAULT_APP_CONFIG)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                on_disk = json.load(fh)
            for key in ("import_source_root", "archive_root", "default_import_studio"):
                if key in on_disk:
                    cfg[key] = on_disk[key]
        except Exception:
            pass
    return cfg


APP_CONFIG = load_app_config()
AUTH_REGISTRATION_SECRET = os.environ.get("CURATOR_REGISTRATION_SECRET", "")

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DATABASE_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def local_now() -> datetime:
    return datetime.now().astimezone()


def next_local_midnight(now: datetime = None) -> datetime:
    if now is None:
        now = local_now()
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return tomorrow


def sanitize_ts(value: datetime) -> str:
    return value.strftime("%Y%m%d_%H%M%S")


def sanitize_label(value: str, default: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_")
    return cleaned if cleaned else default


def normalize_tag(tag: str) -> str:
    return sanitize_label(tag, "")


def parse_iso_datetime(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

# ---------------------------------------------------------------------------
# Log helpers
# ---------------------------------------------------------------------------

def append_json_log(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=True) + "\n")


def read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    results = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return results


def append_backup_log(entry: dict) -> None:
    append_json_log(BACKUP_LOG_PATH, entry)


def append_rollback_log(entry: dict) -> None:
    append_json_log(ROLLBACK_LOG_PATH, entry)


def append_log(entry: dict) -> None:
    append_json_log(LOG_PATH, entry)

# ---------------------------------------------------------------------------
# Backup functions
# ---------------------------------------------------------------------------

def create_db_snapshot(reason: str, tag: str = "") -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = sanitize_ts(local_now())
    safe_reason = sanitize_label(reason, "backup")
    label = f"{safe_reason}_tag-{normalize_tag(tag)}" if tag else safe_reason
    filename = f"Curator_{ts}_{label}.db"
    dest = BACKUP_DIR / filename
    src_conn = sqlite3.connect(str(DATABASE_PATH))
    try:
        dst_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    return dest


def parse_snapshot_created_at(path: Path) -> datetime | None:
    m = BACKUP_NAME_RE.match(path.name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def parse_tag_from_name(path: Path) -> str:
    m = BACKUP_NAME_RE.match(path.name)
    if not m:
        return ""
    label = m.group(2)
    tag_marker = "_tag-"
    idx = label.find(tag_marker)
    if idx == -1:
        return ""
    return label[idx + len(tag_marker):]


def load_backup_metadata() -> dict:
    entries = read_jsonl(BACKUP_LOG_PATH)
    result = {}
    for e in entries:
        snap = e.get("snapshot")
        if snap:
            result[str(Path(snap).resolve())] = e
    return result


def build_backup_catalog() -> list:
    if not BACKUP_DIR.exists():
        return []
    metadata = load_backup_metadata()
    items = []
    for db_file in BACKUP_DIR.glob("*.db"):
        created_at_dt = parse_snapshot_created_at(db_file)
        tag = parse_tag_from_name(db_file)
        key = str(db_file.resolve())
        meta = metadata.get(key, {})
        protected = meta.get("protected", False)
        item = {
            "filename": db_file.name,
            "path": str(db_file),
            "size_bytes": db_file.stat().st_size if db_file.exists() else 0,
            "created_at": created_at_dt.isoformat() if created_at_dt else None,
            "tag": tag,
            "reason": meta.get("reason", ""),
            "protected": protected,
            "_created_at_dt": created_at_dt,
        }
        items.append(item)
    items.sort(
        key=lambda x: x["_created_at_dt"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return items


def cleanup_expired_snapshots(retention_days: int) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    catalog = build_backup_catalog()
    deleted = []
    failed = []
    for item in catalog:
        if item.get("protected"):
            continue
        dt = item.get("_created_at_dt")
        if dt is None:
            continue
        if dt < cutoff:
            p = Path(item["path"])
            try:
                p.unlink(missing_ok=True)
                deleted.append(item["filename"])
                append_backup_log(
                    {
                        "timestamp": utc_now_iso(),
                        "event": "cleanup",
                        "filename": item["filename"],
                        "ok": True,
                    }
                )
            except Exception as ex:
                failed.append({"filename": item["filename"], "error": str(ex)})
    return {"deleted": deleted, "failed": failed}


def find_snapshot_before_or_at(target_dt: datetime) -> dict | None:
    catalog = build_backup_catalog()
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)
    candidates = [
        x for x in catalog
        if x.get("_created_at_dt") is not None and x["_created_at_dt"] <= target_dt
    ]
    if not candidates:
        return None
    return candidates[0]  # already sorted newest-first


def public_backup_item(item: dict) -> dict:
    return {k: v for k, v in item.items() if not k.startswith("_")}


def find_snapshot_by_tag(tag: str) -> dict | None:
    catalog = build_backup_catalog()
    for item in catalog:
        if item.get("tag") == tag:
            return item
    return None


def get_last_success_change_entry() -> dict | None:
    entries = read_jsonl(LOG_PATH)
    for entry in reversed(entries):
        if entry.get("success") is True:
            return entry
    return None


def restore_database_from_snapshot(snapshot_path: Path) -> None:
    src_conn = sqlite3.connect(str(snapshot_path))
    try:
        dst_conn = sqlite3.connect(str(DATABASE_PATH))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def next_backup_time_iso() -> str:
    return next_local_midnight().isoformat()


def run_daily_backup() -> None:
    while not STOP_EVENT.is_set():
        now = local_now()
        target = next_local_midnight(now)
        wait_seconds = (target - now).total_seconds()
        if wait_seconds > 0:
            STOP_EVENT.wait(timeout=wait_seconds)
        if STOP_EVENT.is_set():
            break
        try:
            snap = create_db_snapshot("daily")
            cleanup_expired_snapshots(RETENTION_DAYS)
            append_backup_log(
                {
                    "timestamp": utc_now_iso(),
                    "reason": "daily",
                    "ok": True,
                    "snapshot": str(snap),
                    "tag": "",
                }
            )
        except Exception as ex:
            append_backup_log(
                {
                    "timestamp": utc_now_iso(),
                    "reason": "daily",
                    "ok": False,
                    "error": str(ex),
                    "tag": "",
                }
            )
        # Sleep at least 60s to avoid double-firing near midnight
        STOP_EVENT.wait(timeout=60)

# ---------------------------------------------------------------------------
# AppHandler
# ---------------------------------------------------------------------------

class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self._request_id = api_contract.generate_request_id()
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format, *args):
        pass  # suppress console log noise

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
            return

    def _send_success(self, status: int, data, *, meta_extras: dict | None = None) -> None:
        """Send a contract success envelope with the given data payload."""
        self._send_json(
            status,
            api_contract.success_response(
                data, request_id=self._request_id, meta_extras=meta_extras
            ),
        )

    def _send_error(
        self,
        status: int,
        code: str,
        message: str,
        *,
        details: dict | None = None,
        fields: dict | None = None,
        meta_extras: dict | None = None,
    ) -> None:
        """Send a contract error envelope."""
        self._send_json(
            status,
            api_contract.error_response(
                code,
                message,
                request_id=self._request_id,
                details=details,
                fields=fields,
                meta_extras=meta_extras,
            ),
        )

    def _send_collection(
        self,
        data: list,
        *,
        limit: int,
        offset: int,
        total: int | None,
        filters: list | None = None,
        sort: list | None = None,
    ) -> None:
        """Send a contract collection response with pagination metadata."""
        has_more = total is not None and (offset + limit) < total
        next_offset = offset + limit if has_more else None
        cursor = api_contract.encode_cursor(offset) if offset > 0 else None
        next_cursor = (
            api_contract.encode_cursor(next_offset)
            if next_offset is not None
            else None
        )
        meta_extras = api_contract.build_collection_meta(
            cursor=cursor,
            limit=limit,
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
            filters=filters or [],
            sort=sort or [],
        )
        self._send_json(
            200,
            api_contract.success_response(
                data, request_id=self._request_id, meta_extras=meta_extras
            ),
        )

    @staticmethod
    def _required_scope(path: str, method: str) -> str:
        """Return the least privilege required by a versioned API route."""
        if path in {"/api/backup", "/api/backup/cleanup", "/api/rollback"} or path.startswith("/api/backups"):
            return "admin"
        return "read" if method == "GET" else "write"

    def _authorize_versioned_api(self, path: str, method: str) -> bool:
        """Authenticate before dispatching any normal ``/api/v1`` operation."""
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer ") or not header[7:].strip():
            self._send_error(401, "AUTHENTICATION_MISSING_TOKEN", "A bearer token is required.")
            return False
        auth_service = svc.AuthenticationService(repo.AuthRepository(open_db))
        try:
            self._principal = auth_service.authenticate(
                header[7:].strip(), self._required_scope(path, method)
            )
        except svc.AuthenticationFailure as exc:
            self._send_error(401, exc.code, str(exc))
            return False
        except svc.AuthorizationFailure as exc:
            self._send_error(
                403, exc.code, str(exc), details={"required_scope": exc.required_scope}
            )
            return False
        return True

    @staticmethod
    def _versioned_path_to_legacy(path: str) -> str:
        """Map the established resource handlers onto the versioned boundary."""
        suffix = path[len("/api/v1"):]
        return "/api" + suffix

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path.startswith("/api/v1/"):
            legacy_path = self._versioned_path_to_legacy(path)
            if not self._authorize_versioned_api(legacy_path, "GET"):
                return
            self._handle_api_get(legacy_path, qs)
            return
        if path.startswith("/api/"):
            self._handle_api_get(path, qs)
            return
        if "." in path.split("/")[-1]:
            super().do_GET()
            return
        self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/auth/"):
            try:
                body = self._read_json_body()
            except Exception:
                self._send_error(400, "REQUEST_INVALID_JSON", "The request body contains invalid JSON.")
                return
            self._handle_auth_management_post(path, body)
            return
        if path.startswith("/api/v1/"):
            legacy_path = self._versioned_path_to_legacy(path)
            if not self._authorize_versioned_api(legacy_path, "POST"):
                return
            path = legacy_path
        try:
            body = self._read_json_body()
        except Exception:
            self._send_error(400, "REQUEST_INVALID_JSON", "The request body contains invalid JSON.")
            return
        self._handle_api_post(path, body)

    def _handle_auth_management_post(self, path: str, body: dict) -> None:
        """Loopback-only registration management, outside normal bearer auth."""
        if self.client_address[0] not in {"127.0.0.1", "::1"}:
            self._send_error(403, "AUTHORIZATION_LOOPBACK_REQUIRED", "Authentication management is available only on loopback.")
            return
        auth = svc.AuthenticationService(
            repo.AuthRepository(open_db), registration_secret=AUTH_REGISTRATION_SECRET,
            operation_service=svc.OperationService(repo.OperationRepository(open_db)),
        )
        try:
            if path == "/api/auth/registrations":
                registration = auth.request_registration(
                    device_name=body.get("device_name", ""), device_identity=body.get("device_identity", ""),
                    requested_role=body.get("requested_role", ""), requested_scopes=body.get("requested_scopes"),
                    registration_proof=body.get("registration_proof", ""),
                )
                self._send_success(201, {"registration": registration})
            elif re.match(r"^/api/auth/registrations/[^/]+/approve$", path):
                registration_uuid = path.split("/")[4]
                issued = auth.approve_registration(registration_uuid, approved_role=body.get("approved_role"), approved_scopes=body.get("approved_scopes"))
                self._send_success(200, issued)
            else:
                self._send_error(404, "NOT_FOUND", "The requested resource was not found.")
        except svc.AuthenticationFailure as exc:
            self._send_error(401, exc.code, str(exc))
        except svc.AuthorizationFailure as exc:
            self._send_error(403, exc.code, str(exc))
        except (svc.ServiceConflict, ValueError) as exc:
            self._send_error(409, getattr(exc, "code", "BUSINESS_CONFLICT"), str(exc))

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/v1/"):
            legacy_path = self._versioned_path_to_legacy(path)
            if not self._authorize_versioned_api(legacy_path, "PUT"):
                return
            path = legacy_path
        try:
            body = self._read_json_body()
        except Exception:
            self._send_error(400, "REQUEST_INVALID_JSON", "The request body contains invalid JSON.")
            return
        self._handle_api_put(path, body)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/v1/"):
            legacy_path = self._versioned_path_to_legacy(path)
            if not self._authorize_versioned_api(legacy_path, "DELETE"):
                return
            path = legacy_path
        self._handle_api_delete(path)

    # ------------------------------------------------------------------
    # GET handlers
    # ------------------------------------------------------------------

    def _handle_api_get(self, path: str, qs: dict) -> None:
        try:
            if path == "/api/health":
                self._get_health()
            elif path == "/api/config":
                self._get_config()
            elif path == "/api/statuses":
                self._get_statuses()
            elif path == "/api/models":
                self._get_models(qs)
            elif re.match(r"^/api/models/\d+$", path):
                model_id = int(path.split("/")[-1])
                self._get_model(model_id)
            elif path == "/api/studios":
                self._get_studios(qs)
            elif re.match(r"^/api/studios/\d+$", path):
                studio_id = int(path.split("/")[-1])
                self._get_studio(studio_id)
            elif path == "/api/albums":
                self._get_albums(qs)
            elif re.match(r"^/api/albums/\d+$", path):
                album_id = int(path.split("/")[-1])
                self._get_album(album_id)
            elif path == "/api/workspace/albums":
                self._get_workspace_albums(qs)
            elif re.match(r"^/api/workspace/albums/\d+$", path):
                wa_id = int(path.split("/")[-1])
                self._get_workspace_album(wa_id)
            elif path == "/api/backups":
                self._get_backups()
            elif path == "/api/operations":
                self._get_operations(qs)
            elif re.match(r"^/api/operations/[^/]+$", path):
                self._get_operation(path.split("/")[-1])
            else:
                self._send_error(404, "NOT_FOUND", "The requested resource was not found.")
        except Exception:
            self._send_error(500, "INTERNAL_ERROR", "An unexpected server error occurred.")

    def _get_health(self):
        backup_catalog = build_backup_catalog()
        self._send_success(
            200,
            {
                "database_path": str(DATABASE_PATH),
                "server_time": utc_now_iso(),
                "next_backup_at": next_backup_time_iso(),
                "backup_count": len(backup_catalog),
                "db_exists": DATABASE_PATH.exists(),
            },
        )

    def _get_config(self):
        global APP_CONFIG
        APP_CONFIG = load_app_config()
        self._send_success(200, APP_CONFIG)

    def _get_statuses(self):
        status_repo = repo.StatusRepository(open_db)
        self._send_success(200, {"statuses": status_repo.list_with_counts()})

    def _get_models(self, qs: dict):
        q = qs.get("q", [""])[0].strip()
        limit = int(qs.get("limit", ["50"])[0])
        offset = int(qs.get("offset", ["0"])[0])
        model_repo = repo.ModelRepository(open_db)
        rows, total = model_repo.search(q, limit, offset)
        self._send_collection(rows, limit=limit, offset=offset, total=total)

    def _get_model(self, model_id: int):
        model_repo = repo.ModelRepository(open_db)
        result = model_repo.get_by_id(model_id)
        if result is None:
            self._send_error(404, "NOT_FOUND", "Model not found.")
            return
        self._send_success(200, result)

    def _get_studios(self, qs: dict):
        q = qs.get("q", [""])[0].strip()
        limit = int(qs.get("limit", ["50"])[0])
        offset = int(qs.get("offset", ["0"])[0])
        studio_repo = repo.StudioRepository(open_db)
        rows, total = studio_repo.search(q, limit, offset)
        self._send_collection(rows, limit=limit, offset=offset, total=total)

    def _get_studio(self, studio_id: int):
        studio_repo = repo.StudioRepository(open_db)
        result = studio_repo.get_by_id(studio_id)
        if result is None:
            self._send_error(404, "NOT_FOUND", "Studio not found.")
            return
        self._send_success(200, result)

    def _get_albums(self, qs: dict):
        album_repo = repo.AlbumRepository(open_db)
        rows, total = album_repo.search(
            q=qs.get("q", [""])[0].strip(),
            studio_id=qs.get("studio_id", [""])[0].strip(),
            status_id=qs.get("status_id", [""])[0].strip(),
            model_id=qs.get("model_id", [""])[0].strip(),
            rating_min=qs.get("rating_min", [""])[0].strip(),
            rating_max=qs.get("rating_max", [""])[0].strip(),
            sort=qs.get("sort", ["updated_at"])[0].strip(),
            limit=int(qs.get("limit", ["50"])[0]),
            offset=int(qs.get("offset", ["0"])[0]),
        )
        self._send_collection(
            rows,
            limit=int(qs.get("limit", ["50"])[0]),
            offset=int(qs.get("offset", ["0"])[0]),
            total=total,
        )

    def _get_album(self, album_id: int):
        album_repo = repo.AlbumRepository(open_db)
        result = album_repo.get_by_id(album_id)
        if result is None:
            self._send_error(404, "NOT_FOUND", "Album not found.")
            return
        self._send_success(200, result)

    def _get_workspace_albums(self, qs: dict):
        wa_repo = repo.WorkspaceAlbumRepository(open_db)
        limit = int(qs.get("limit", ["50"])[0])
        offset = int(qs.get("offset", ["0"])[0])
        rows, total = wa_repo.search(
            status_id=qs.get("status_id", [""])[0].strip(),
            studio_name=qs.get("studio_name", [""])[0].strip(),
            primary_model=qs.get("primary_model", [""])[0].strip(),
            linked=qs.get("linked", [""])[0].strip().lower(),
            q=qs.get("q", [""])[0].strip(),
            limit=limit,
            offset=offset,
        )
        self._send_collection(rows, limit=limit, offset=offset, total=total)

    def _get_workspace_album(self, wa_id: int):
        wa_repo = repo.WorkspaceAlbumRepository(open_db)
        result = wa_repo.get_by_id(wa_id)
        if result is None:
            self._send_error(404, "NOT_FOUND", "Workspace album not found.")
            return
        self._send_success(200, {"album": result})

    def _get_backups(self):
        catalog = build_backup_catalog()
        items = [public_backup_item(x) for x in catalog]
        self._send_success(200, {"items": items, "retention_days": RETENTION_DAYS})

    def _operation_reader(self):
        principal = getattr(self, "_principal", None)
        if principal is None:
            self._send_error(404, "NOT_FOUND", "The requested resource was not found.")
            return None
        return svc.OperationReadService(repo.OperationRepository(open_db)), principal["role"]

    def _get_operations(self, qs: dict):
        reader = self._operation_reader()
        if reader is None:
            return
        service, role = reader
        limit = min(max(int(qs.get("limit", ["50"])[0]), 1), 100)
        self._send_success(200, {"items": service.list_recent(role, limit)})

    def _get_operation(self, operation_uuid: str):
        reader = self._operation_reader()
        if reader is None:
            return
        service, role = reader
        try:
            self._send_success(200, {"operation": service.get(operation_uuid, role)})
        except svc.ServiceNotFound as exc:
            self._send_error(404, "NOT_FOUND", str(exc))

    # ------------------------------------------------------------------
    # POST handlers
    # ------------------------------------------------------------------

    def _handle_api_post(self, path: str, body: dict) -> None:
        try:
            if path == "/api/statuses":
                self._post_status(body)
            elif path == "/api/models":
                self._post_model(body)
            elif path == "/api/studios":
                self._post_studio(body)
            elif path == "/api/albums":
                self._post_album(body)
            elif re.match(r"^/api/albums/\d+/models$", path):
                album_id = int(path.split("/")[3])
                self._post_album_model(album_id, body)
            elif re.match(r"^/api/albums/\d+/relations$", path):
                album_id = int(path.split("/")[3])
                self._post_album_relation(album_id, body)
            elif re.match(r"^/api/albums/\d+/photos$", path):
                album_id = int(path.split("/")[3])
                self._post_album_photo(album_id, body)
            elif path == "/api/workspace/albums/batch":
                self._post_workspace_batch(body)
            elif path == "/api/import/preview":
                self._post_import_preview(body)
            elif path == "/api/import/execute":
                self._post_import_execute(body)
            elif path == "/api/backup":
                self._post_backup(body)
            elif path == "/api/backup/cleanup":
                self._post_backup_cleanup()
            elif path == "/api/rollback":
                self._post_rollback(body)
            else:
                self._send_error(404, "NOT_FOUND", "The requested resource was not found.")
        except Exception:
            self._send_error(500, "INTERNAL_ERROR", "An unexpected server error occurred.")

    def _post_status(self, body: dict):
        name = body.get("name", "").strip()
        description = body.get("description", "")
        if not name:
            self._send_error(400, "REQUEST_MISSING_FIELD", "The 'name' field is required.")
            return
        status_repo = repo.StatusRepository(open_db)
        result = status_repo.create(name, description)
        self._send_success(201, result)

    def _post_model(self, body: dict):
        model_repo = repo.ModelRepository(open_db)
        result = model_repo.create(body)
        self._send_success(201, result)

    def _post_studio(self, body: dict):
        studio_repo = repo.StudioRepository(open_db)
        result = studio_repo.create(body)
        self._send_success(201, result)

    def _post_album(self, body: dict):
        album_repo = repo.AlbumRepository(open_db)
        album_service = svc.AlbumService(album_repo=album_repo, log_fn=append_log)
        models = body.get("models", [])
        relations = body.get("relations", [])
        album_id = album_service.create(body, models, relations)
        self._send_success(201, {"id": album_id})

    def _post_album_model(self, album_id: int, body: dict):
        am_repo = repo.AlbumModelRepository(open_db)
        new_id = am_repo.add(album_id, body)
        self._send_success(201, {"id": new_id})

    def _post_album_relation(self, album_id: int, body: dict):
        ar_repo = repo.AlbumRelationRepository(open_db)
        new_id = ar_repo.add(album_id, body)
        self._send_success(201, {"id": new_id})

    def _post_album_photo(self, album_id: int, body: dict):
        photo_repo = repo.PhotoRepository(open_db)
        new_id = photo_repo.add(album_id, body)
        self._send_success(201, {"id": new_id})

    def _post_workspace_batch(self, body: dict):
        ids = body.get("ids", [])
        changes = body.get("changes", {})
        if not ids:
            self._send_error(400, "REQUEST_MISSING_FIELD", "The 'ids' field is required.")
            return
        wa_repo = repo.WorkspaceAlbumRepository(open_db)
        workspace_service = svc.WorkspaceAlbumService(
            workspace_repo=wa_repo,
            snapshot_fn=create_db_snapshot,
            backup_log_fn=append_backup_log,
        )
        try:
            updated = workspace_service.batch_update(ids, changes)
        except ValueError as exc:
            self._send_error(400, "REQUEST_INVALID", str(exc))
            return
        self._send_success(200, {"updated": updated})

    def _post_import_preview(self, body: dict):
        items_in = body.get("items", [])
        global APP_CONFIG
        APP_CONFIG = load_app_config()
        archive_root = APP_CONFIG.get("archive_root", "")
        default_studio = APP_CONFIG.get("default_import_studio", "")

        import_repo = repo.ImportRepository(open_db)
        import_service = svc.ImportService(
            import_repo=import_repo,
            snapshot_fn=create_db_snapshot,
            backup_log_fn=append_backup_log,
            change_log_fn=append_log,
            operation_service=svc.OperationService(repo.OperationRepository(open_db)),
            initiator=svc.OP_INITIATOR_WEB_UI,
        )
        preview = import_service.preview(items_in, archive_root, default_studio)
        self._send_success(200, {"preview": preview})

    def _post_import_execute(self, body: dict):
        items_in = body.get("items", [])
        if not items_in:
            self._send_error(400, "REQUEST_MISSING_FIELD", "The 'items' field is required.")
            return

        global APP_CONFIG
        APP_CONFIG = load_app_config()
        archive_root = APP_CONFIG.get("archive_root", "")
        default_studio = APP_CONFIG.get("default_import_studio", "")

        import_repo = repo.ImportRepository(open_db)
        import_service = svc.ImportService(
            import_repo=import_repo,
            snapshot_fn=create_db_snapshot,
            backup_log_fn=append_backup_log,
            change_log_fn=append_log,
            operation_service=svc.OperationService(repo.OperationRepository(open_db)),
            initiator=svc.OP_INITIATOR_WEB_UI,
        )
        result = import_service.execute(items_in, archive_root, default_studio)
        self._send_success(200, result)

    def _post_backup(self, body: dict):
        reason = body.get("reason", "manual")
        tag = body.get("tag", "")
        backup_service = svc.BackupService(
            snapshot_fn=create_db_snapshot,
            restore_fn=restore_database_from_snapshot,
            backup_log_fn=append_backup_log,
            rollback_log_fn=append_rollback_log,
            catalog_fn=build_backup_catalog,
            last_change_fn=get_last_success_change_entry,
            public_item_fn=public_backup_item,
            parse_tag_fn=parse_tag_from_name,
            cleanup_fn=cleanup_expired_snapshots,
        )
        try:
            result = backup_service.create(reason, tag)
            self._send_success(200, result)
        except Exception as ex:
            backup_service.create_failed(reason, tag, ex)
            self._send_error(500, "INTERNAL_ERROR", "The backup operation failed.")

    def _post_backup_cleanup(self):
        result = cleanup_expired_snapshots(RETENTION_DAYS)
        self._send_success(200, result)
    def _post_rollback(self, body: dict):
        mode = body.get("mode", "")
        if not mode:
            self._send_error(400, "REQUEST_INVALID", "The rollback mode is not recognised.")
            return
        backup_service = svc.BackupService(
            snapshot_fn=create_db_snapshot,
            restore_fn=restore_database_from_snapshot,
            backup_log_fn=append_backup_log,
            rollback_log_fn=append_rollback_log,
            catalog_fn=build_backup_catalog,
            last_change_fn=get_last_success_change_entry,
            public_item_fn=public_backup_item,
            parse_tag_fn=parse_tag_from_name,
        )
        try:
            result = backup_service.rollback(mode, body)
        except ValueError as exc:
            self._send_error(400, "REQUEST_INVALID", str(exc))
            return
        except svc.ServiceNotFound as exc:
            self._send_error(404, "NOT_FOUND", str(exc))
            return
        except Exception:
            self._send_error(500, "INTERNAL_ERROR", "The restore operation failed.")
            return
        self._send_success(200, result)

    # ------------------------------------------------------------------
    # PUT handlers
    # ------------------------------------------------------------------

    def _handle_api_put(self, path: str, body: dict) -> None:
        try:
            if re.match(r"^/api/statuses/\d+$", path):
                status_id = int(path.split("/")[-1])
                self._put_status(status_id, body)
            elif re.match(r"^/api/models/\d+$", path):
                model_id = int(path.split("/")[-1])
                self._put_model(model_id, body)
            elif re.match(r"^/api/studios/\d+$", path):
                studio_id = int(path.split("/")[-1])
                self._put_studio(studio_id, body)
            elif re.match(r"^/api/albums/\d+$", path):
                album_id = int(path.split("/")[-1])
                self._put_album(album_id, body)
            elif re.match(r"^/api/albums/\d+/models/\d+$", path):
                parts = path.split("/")
                album_id = int(parts[3])
                am_id = int(parts[5])
                self._put_album_model(album_id, am_id, body)
            elif re.match(r"^/api/albums/\d+/relations/\d+$", path):
                parts = path.split("/")
                album_id = int(parts[3])
                relation_id = int(parts[5])
                self._put_album_relation(album_id, relation_id, body)
            elif re.match(r"^/api/photos/\d+$", path):
                photo_id = int(path.split("/")[-1])
                self._put_photo(photo_id, body)
            elif re.match(r"^/api/workspace/albums/\d+$", path):
                wa_id = int(path.split("/")[-1])
                self._put_workspace_album(wa_id, body)
            else:
                self._send_error(404, "NOT_FOUND", "The requested resource was not found.")
        except Exception:
            self._send_error(500, "INTERNAL_ERROR", "An unexpected server error occurred.")

    def _put_status(self, status_id: int, body: dict):
        status_repo = repo.StatusRepository(open_db)
        result = status_repo.update(status_id, body.get("name"), body.get("description"))
        if result is None:
            self._send_error(404, "NOT_FOUND", "Status not found.")
            return
        self._send_success(200, {"status": result})

    def _put_model(self, model_id: int, body: dict):
        model_repo = repo.ModelRepository(open_db)
        model_service = svc.ModelService(model_repo=model_repo, log_fn=append_log)
        try:
            row = model_service.update_fields(model_id, body)
        except svc.ServiceNotFound:
            self._send_error(404, "NOT_FOUND", "Model not found.")
            return
        self._send_success(200, {"model": row})

    def _put_studio(self, studio_id: int, body: dict):
        studio_repo = repo.StudioRepository(open_db)
        now = utc_now_iso()
        result = studio_repo.update(studio_id, body, now)
        if result is None:
            self._send_error(404, "NOT_FOUND", "Studio not found.")
            return
        self._send_success(200, {"studio": result})

    def _put_album(self, album_id: int, body: dict):
        album_repo = repo.AlbumRepository(open_db)
        album_service = svc.AlbumService(album_repo=album_repo, log_fn=append_log)
        models = body.get("models", [])
        relations = body.get("relations", [])
        album_service.update(album_id, body, models, relations)
        self._send_success(200, None)

    def _put_album_model(self, album_id: int, am_id: int, body: dict):
        am_repo = repo.AlbumModelRepository(open_db)
        am_repo.update(album_id, am_id, body)
        self._send_success(200, None)

    def _put_album_relation(self, album_id: int, relation_id: int, body: dict):
        ar_repo = repo.AlbumRelationRepository(open_db)
        ar_repo.update(album_id, relation_id, body)
        self._send_success(200, None)

    def _put_photo(self, photo_id: int, body: dict):
        photo_repo = repo.PhotoRepository(open_db)
        photo_repo.update(photo_id, body)
        self._send_success(200, None)

    def _put_workspace_album(self, wa_id: int, body: dict):
        wa_repo = repo.WorkspaceAlbumRepository(open_db)
        workspace_service = svc.WorkspaceAlbumService(
            workspace_repo=wa_repo,
            snapshot_fn=create_db_snapshot,
            backup_log_fn=append_backup_log,
        )
        try:
            workspace_service.update(wa_id, body)
        except ValueError as exc:
            self._send_error(400, "REQUEST_INVALID", str(exc))
            return
        self._send_success(200, None)

    # ------------------------------------------------------------------
    # DELETE handlers
    # ------------------------------------------------------------------

    def _handle_api_delete(self, path: str) -> None:
        try:
            if re.match(r"^/api/statuses/\d+$", path):
                status_id = int(path.split("/")[-1])
                self._delete_status(status_id)
            elif re.match(r"^/api/models/\d+$", path):
                model_id = int(path.split("/")[-1])
                self._delete_model(model_id)
            elif re.match(r"^/api/studios/\d+$", path):
                studio_id = int(path.split("/")[-1])
                self._delete_studio(studio_id)
            elif re.match(r"^/api/albums/\d+$", path):
                album_id = int(path.split("/")[-1])
                self._delete_album(album_id)
            elif re.match(r"^/api/albums/\d+/models/\d+$", path):
                parts = path.split("/")
                album_id = int(parts[3])
                am_id = int(parts[5])
                self._delete_album_model(album_id, am_id)
            elif re.match(r"^/api/albums/\d+/relations/\d+$", path):
                parts = path.split("/")
                album_id = int(parts[3])
                relation_id = int(parts[5])
                self._delete_album_relation(album_id, relation_id)
            elif re.match(r"^/api/photos/\d+$", path):
                photo_id = int(path.split("/")[-1])
                self._delete_photo(photo_id)
            else:
                self._send_error(404, "NOT_FOUND", "The requested resource was not found.")
        except Exception:
            self._send_error(500, "INTERNAL_ERROR", "An unexpected server error occurred.")

    def _delete_status(self, status_id: int):
        status_repo = repo.StatusRepository(open_db)
        status_service = svc.StatusService(status_repo=status_repo)
        try:
            status_service.delete(status_id)
        except svc.ServiceConflict as exc:
            self._send_error(409, exc.code, str(exc), details=exc.details)
            return
        self._send_success(200, None)

    def _delete_model(self, model_id: int):
        model_repo = repo.ModelRepository(open_db)
        model_service = svc.ModelService(model_repo=model_repo)
        try:
            model_service.delete(model_id)
        except svc.ServiceConflict as exc:
            self._send_error(409, exc.code, str(exc), details=exc.details)
            return
        self._send_success(200, None)

    def _delete_studio(self, studio_id: int):
        studio_repo = repo.StudioRepository(open_db)
        studio_service = svc.StudioService(studio_repo=studio_repo)
        try:
            studio_service.delete(studio_id)
        except svc.ServiceConflict as exc:
            self._send_error(409, exc.code, str(exc), details=exc.details)
            return
        self._send_success(200, None)

    def _delete_album(self, album_id: int):
        album_repo = repo.AlbumRepository(open_db)
        album_service = svc.AlbumService(album_repo=album_repo, log_fn=append_log)
        album_service.delete(album_id)
        self._send_success(200, None)

    def _delete_album_model(self, album_id: int, am_id: int):
        am_repo = repo.AlbumModelRepository(open_db)
        am_repo.delete(album_id, am_id)
        self._send_success(200, None)

    def _delete_album_relation(self, album_id: int, relation_id: int):
        ar_repo = repo.AlbumRelationRepository(open_db)
        ar_repo.delete(album_id, relation_id)
        self._send_success(200, None)

    def _delete_photo(self, photo_id: int):
        photo_repo = repo.PhotoRepository(open_db)
        photo_repo.delete(photo_id)
        self._send_success(200, None)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    if "--check" in sys.argv:
        print(f"Config: {CONFIG_PATH}")
        print(f"Database path: {DATABASE_PATH}")
        print(f"Static dir: {STATIC_DIR}")
        if DATABASE_PATH.exists():
            print("OK: Database file found")
        else:
            print("NOTE: Database file not present at configured path (expected on NAS mount)")
        sys.exit(0)

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")
    if not STATIC_DIR.exists():
        raise FileNotFoundError(f"Static directory not found: {STATIC_DIR}")

    host = "127.0.0.1"
    port = int(os.environ.get("CURATOR_PORT", "8788"))

    backup_thread = threading.Thread(
        target=run_daily_backup, name="daily-backup", daemon=True
    )
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
    print(f"Curator Web UI running at http://{host}:{port}")
    print(f"Database: {DATABASE_PATH}")
    print(f"Backups: {BACKUP_DIR}")

    try:
        server.serve_forever()
    finally:
        STOP_EVENT.set()
        backup_thread.join(timeout=3)


if __name__ == "__main__":
    main()
