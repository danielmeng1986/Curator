#!/usr/bin/env python3
import json
import hashlib
import os
import re
import shutil
import sqlite3
import socket
import secrets
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:  # Package execution: python3 -m apps.backend
    from . import api_contract
    from . import repositories as repo
    from . import services as svc
except ImportError:  # Focused test discovery still loads sibling modules directly.
    import api_contract
    import repositories as repo
    import services as svc

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[1]
RUNTIME_DIR = Path(os.environ.get("CURATOR_RUNTIME_DIR", REPO_ROOT / "var"))
STATIC_DIR = Path(os.environ.get("CURATOR_STATIC_DIR", REPO_ROOT / "apps" / "web" / "static"))
DATABASE_PATH = Path(os.environ.get("CURATOR_DATABASE_PATH", RUNTIME_DIR / "data" / "Curator.db"))
CONFIG_PATH = Path(os.environ.get("CURATOR_CONFIG_PATH", REPO_ROOT / "config" / "backend.json"))
LOG_DIR = Path(os.environ.get("CURATOR_LOG_DIR", RUNTIME_DIR / "logs"))
BACKUP_DIR = Path(os.environ.get("CURATOR_BACKUP_DIR", RUNTIME_DIR / "backups"))
LOG_PATH = LOG_DIR / "changes.log"
BACKUP_LOG_PATH = LOG_DIR / "backup.log"
ROLLBACK_LOG_PATH = LOG_DIR / "rollback.log"

# ---------------------------------------------------------------------------
# Default config
# ---------------------------------------------------------------------------
DEFAULT_APP_CONFIG = {
    "import_source_root": "",
    "archive_root": "",
    "default_import_studio": "",
    "quarantine_root": "",
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
            for key in ("import_source_root", "archive_root", "default_import_studio", "quarantine_root"):
                if key in on_disk:
                    cfg[key] = on_disk[key]
        except Exception:
            pass
    return cfg


APP_CONFIG = load_app_config()
AUTH_REGISTRATION_SECRET = os.environ.get("CURATOR_REGISTRATION_SECRET", "")
ALBUM_BATCH_PREVIEW_SECRET = secrets.token_bytes(32)
IMPORT_PREVIEW_SECRET = secrets.token_bytes(32)
QUARANTINE_PREVIEW_SECRET = secrets.token_bytes(32)
SNAPSHOT_CLEANUP_PREVIEW_SECRET = secrets.token_bytes(32)
WORK_DISPATCH_PREVIEW_SECRET = secrets.token_bytes(32)
RESTORE_EXECUTION_LOCK = threading.Lock()

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
            "protection_state": "protected" if protected else "unprotected",
            "retention_class": meta.get("retention_class", "ordinary"),
            "verification_state": meta.get("verification_state", "not_verified"),
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


def verify_snapshot_item(item: dict) -> dict:
    """Run SQLite integrity verification for a catalog-resolved snapshot."""
    path = Path(item["path"])
    state, detail = "failed", "Recovery point could not be verified."
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            rows = [row[0] for row in conn.execute("PRAGMA integrity_check")]
        if rows == ["ok"]:
            state, detail = "verified", "SQLite integrity check passed."
    except sqlite3.Error:
        pass
    append_backup_log({
        "timestamp": utc_now_iso(), "event": "verification", "snapshot": str(path),
        "reason": item.get("reason", ""), "tag": item.get("tag", ""),
        "protected": item.get("protected", False),
        "retention_class": item.get("retention_class", "ordinary"),
        "verification_state": state, "ok": state == "verified",
    })
    return {"verification_state": state, "verified_at": utc_now_iso(), "detail": detail}


def delete_snapshot_item(item: dict) -> None:
    """Delete only a catalog-resolved file beneath the configured backup root."""
    path = Path(item["path"]).resolve()
    if path.parent != BACKUP_DIR.resolve() or path.suffix != ".db":
        raise ValueError("Recovery point is outside the managed backup root.")
    path.unlink()
    append_backup_log({"timestamp": utc_now_iso(), "event": "cleanup",
                       "filename": path.name, "ok": True})


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


def database_restore_state(verify: bool = False):
    """Return a bounded database-state fingerprint or post-Restore integrity result."""
    if verify:
        try:
            with sqlite3.connect(str(DATABASE_PATH)) as conn:
                rows = [row[0] for row in conn.execute("PRAGMA integrity_check")]
            return {"verified": rows == ["ok"]}
        except sqlite3.Error:
            return {"verified": False}
    # Authentication updates token ``last_used_at`` before every protected
    # request.  Bind Restore previews to business state, not that expected
    # transport-level write or the single-use claim tables themselves.
    excluded = {
        "auth_bootstrap_code", "auth_registration", "auth_token", "auth_token_renewal",
        "restore_preview_claim", "snapshot_cleanup_preview_claim", "import_preview_claim",
        "quarantine_preview_claim", "sqlite_sequence",
    }
    digest = hashlib.sha256()
    with sqlite3.connect(str(DATABASE_PATH)) as conn:
        tables = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) if row[0] not in excluded and not row[0].startswith("sqlite_")]
        for table in tables:
            quoted = table.replace('"', '""')
            digest.update(table.encode())
            for row in conn.execute(f'SELECT * FROM "{quoted}" ORDER BY rowid'):
                digest.update(repr(tuple(row)).encode())
    return digest.hexdigest()


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

    def _send_evidence_content(self, descriptor) -> None:
        try:
            self.send_response(200)
            self.send_header("Content-Type", descriptor["mime_type"])
            self.send_header("Content-Length", str(descriptor["size_bytes"]))
            self.send_header("Cache-Control", "private, no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("ETag", f'"sha256-{descriptor["sha256"]}"')
            self.send_header("Content-Disposition", f'inline; filename="{descriptor["filename"].replace(chr(34), "")}"')
            self.end_headers()
            with descriptor["path"].open("rb") as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b""): self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, socket.error): return

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
        if path in {"/api/auth/me", "/api/auth/renewals"}:
            return "read"
        if path in {"/api/backup", "/api/backup/cleanup", "/api/rollback"} or path.startswith("/api/backups") or path.startswith("/api/auth/") or path.startswith("/api/admin/") or path.startswith("/api/ai-workspaces") or path.startswith("/api/work-dispatch"):
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

        if path == "/api/auth/bootstrap/status":
            self._handle_auth_bootstrap_status()
            return
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
        """Loopback-only registration request and first bootstrap boundary."""
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
            elif path == "/api/auth/bootstrap/complete":
                issued = auth.complete_bootstrap_with_code(
                    code=body.get("code", ""),
                    device_name=body.get("device_name", ""),
                    device_identity=body.get("device_identity", ""),
                )
                self._send_success(200, issued)
            elif re.match(r"^/api/auth/registrations/[^/]+/approve$", path):
                self._send_error(
                    403, "AUTHORIZATION_ADMIN_REQUIRED",
                    "Registration approval requires an authenticated Admin Token.",
                )
            else:
                self._send_error(404, "NOT_FOUND", "The requested resource was not found.")
        except svc.AuthenticationFailure as exc:
            self._send_error(401, exc.code, str(exc))
        except svc.AuthorizationFailure as exc:
            self._send_error(403, exc.code, str(exc))
        except (svc.ServiceConflict, ValueError) as exc:
            self._send_error(409, getattr(exc, "code", "BUSINESS_CONFLICT"), str(exc))

    def _handle_auth_bootstrap_status(self) -> None:
        if self.client_address[0] not in {"127.0.0.1", "::1"}:
            self._send_error(403, "AUTHORIZATION_LOOPBACK_REQUIRED", "Administrator bootstrap is available only on loopback.")
            return
        auth = svc.AuthenticationService(repo.AuthRepository(open_db))
        self._send_success(200, {"bootstrap": auth.bootstrap_status()})

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
            elif path == "/api/workspace/albums" or re.match(r"^/api/workspace/albums/\d+$", path):
                self._send_error(410, "HISTORICAL_WORKSPACE_RETIRED", "The historical Workspace Album API is retired.")
            elif path == "/api/admin/history/workspace-albums":
                self._get_historical_workspace_albums(qs)
            elif re.match(r"^/api/admin/history/workspace-albums/\d+$", path):
                self._get_historical_workspace_album(int(path.split("/")[-1]))
            elif path == "/api/ai-workspaces":
                self._get_ai_workspaces(qs)
            elif re.match(r"^/api/ai-workspaces/[^/]+$", path):
                self._get_ai_workspace(path.split("/")[-1])
            elif re.match(r"^/api/ai-workspaces/[^/]+/items$", path):
                if not self._require_admin_principal(): return
                workspace_uuid = path.split("/")[3]
                self._send_success(200, {"items": self._ai_work_item_service().list(workspace_uuid)})
            elif re.match(r"^/api/ai-work-items/[^/]+$", path):
                if not self._require_admin_principal(): return
                self._send_success(200, {"item": self._ai_work_item_service().get(path.split("/")[-1], include_attempts=True)})
            elif re.match(r"^/api/ai-work-items/[^/]+/evidence-manifest$", path):
                if not self._require_admin_principal(): return
                self._send_success(200, {"manifest":self._ai_photo_evidence_service().revalidate(path.split("/")[3])})
            elif re.match(r"^/api/ai-work-items/[^/]+/results$", path):
                if not self._require_admin_principal(): return
                self._send_success(200, {"results":self._ai_result_service().get(path.split("/")[3])})
            elif path == "/api/ai-reviews":
                if not self._require_admin_principal(): return
                state=qs.get("state",[None])[0]; workspace_uuid=qs.get("workspace_uuid",[None])[0]
                result=self._ai_review_service().queue(state,workspace_uuid,
                    int(qs.get("limit",["50"])[0]),int(qs.get("offset",["0"])[0]))
                self._send_collection(result["items"],limit=result["limit"],offset=result["offset"],total=result["total"])
            elif re.match(r"^/api/ai-work-items/[^/]+/review$", path):
                if not self._require_admin_principal(): return
                self._send_success(200,{"review":self._ai_review_service().detail(path.split("/")[3])})
            elif re.match(r"^/api/ai-evidence/[^/]+$", path):
                evidence_uuid = path.split("/")[3]
                self._send_success(200,{"evidence":self._ai_photo_evidence_service().metadata(
                    evidence_uuid,self._principal["role"],self._principal.get("token_uuid"))})
            elif re.match(r"^/api/ai-evidence/[^/]+/content$", path):
                evidence_uuid = path.split("/")[3]
                self._send_evidence_content(self._ai_photo_evidence_service().content_descriptor(
                    evidence_uuid,self._principal["role"],self._principal.get("token_uuid")))
            elif path == "/api/ai-model-configurations":
                self._get_ai_model_configurations()
            elif re.match(r"^/api/ai-model-configurations/[^/]+$", path):
                self._get_ai_model_configuration(path.split("/")[-1])
            elif path == "/api/work-dispatch/candidates":
                self._get_work_dispatch_candidates(qs)
            elif re.match(r"^/api/work-dispatch/batches/[^/]+$", path):
                if not self._require_admin_principal(): return
                self._send_success(200, self._work_dispatch_service().batch_detail(path.split("/")[-1]))
            elif path == "/api/backups":
                self._get_backups()
            elif path == "/api/operations":
                self._get_operations(qs)
            elif re.match(r"^/api/operations/[^/]+$", path):
                self._get_operation(path.split("/")[-1])
            elif path == "/api/issues":
                self._get_issues(qs)
            elif re.match(r"^/api/issues/[^/]+$", path):
                self._get_issue(path.split("/")[-1])
            elif path == "/api/repairs":
                self._get_repairs(qs)
            elif re.match(r"^/api/repairs/[^/]+$", path):
                self._get_repair(path.split("/")[-1])
            elif path == "/api/repair-suppressions":
                self._get_repair_suppressions()
            elif path == "/api/quarantine-items":
                self._get_quarantine_items()
            elif re.match(r"^/api/quarantine-items/[^/]+$", path):
                self._get_quarantine_item(path.split("/")[-1])
            elif path == "/api/auth/me":
                self._send_success(200, {"principal": self._principal})
            elif path == "/api/auth/admin/state":
                self._get_auth_admin_state()
            else:
                self._send_error(404, "NOT_FOUND", "The requested resource was not found.")
        except ValueError as exc:
            self._send_error(400, "REQUEST_INVALID", str(exc))
        except svc.ServiceNotFound as exc:
            self._send_error(404, "NOT_FOUND", str(exc))
        except svc.ServiceConflict as exc:
            self._send_error(409, exc.code, str(exc), details=exc.details)
        except svc.AuthorizationFailure as exc:
            self._send_error(403, exc.code, str(exc))
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
        date_filters = {
            name: qs.get(name, [""])[0].strip()
            for name in (
                "capture_date_from", "capture_date_to",
                "publish_date_from", "publish_date_to",
            )
        }
        for name, value in date_filters.items():
            if value:
                try:
                    datetime.strptime(value, "%Y-%m-%d")
                except ValueError as exc:
                    raise ValueError(f"{name} must use YYYY-MM-DD format.") from exc
        for prefix in ("capture_date", "publish_date"):
            if date_filters[f"{prefix}_from"] and date_filters[f"{prefix}_to"] \
                    and date_filters[f"{prefix}_from"] > date_filters[f"{prefix}_to"]:
                raise ValueError(f"{prefix}_from must not be later than {prefix}_to.")
        album_repo = repo.AlbumRepository(open_db)
        rows, total = album_repo.search(
            q=qs.get("q", [""])[0].strip(),
            studio_id=qs.get("studio_id", [""])[0].strip(),
            status_id=qs.get("status_id", [""])[0].strip(),
            model_id=qs.get("model_id", [""])[0].strip(),
            rating_min=qs.get("rating_min", [""])[0].strip(),
            rating_max=qs.get("rating_max", [""])[0].strip(),
            **date_filters,
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

    def _get_historical_workspace_albums(self, qs: dict):
        if not self._require_admin_principal(): return
        limit, offset = int(qs.get("limit", ["50"])[0]), int(qs.get("offset", ["0"])[0])
        if not 1 <= limit <= 100 or offset < 0: raise ValueError("History pagination is invalid.")
        rows, total = repo.WorkspaceAlbumRepository(open_db).search_historical(limit, offset)
        self._send_collection(rows, limit=limit, offset=offset, total=total)

    def _get_historical_workspace_album(self, wa_id: int):
        if not self._require_admin_principal(): return
        item = repo.WorkspaceAlbumRepository(open_db).get_historical(wa_id)
        if item is None: raise svc.ServiceNotFound("Historical Workspace Album not found.")
        self._send_success(200, {"item": item})

    def _ai_workspace_service(self):
        return svc.AIWorkspaceService(
            repo.AIWorkspaceRepository(open_db),
            svc.OperationService(repo.OperationRepository(open_db)),
        )

    def _get_ai_workspaces(self, qs: dict):
        if not self._require_admin_principal(): return
        self._send_success(200, {"items": self._ai_workspace_service().list(qs.get("lifecycle_state", [None])[0])})

    def _get_ai_workspace(self, workspace_uuid: str):
        if not self._require_admin_principal(): return
        self._send_success(200, {"workspace": self._ai_workspace_service().get(workspace_uuid)})

    def _ai_model_configuration_service(self):
        return svc.AIModelConfigurationService(
            repo.AIModelConfigurationRepository(open_db),
            svc.OperationService(repo.OperationRepository(open_db)),
        )

    def _ai_work_item_service(self):
        return svc.AIWorkItemService(
            repo.AIWorkItemRepository(open_db), repo.AIWorkspaceRepository(open_db),
            repo.AlbumRepository(open_db), self._ai_model_configuration_service(),
            svc.OperationService(repo.OperationRepository(open_db)),
        )

    def _ai_photo_evidence_service(self):
        return svc.AIPhotoEvidenceManifestService(
            repo.AIPhotoEvidenceRepository(open_db), repo.AIWorkItemRepository(open_db),
            repo.AlbumRepository(open_db), APP_CONFIG.get("archive_root", ""),
            repo.IssueRepository(open_db),
        )

    def _ai_result_service(self):
        return svc.AIResultSubmissionService(
            repo.AIResultRepository(open_db), self._ai_photo_evidence_service()
        )

    def _ai_review_service(self):
        return svc.AIReviewService(repo.AIReviewRepository(open_db))

    def _work_dispatch_service(self):
        return svc.WorkDispatchService(
            repo.AlbumAIWorkDispatchRepository(open_db), repo.AlbumRepository(open_db),
            workspace_repo=repo.AIWorkspaceRepository(open_db),
            configuration_service=self._ai_model_configuration_service(),
            preview_secret=WORK_DISPATCH_PREVIEW_SECRET,
        )

    def _get_work_dispatch_candidates(self, qs):
        if not self._require_admin_principal(): return
        worker_kind = qs.get("worker_kind", [""])[0].strip()
        filters = {key: qs.get(key, [""])[0].strip() for key in svc.WorkDispatchService.FILTER_FIELDS
                   if qs.get(key, [""])[0].strip()}
        result = self._work_dispatch_service().candidates(worker_kind, filters,
            availability=qs.get("availability", ["available"])[0].strip(),
            limit=int(qs.get("limit", ["50"])[0]), offset=int(qs.get("offset", ["0"])[0]))
        self._send_collection(result["items"], limit=result["limit"], offset=result["offset"],
            total=result["total"], filters=[{"field":key,"operator":"eq","value":value}
                for key,value in {**result["filters"],"availability":result["availability"],
                    "worker_kind":result["worker_kind"]}.items()],
            sort=[{"field":result["filters"].get("sort","updated_at"),"direction":"desc"}])

    def _require_worker_principal(self):
        if self._principal["role"] != "writer":
            self._send_error(403, "AUTHORIZATION_WRITER_WORKER_REQUIRED", "A Writer AI Worker Token is required.")
            return False
        return True

    def _get_ai_model_configurations(self):
        is_admin = self._principal["role"] == "admin"
        self._send_success(200, {"items": self._ai_model_configuration_service().list(admin=is_admin)})

    def _get_ai_model_configuration(self, config_uuid):
        is_admin = self._principal["role"] == "admin"
        self._send_success(200, {"configuration": self._ai_model_configuration_service().get(config_uuid, admin=is_admin)})

    def _get_backups(self):
        if not self._require_admin_principal(): return
        service = self._backup_admin_service()
        self._send_success(200, {"items": service.recovery_points(),
                                 "retention_days": RETENTION_DAYS})

    def _backup_admin_service(self):
        return svc.BackupService(
            snapshot_fn=create_db_snapshot, restore_fn=restore_database_from_snapshot,
            backup_log_fn=append_backup_log, rollback_log_fn=append_rollback_log,
            catalog_fn=build_backup_catalog, last_change_fn=get_last_success_change_entry,
            public_item_fn=public_backup_item, parse_tag_fn=parse_tag_from_name,
            cleanup_fn=cleanup_expired_snapshots, preview_secret=SNAPSHOT_CLEANUP_PREVIEW_SECRET,
            cleanup_repo=repo.SnapshotCleanupRepository(open_db),
            delete_snapshot_fn=delete_snapshot_item, verify_snapshot_fn=verify_snapshot_item,
            operation_service=svc.OperationService(repo.OperationRepository(open_db)),
            restore_preview_repo=repo.RestorePreviewRepository(open_db),
            database_state_fn=database_restore_state,
        )

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
        try:
            limit = int(qs.get("limit", ["50"])[0])
        except (TypeError, ValueError) as exc:
            raise ValueError("Operation limit must be an integer from 1 to 100.") from exc
        if not 1 <= limit <= 100:
            raise ValueError("Operation limit must be an integer from 1 to 100.")
        status = qs.get("status", [None])[0] or None
        if status is not None and status not in {
            svc.OP_STATUS_PENDING, svc.OP_STATUS_RUNNING, svc.OP_STATUS_SUCCEEDED,
            svc.OP_STATUS_FAILED, svc.OP_STATUS_NEEDS_REPAIR, svc.OP_STATUS_CANCELLED,
        }:
            raise ValueError("Invalid Operation status filter.")
        operation_type = qs.get("operation_type", [None])[0] or None
        if operation_type is not None and (len(operation_type) > 100 or not re.fullmatch(r"[A-Za-z0-9_.-]+", operation_type)):
            raise ValueError("Invalid Operation type filter.")

        def normalized_date(name: str) -> str | None:
            value = qs.get(name, [None])[0] or None
            if value is None:
                return None
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc).isoformat()
            except ValueError as exc:
                raise ValueError(f"Invalid ISO-8601 {name} filter.") from exc

        started_from = normalized_date("started_from")
        started_to = normalized_date("started_to")
        if started_from and started_to and started_from > started_to:
            raise ValueError("Operation started_from must not be after started_to.")
        cursor = qs.get("cursor", [None])[0] or None
        result = service.query(
            role, limit=limit, cursor=cursor, status=status,
            operation_type=operation_type, started_from=started_from, started_to=started_to,
        )
        filters = [{"field": key, "operator": "eq" if key in {"status", "operation_type"} else "gte" if key == "started_from" else "lte", "value": value}
                   for key, value in result["filters"].items()]
        meta = api_contract.build_collection_meta(
            cursor=cursor, limit=limit, next_cursor=result["next_cursor"],
            has_more=result["has_more"], total=result["total"], filters=filters,
            sort=[{"field": "started_at", "direction": "desc"}],
        )
        self._send_json(200, api_contract.success_response(
            result["items"], request_id=self._request_id, meta_extras=meta,
        ))

    def _get_operation(self, operation_uuid: str):
        reader = self._operation_reader()
        if reader is None:
            return
        service, role = reader
        try:
            self._send_success(200, {"operation": service.get(operation_uuid, role)})
        except svc.ServiceNotFound as exc:
            self._send_error(404, "NOT_FOUND", str(exc))

    def _issue_repair_reader(self):
        role = self._principal["role"]
        return svc.IssueRepairReviewService(
            repo.IssueRepository(open_db), repo.RepairRepository(open_db),
            svc.OperationService(repo.OperationRepository(open_db)),
        ), role

    def _get_issues(self, qs: dict):
        service, role = self._issue_repair_reader()
        state = qs.get("state", [None])[0] or None
        if state and state not in {svc.ISSUE_STATE_OPEN, svc.ISSUE_STATE_IN_PROGRESS, svc.ISSUE_STATE_RESOLVED, svc.ISSUE_STATE_ARCHIVED}:
            raise ValueError("Invalid Issue state filter.")
        self._send_success(200, {"items": service.list_issues(role, state=state, owner=qs.get("owner", [None])[0] or None)})

    def _get_issue(self, issue_uuid: str):
        service, role = self._issue_repair_reader()
        self._send_success(200, {"issue": service.get_issue(issue_uuid, role)})

    def _get_repairs(self, qs: dict):
        service, role = self._issue_repair_reader()
        state = qs.get("state", [None])[0] or None
        category = qs.get("category", [None])[0] or None
        if state and state not in svc._REPAIR_TRANSITIONS: raise ValueError("Invalid Repair state filter.")
        if category and category not in {svc.REPAIR_CATEGORY_AUTOMATIC, svc.REPAIR_CATEGORY_ASSISTED, svc.REPAIR_CATEGORY_MANUAL_CONFLICT}: raise ValueError("Invalid Repair category filter.")
        self._send_success(200, {"items": service.list_repairs(role, state=state, category=category)})

    def _get_repair(self, repair_uuid: str):
        service, role = self._issue_repair_reader()
        self._send_success(200, {"repair": service.get_repair(repair_uuid, role)})

    def _get_repair_suppressions(self):
        if self._principal["role"] != "admin":
            self._send_error(403, "AUTHORIZATION_ADMIN_REQUIRED", "An Admin Token is required.")
            return
        self._send_success(200, {"items": repo.RepairSuppressionRepository(open_db).list_records()})

    def _require_admin_principal(self) -> bool:
        if self._principal["role"] != "admin":
            self._send_error(403, "AUTHORIZATION_ADMIN_REQUIRED", "An Admin Token is required.")
            return False
        return True

    def _get_quarantine_items(self):
        if not self._require_admin_principal(): return
        self._send_success(200, {"items": repo.QuarantineRepository(open_db).list()})

    def _get_quarantine_item(self, item_uuid):
        if not self._require_admin_principal(): return
        item = repo.QuarantineRepository(open_db).get(item_uuid)
        if not item: raise svc.ServiceNotFound("Quarantine item not found.")
        self._send_success(200, {"item": item})

    def _auth_admin_service(self):
        return svc.AuthenticationService(
            repo.AuthRepository(open_db),
            operation_service=svc.OperationService(repo.OperationRepository(open_db)),
        )

    def _get_auth_admin_state(self):
        if not self._require_admin_principal(): return
        self._send_success(200, self._auth_admin_service().admin_read_model())

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
            elif path == "/api/albums/batch/preview":
                self._post_album_batch_preview(body)
            elif path == "/api/albums/batch/execute":
                self._post_album_batch_execute(body)
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
                self._send_error(410, "HISTORICAL_WORKSPACE_RETIRED", "The historical Workspace Album API is retired.")
            elif path == "/api/import/preview":
                self._post_import_preview(body)
            elif path == "/api/import/execute":
                self._post_import_execute(body)
            elif path == "/api/ai-workspaces":
                if not self._require_admin_principal(): return
                created = self._ai_workspace_service().create(body.get("title", ""), self._principal.get("token_uuid"))
                self._send_success(201, {"workspace": created})
            elif path == "/api/work-dispatch/preview":
                if not self._require_admin_principal(): return
                preview = self._work_dispatch_service().preview(
                    body.get("worker_kind", ""), body.get("workspace_uuid", ""),
                    body.get("configuration_uuids"), album_ids=body.get("album_ids"),
                    filters=body.get("filters"), first_n=body.get("first_n"),
                    created_by_token_uuid=self._principal.get("token_uuid"))
                self._send_success(200, {"preview":preview})
            elif path == "/api/work-dispatch/execute":
                if not self._require_admin_principal(): return
                token = body.get("preview_token", "")
                if not token: raise ValueError("preview_token is required.")
                self._send_success(200, {"result":self._work_dispatch_service().execute(
                    token, self._principal.get("token_uuid"))})
            elif re.match(r"^/api/ai-workspaces/[^/]+/items$", path):
                if not self._require_admin_principal(): return
                self._send_error(409, "WORK_DISPATCH_REQUIRED",
                    "Create AI Work Items through Work Dispatch preview and execution.")
            elif path == "/api/ai-work-items/claim":
                if not self._require_worker_principal(): return
                item = self._ai_work_item_service().claim_next(self._principal["token_uuid"], body.get("lease_seconds", 300))
                self._send_success(200, {"item": item})
            elif re.match(r"^/api/ai-work-items/[^/]+/(heartbeat|fail)$", path):
                if not self._require_worker_principal(): return
                parts = path.split("/"); service = self._ai_work_item_service()
                if parts[4] == "heartbeat":
                    item = service.heartbeat(parts[3], self._principal["token_uuid"], body.get("lease_seconds", 300))
                else:
                    item = service.fail(parts[3], self._principal["token_uuid"], body.get("error_code", ""), body.get("message", ""))
                self._send_success(200, {"item": item})
            elif re.match(r"^/api/ai-work-items/[^/]+/results/(vision|writer)$", path):
                if not self._require_worker_principal(): return
                parts = path.split("/"); stage = parts[5].title()
                result = self._ai_result_service().submit(
                    parts[3], self._principal["token_uuid"], stage,
                    body.get("schema_version"), body.get("payload"), body.get("runtime_metrics")
                )
                self._send_success(200, {"result": result})
            elif re.match(r"^/api/ai-work-items/[^/]+/review/start$", path):
                if not self._require_admin_principal(): return
                review=self._ai_review_service().start(path.split("/")[3],body.get("expected_version"),self._principal["token_uuid"])
                self._send_success(200,{"review":review})
            elif re.match(r"^/api/ai-work-items/[^/]+/review/decision$", path):
                if not self._require_admin_principal(): return
                review=self._ai_review_service().decide(path.split("/")[3],body.get("expected_version"),
                    body.get("action"),self._principal["token_uuid"],body)
                self._send_success(200,{"review":review})
            elif re.match(r"^/api/ai-work-items/[^/]+/(retry|cancel)$", path):
                if not self._require_admin_principal(): return
                parts = path.split("/"); expected = body.get("expected_version")
                if not isinstance(expected, int): raise ValueError("expected_version is required and must be an integer.")
                service = self._ai_work_item_service()
                item = service.retry(parts[3], expected) if parts[4] == "retry" else service.cancel(parts[3], expected)
                self._send_success(200, {"item": item})
            elif re.match(r"^/api/ai-work-items/[^/]+/evidence-manifest$", path):
                if not self._require_admin_principal(): return
                manifest = self._ai_photo_evidence_service().create(path.split("/")[3])
                self._send_success(201, {"manifest":manifest})
            elif path == "/api/ai-model-configurations":
                if not self._require_admin_principal(): return
                self._send_success(201, {"configuration": self._ai_model_configuration_service().create(body)})
            elif re.match(r"^/api/ai-model-configurations/[^/]+/(enable|disable)$", path):
                if not self._require_admin_principal(): return
                parts = path.split("/"); expected = body.get("expected_version")
                if not isinstance(expected, int): raise ValueError("expected_version is required and must be an integer.")
                updated = self._ai_model_configuration_service().set_enabled(parts[3], expected, parts[4] == "enable")
                self._send_success(200, {"configuration": updated})
            elif re.match(r"^/api/ai-workspaces/[^/]+/(close|archive)$", path):
                if not self._require_admin_principal(): return
                parts = path.split("/"); workspace_uuid, action = parts[3], parts[4]
                expected = body.get("expected_version")
                if not isinstance(expected, int): raise ValueError("expected_version is required and must be an integer.")
                service = self._ai_workspace_service()
                updated = service.close(workspace_uuid, expected) if action == "close" else service.archive(workspace_uuid, expected)
                self._send_success(200, {"workspace": updated})
            elif path == "/api/backup":
                self._post_backup(body)
            elif re.match(r"^/api/backups/[^/]+/verify$", path):
                self._post_backup_verify(path.split("/")[3])
            elif path == "/api/backups/cleanup/preview":
                self._send_success(200, {"preview": self._backup_admin_service().preview_cleanup()})
            elif path == "/api/backups/cleanup/execute":
                token = body.get("preview_token", "")
                if not token: raise ValueError("preview_token is required.")
                self._send_success(200, self._backup_admin_service().execute_cleanup(token))
            elif path == "/api/backups/restore/preview":
                identity = body.get("identity", "")
                if not identity: raise ValueError("identity is required.")
                self._send_success(200, {"preview": self._backup_admin_service().preview_restore(identity)})
            elif path == "/api/backups/restore/execute":
                token, confirmation = body.get("preview_token", ""), body.get("confirmation", "")
                if not token or not confirmation: raise ValueError("preview_token and confirmation are required.")
                if not RESTORE_EXECUTION_LOCK.acquire(blocking=False):
                    raise svc.ServiceConflict("RESTORE_IN_PROGRESS", "Another database Restore is in progress.")
                try:
                    self._send_success(200, self._backup_admin_service().execute_restore(token, confirmation))
                finally:
                    RESTORE_EXECUTION_LOCK.release()
            elif path == "/api/backup/cleanup":
                self._send_error(409, "SNAPSHOT_CLEANUP_PREVIEW_REQUIRED", "Create a cleanup preview before execution.")
            elif path == "/api/rollback":
                self._send_error(409, "RESTORE_PREVIEW_REQUIRED", "Create a protected Restore preview before execution.")
            elif re.match(r"^/api/auth/registrations/[^/]+/approve$", path):
                self._post_authenticated_registration_approval(path, body)
            elif path == "/api/auth/renewals":
                self._post_token_renewal(body)
            elif re.match(r"^/api/auth/admin/registrations/[^/]+/(approve|reject)$", path):
                self._post_auth_registration_decision(path, body)
            elif re.match(r"^/api/auth/admin/renewals/[^/]+/(approve|reject)$", path):
                self._post_auth_renewal_decision(path, body)
            elif re.match(r"^/api/auth/admin/tokens/[^/]+/revoke$", path):
                self._post_auth_token_revoke(path)
            elif re.match(r"^/api/issues/[^/]+/decisions$", path):
                self._post_issue_decision(path.split("/")[3], body)
            elif re.match(r"^/api/repairs/[^/]+/decisions$", path):
                self._post_repair_decision(path.split("/")[3], body)
            elif path == "/api/repair-suppressions":
                self._post_repair_suppression(body)
            elif re.match(r"^/api/repair-suppressions/[^/]+/revoke$", path):
                self._post_repair_suppression_revoke(path.split("/")[3])
            elif path == "/api/quarantine/preview":
                self._post_quarantine_preview(body)
            elif path == "/api/quarantine/execute":
                self._post_quarantine_execute(body)
            else:
                self._send_error(404, "NOT_FOUND", "The requested resource was not found.")
        except ValueError as exc:
            self._send_error(400, "REQUEST_INVALID", str(exc))
        except svc.ServiceNotFound as exc:
            self._send_error(404, "NOT_FOUND", str(exc))
        except svc.ServiceConflict as exc:
            if exc.code == "ADMIN_REQUIRED":
                self._send_error(403, "AUTHORIZATION_ADMIN_REQUIRED", str(exc), details=exc.details)
            else:
                self._send_error(409, exc.code, str(exc), details=exc.details)
        except svc.AuthorizationFailure as exc:
            self._send_error(403, "AUTHORIZATION_ADMIN_REQUIRED", str(exc))
        except sqlite3.IntegrityError:
            self._send_error(409, "BUSINESS_CONFLICT", "The requested write conflicts with current data.")
        except Exception:
            self._send_error(500, "INTERNAL_ERROR", "An unexpected server error occurred.")

    def _post_issue_decision(self, issue_uuid: str, body: dict):
        service, role = self._issue_repair_reader()
        action, expected = body.get("action", ""), body.get("expected_updated_at", "")
        if not action or not expected: raise ValueError("action and expected_updated_at are required.")
        self._send_success(200, service.decide_issue(issue_uuid, role, action, expected, body))

    def _post_repair_decision(self, repair_uuid: str, body: dict):
        service, role = self._issue_repair_reader()
        action, expected = body.get("action", ""), body.get("expected_updated_at", "")
        if not action or not expected: raise ValueError("action and expected_updated_at are required.")
        self._send_success(200, service.decide_repair(repair_uuid, role, action, expected, body))

    def _repair_decision_policy(self):
        return svc.RepairDecisionService(
            svc.RepairService(repo.RepairRepository(open_db), repo.IssueRepository(open_db)),
            svc.OperationService(repo.OperationRepository(open_db)),
            repo.RepairSuppressionRepository(open_db), APP_CONFIG.get("archive_root", ""),
        )

    def _post_repair_suppression(self, body: dict):
        required = ("fingerprint", "scope_path", "reason", "expires_at")
        if any(not body.get(field) for field in required): raise ValueError("fingerprint, scope_path, reason, and expires_at are required.")
        record = self._repair_decision_policy().create_suppression(
            fingerprint=body["fingerprint"], scope_path=body["scope_path"], reason=body["reason"],
            creator=self._principal.get("device_name") or self._principal["role"], actor_role=self._principal["role"],
            expires_at=body["expires_at"],
        )
        self._send_success(201, {"suppression": record})

    def _post_repair_suppression_revoke(self, suppression_uuid: str):
        record = self._repair_decision_policy().revoke_suppression(
            suppression_uuid, actor=self._principal.get("device_name") or self._principal["role"], actor_role=self._principal["role"],
        )
        self._send_success(200, {"suppression": record})

    def _quarantine_contract(self):
        archive_root = APP_CONFIG.get("archive_root", "")
        quarantine_root = APP_CONFIG.get("quarantine_root") or str(RUNTIME_DIR / "quarantine")
        quarantine_repo = repo.QuarantineRepository(open_db)
        service = svc.QuarantineService(
            quarantine_repo, svc.OperationService(repo.OperationRepository(open_db)),
            archive_root, quarantine_root, create_db_snapshot,
        )
        return svc.QuarantineContractService(
            quarantine_repo, repo.RepairRepository(open_db), service,
            archive_root, quarantine_root, QUARANTINE_PREVIEW_SECRET,
        )

    def _post_quarantine_preview(self, body: dict):
        if not self._require_admin_principal(): return
        action = body.get("action")
        if action == "quarantine": result = self._quarantine_contract().preview_quarantine(body.get("repair_uuid", ""), body.get("reason", ""))
        elif action == "restore": result = self._quarantine_contract().preview_restore(body.get("item_uuid", ""))
        else: raise ValueError("Quarantine preview action must be quarantine or restore.")
        self._send_success(200, {"preview": result})

    def _post_quarantine_execute(self, body: dict):
        if not self._require_admin_principal(): return
        token = body.get("preview_token", "")
        if not token: raise ValueError("preview_token is required.")
        self._send_success(200, self._quarantine_contract().execute(token, self._principal["role"]))

    def _post_authenticated_registration_approval(self, path: str, body: dict) -> None:
        principal = getattr(self, "_principal", None)
        if principal is None or principal.get("role") != "admin":
            self._send_error(403, "AUTHORIZATION_ADMIN_REQUIRED", "An Admin Token is required.")
            return
        auth = svc.AuthenticationService(
            repo.AuthRepository(open_db),
            operation_service=svc.OperationService(repo.OperationRepository(open_db)),
        )
        registration_uuid = path.split("/")[4]
        try:
            issued = auth.approve_registration(
                registration_uuid,
                approved_role=body.get("approved_role"),
                approved_scopes=body.get("approved_scopes"),
            )
            self._send_success(200, issued)
        except svc.ServiceNotFound as exc:
            self._send_error(404, "NOT_FOUND", str(exc))
        except (svc.ServiceConflict, ValueError) as exc:
            self._send_error(409, getattr(exc, "code", "BUSINESS_CONFLICT"), str(exc))

    def _post_auth_registration_decision(self, path: str, body: dict):
        if not self._require_admin_principal(): return
        parts = path.split("/"); registration_uuid, action = parts[5], parts[6]
        auth = self._auth_admin_service()
        if action == "approve":
            self._send_success(200, auth.approve_registration(
                registration_uuid, approved_role=body.get("approved_role"),
                approved_scopes=body.get("approved_scopes"),
            ))
        else:
            auth.reject_registration(registration_uuid); self._send_success(200, {"status": "Rejected"})

    def _post_auth_renewal_decision(self, path: str, body: dict):
        if not self._require_admin_principal(): return
        parts = path.split("/"); renewal_uuid, action = parts[5], parts[6]
        auth = self._auth_admin_service()
        if action == "approve": self._send_success(200, auth.approve_renewal(renewal_uuid))
        else: auth.reject_renewal(renewal_uuid); self._send_success(200, {"status": "Rejected"})

    def _post_auth_token_revoke(self, path: str):
        if not self._require_admin_principal(): return
        token_uuid = path.split("/")[5]
        self._auth_admin_service().revoke_token(token_uuid)
        self._send_success(200, {"status": "Revoked", "token_uuid": token_uuid})

    def _post_token_renewal(self, body: dict) -> None:
        header = self.headers.get("Authorization", "")
        token = header[7:].strip() if header.startswith("Bearer ") else ""
        auth = svc.AuthenticationService(
            repo.AuthRepository(open_db),
            operation_service=svc.OperationService(repo.OperationRepository(open_db)),
        )
        try:
            renewal = auth.request_renewal(
                token,
                device_identity=body.get("device_identity", ""),
            )
            self._send_success(202, {"renewal": renewal})
        except svc.AuthenticationFailure as exc:
            self._send_error(401, exc.code, str(exc))
        except (svc.ServiceConflict, ValueError) as exc:
            self._send_error(409, getattr(exc, "code", "BUSINESS_CONFLICT"), str(exc))

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

    def _album_service(self) -> svc.AlbumService:
        return svc.AlbumService(
            album_repo=repo.AlbumRepository(open_db), log_fn=append_log,
            preview_secret=ALBUM_BATCH_PREVIEW_SECRET,
            operation_service=svc.OperationService(repo.OperationRepository(open_db)),
            initiator=svc.OP_INITIATOR_WEB_UI,
        )

    def _post_album_batch_preview(self, body: dict):
        preview = self._album_service().preview_batch(
            body.get("ids", []), body.get("changes", {}),
            overwrite_non_empty=body.get("overwrite_non_empty", False),
        )
        self._send_success(200, {"preview": preview})

    def _post_album_batch_execute(self, body: dict):
        token = body.get("preview_token", "")
        if not token:
            raise ValueError("The preview_token field is required.")
        self._send_success(200, {"result": self._album_service().execute_batch(token)})

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
        import_action = body.get("import_action", "")
        if not items_in:
            raise ValueError("The items field is required.")
        if not import_action:
            raise ValueError("The import_action field is required.")
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
            preview_secret=IMPORT_PREVIEW_SECRET,
        )
        preview = import_service.preview(
            items_in, archive_root, default_studio, import_action=import_action
        )
        self._send_success(200, {"preview": preview})

    def _post_import_execute(self, body: dict):
        preview_token = body.get("preview_token", "")
        if not preview_token:
            raise ValueError("The preview_token field is required.")

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
            preview_secret=IMPORT_PREVIEW_SECRET,
        )
        result = import_service.execute_preview(preview_token, archive_root, default_studio)
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

    def _post_backup_verify(self, identity: str):
        self._send_success(200, {"verification": self._backup_admin_service().verify(identity)})

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
                self._send_error(410, "HISTORICAL_WORKSPACE_RETIRED", "The historical Workspace Album API is retired.")
            elif re.match(r"^/api/ai-model-configurations/[^/]+$", path):
                if not self._require_admin_principal(): return
                expected = body.get("expected_version")
                if not isinstance(expected, int): raise ValueError("expected_version is required and must be an integer.")
                changes = {key: value for key, value in body.items() if key != "expected_version"}
                self._send_success(200, {"configuration": self._ai_model_configuration_service().update(path.split("/")[-1], expected, changes)})
            else:
                self._send_error(404, "NOT_FOUND", "The requested resource was not found.")
        except ValueError as exc:
            self._send_error(400, "REQUEST_INVALID", str(exc))
        except svc.ServiceNotFound as exc:
            self._send_error(404, "NOT_FOUND", str(exc))
        except svc.ServiceConflict as exc:
            self._send_error(409, exc.code, str(exc), details=exc.details)
        except sqlite3.IntegrityError:
            self._send_error(409, "BUSINESS_CONFLICT", "The requested write conflicts with current data.")
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
    print(f"Curator Backend running at http://{host}:{port}")
    print(f"Database: {DATABASE_PATH}")
    print(f"Backups: {BACKUP_DIR}")

    try:
        server.serve_forever()
    finally:
        STOP_EVENT.set()
        backup_thread.join(timeout=3)


if __name__ == "__main__":
    main()
