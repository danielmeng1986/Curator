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
# Import helpers
# ---------------------------------------------------------------------------

def parse_album_folder_name(folder_name: str) -> tuple[str, str]:
    m = ALBUM_FOLDER_RE.match(folder_name.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", folder_name.strip()


def alphabet_for_model(model_name: str) -> str:
    if not model_name:
        return "_"
    first = model_name[0]
    if first.isalpha():
        return first.upper()
    if first.isdigit():
        return "0-9"
    return "_"


def build_archive_path(model_name: str, studio_name: str, album_name: str) -> str:
    alpha = alphabet_for_model(model_name)
    return f"{alpha}/{model_name}/p/{studio_name}/{album_name}"

# ---------------------------------------------------------------------------
# AppHandler
# ---------------------------------------------------------------------------

class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
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

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

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
        try:
            body = self._read_json_body()
        except Exception as ex:
            self._send_json(400, {"ok": False, "error": f"Invalid JSON: {ex}"})
            return
        self._handle_api_post(path, body)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            body = self._read_json_body()
        except Exception as ex:
            self._send_json(400, {"ok": False, "error": f"Invalid JSON: {ex}"})
            return
        self._handle_api_put(path, body)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
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
            else:
                self._send_json(404, {"ok": False, "error": "Not found"})
        except Exception as ex:
            self._send_json(500, {"ok": False, "error": str(ex)})

    def _get_health(self):
        backup_catalog = build_backup_catalog()
        self._send_json(
            200,
            {
                "ok": True,
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
        self._send_json(200, {"ok": True, **APP_CONFIG})

    def _get_statuses(self):
        with open_db() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.name, s.description,
                    (SELECT COUNT(*) FROM album a WHERE a.status_id = s.id) as album_count,
                    (SELECT COUNT(*) FROM workspace_album wa WHERE wa.status_id = s.id) as workspace_album_count
                FROM status s ORDER BY s.id
                """
            ).fetchall()
        self._send_json(200, {"ok": True, "statuses": [dict(r) for r in rows]})

    def _get_models(self, qs: dict):
        q = qs.get("q", [""])[0].strip()
        limit = int(qs.get("limit", ["50"])[0])
        offset = int(qs.get("offset", ["0"])[0])
        pattern = f"%{q}%" if q else "%%"
        with open_db() as conn:
            rows = conn.execute(
                """
                SELECT id, uuid, display_name, primary_name, description,
                    country, ethnicity, eye_color, natural_hair_color, created_at, updated_at
                FROM model
                WHERE (display_name LIKE ? OR primary_name LIKE ?)
                ORDER BY COALESCE(display_name, primary_name)
                LIMIT ? OFFSET ?
                """,
                (pattern, pattern, limit, offset),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM model WHERE (display_name LIKE ? OR primary_name LIKE ?)",
                (pattern, pattern),
            ).fetchone()[0]
        self._send_json(
            200,
            {
                "ok": True,
                "models": [dict(r) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )

    def _get_model(self, model_id: int):
        with open_db() as conn:
            row = conn.execute(
                "SELECT * FROM model WHERE id = ?", (model_id,)
            ).fetchone()
            if row is None:
                self._send_json(404, {"ok": False, "error": "Model not found"})
                return
            albums = conn.execute(
                """
                SELECT a.id, a.title, a.capture_date, am.age_when_shot, am.role, am.remarks,
                    s.name as studio_name
                FROM album_model am
                JOIN album a ON a.id = am.album_id
                LEFT JOIN studio s ON s.id = a.studio_id
                WHERE am.model_id = ?
                ORDER BY a.capture_date DESC
                """,
                (model_id,),
            ).fetchall()
        self._send_json(
            200,
            {
                "ok": True,
                "model": dict(row),
                "albums": [dict(a) for a in albums],
            },
        )

    def _get_studios(self, qs: dict):
        q = qs.get("q", [""])[0].strip()
        limit = int(qs.get("limit", ["50"])[0])
        offset = int(qs.get("offset", ["0"])[0])
        pattern = f"%{q}%" if q else "%%"
        with open_db() as conn:
            rows = conn.execute(
                """
                SELECT id, uuid, name, website, description, media_scope, created_at, updated_at
                FROM studio WHERE name LIKE ? ORDER BY name LIMIT ? OFFSET ?
                """,
                (pattern, limit, offset),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM studio WHERE name LIKE ?", (pattern,)
            ).fetchone()[0]
        self._send_json(
            200,
            {
                "ok": True,
                "studios": [dict(r) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )

    def _get_studio(self, studio_id: int):
        with open_db() as conn:
            row = conn.execute(
                "SELECT * FROM studio WHERE id = ?", (studio_id,)
            ).fetchone()
            if row is None:
                self._send_json(404, {"ok": False, "error": "Studio not found"})
                return
            albums = conn.execute(
                """
                SELECT a.id, a.title, a.capture_date, a.publish_date, a.rating,
                    st.name as status_name
                FROM album a
                LEFT JOIN status st ON st.id = a.status_id
                WHERE a.studio_id = ?
                ORDER BY a.publish_date DESC
                """,
                (studio_id,),
            ).fetchall()
        self._send_json(
            200,
            {
                "ok": True,
                "studio": dict(row),
                "albums": [dict(a) for a in albums],
            },
        )

    def _get_albums(self, qs: dict):
        q = qs.get("q", [""])[0].strip()
        studio_id = qs.get("studio_id", [""])[0].strip()
        status_id = qs.get("status_id", [""])[0].strip()
        model_id = qs.get("model_id", [""])[0].strip()
        rating_min = qs.get("rating_min", [""])[0].strip()
        rating_max = qs.get("rating_max", [""])[0].strip()
        sort = qs.get("sort", ["updated_at"])[0].strip()
        limit = int(qs.get("limit", ["50"])[0])
        offset = int(qs.get("offset", ["0"])[0])

        sort_map = {
            "title": "a.title",
            "studio_name": "s.name",
            "publish_date": "a.publish_date",
            "rating": "a.rating",
            "updated_at": "a.updated_at",
            "capture_date": "a.capture_date",
        }
        order_col = sort_map.get(sort, "a.updated_at")

        conditions = []
        params: list = []

        if q:
            conditions.append("(a.title LIKE ? OR a.description LIKE ?)")
            params += [f"%{q}%", f"%{q}%"]
        if studio_id:
            conditions.append("a.studio_id = ?")
            params.append(int(studio_id))
        if status_id:
            conditions.append("a.status_id = ?")
            params.append(int(status_id))
        if model_id:
            conditions.append(
                "EXISTS (SELECT 1 FROM album_model am2 WHERE am2.album_id = a.id AND am2.model_id = ?)"
            )
            params.append(int(model_id))
        if rating_min:
            conditions.append("a.rating >= ?")
            params.append(float(rating_min))
        if rating_max:
            conditions.append("a.rating <= ?")
            params.append(float(rating_max))

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        query = f"""
            SELECT a.id, a.uuid, a.title, a.description, a.scene, a.location,
                a.capture_date, a.publish_date, a.rating, a.path,
                a.studio_id, a.status_id, a.created_at, a.updated_at,
                s.name as studio_name,
                st.name as status_name,
                GROUP_CONCAT(DISTINCT COALESCE(m.display_name, m.primary_name)) as model_names
            FROM album a
            LEFT JOIN studio s ON s.id = a.studio_id
            LEFT JOIN status st ON st.id = a.status_id
            LEFT JOIN album_model am ON am.album_id = a.id
            LEFT JOIN model m ON m.id = am.model_id
            {where_clause}
            GROUP BY a.id
            ORDER BY {order_col} DESC
            LIMIT ? OFFSET ?
        """

        count_query = f"""
            SELECT COUNT(DISTINCT a.id)
            FROM album a
            LEFT JOIN studio s ON s.id = a.studio_id
            LEFT JOIN status st ON st.id = a.status_id
            {where_clause}
        """

        with open_db() as conn:
            rows = conn.execute(query, params + [limit, offset]).fetchall()
            total = conn.execute(count_query, params).fetchone()[0]

        self._send_json(
            200,
            {
                "ok": True,
                "albums": [dict(r) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )

    def _get_album(self, album_id: int):
        with open_db() as conn:
            row = conn.execute(
                """
                SELECT a.*, s.name as studio_name, st.name as status_name
                FROM album a
                LEFT JOIN studio s ON s.id = a.studio_id
                LEFT JOIN status st ON st.id = a.status_id
                WHERE a.id = ?
                """,
                (album_id,),
            ).fetchone()
            if row is None:
                self._send_json(404, {"ok": False, "error": "Album not found"})
                return
            models = conn.execute(
                """
                SELECT am.id, am.model_id, am.age_when_shot, am.role, am.remarks,
                    COALESCE(m.display_name, m.primary_name) as model_name
                FROM album_model am
                JOIN model m ON m.id = am.model_id
                WHERE am.album_id = ?
                """,
                (album_id,),
            ).fetchall()
            relations = conn.execute(
                """
                SELECT ar.id, ar.related_album_id, ar.relation_type, ar.remarks,
                    a2.title as related_title, s2.name as related_studio
                FROM album_relation ar
                JOIN album a2 ON a2.id = ar.related_album_id
                LEFT JOIN studio s2 ON s2.id = a2.studio_id
                WHERE ar.album_id = ?
                """,
                (album_id,),
            ).fetchall()
            photos = conn.execute(
                """
                SELECT id, uuid, filename, relative_path, width, height, capture_time, created_at
                FROM photo WHERE album_id = ? ORDER BY filename
                """,
                (album_id,),
            ).fetchall()
        self._send_json(
            200,
            {
                "ok": True,
                "album": dict(row),
                "models": [dict(m) for m in models],
                "relations": [dict(r) for r in relations],
                "photos": [dict(p) for p in photos],
            },
        )

    def _get_workspace_albums(self, qs: dict):
        status_id = qs.get("status_id", [""])[0].strip()
        studio_name = qs.get("studio_name", [""])[0].strip()
        primary_model = qs.get("primary_model", [""])[0].strip()
        linked = qs.get("linked", [""])[0].strip().lower()
        q = qs.get("q", [""])[0].strip()
        limit = int(qs.get("limit", ["50"])[0])
        offset = int(qs.get("offset", ["0"])[0])

        conditions = []
        params: list = []

        if status_id:
            conditions.append("wa.status_id = ?")
            params.append(int(status_id))
        if studio_name:
            conditions.append("wa.studio_name LIKE ?")
            params.append(f"%{studio_name}%")
        if primary_model:
            conditions.append("wa.primary_model LIKE ?")
            params.append(f"%{primary_model}%")
        if linked == "yes":
            conditions.append("wa.album_id IS NOT NULL")
        elif linked == "no":
            conditions.append("wa.album_id IS NULL")
        if q:
            conditions.append(
                "(wa.album_name LIKE ? OR wa.primary_model LIKE ? OR wa.studio_name LIKE ?)"
            )
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        query = f"""
            SELECT wa.*, s.name as status_name
            FROM workspace_album wa
            LEFT JOIN status s ON s.id = wa.status_id
            {where_clause}
            ORDER BY wa.id DESC
            LIMIT ? OFFSET ?
        """
        count_query = f"""
            SELECT COUNT(*) FROM workspace_album wa
            LEFT JOIN status s ON s.id = wa.status_id
            {where_clause}
        """

        with open_db() as conn:
            rows = conn.execute(query, params + [limit, offset]).fetchall()
            total = conn.execute(count_query, params).fetchone()[0]

        self._send_json(
            200,
            {
                "ok": True,
                "albums": [dict(r) for r in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            },
        )

    def _get_workspace_album(self, wa_id: int):
        with open_db() as conn:
            row = conn.execute(
                """
                SELECT wa.*, s.name as status_name
                FROM workspace_album wa
                LEFT JOIN status s ON s.id = wa.status_id
                WHERE wa.id = ?
                """,
                (wa_id,),
            ).fetchone()
            if row is None:
                self._send_json(404, {"ok": False, "error": "Workspace album not found"})
                return
            d = dict(row)
            # belongs_to info
            if d.get("belongs_to_album_id"):
                parent = conn.execute(
                    "SELECT id, album_name, primary_model FROM workspace_album WHERE id = ?",
                    (d["belongs_to_album_id"],),
                ).fetchone()
                d["belongs_to"] = dict(parent) if parent else None
            else:
                d["belongs_to"] = None
            # linked album info
            if d.get("album_id"):
                linked = conn.execute(
                    "SELECT id, title FROM album WHERE id = ?", (d["album_id"],)
                ).fetchone()
                d["linked_album"] = dict(linked) if linked else None
            else:
                d["linked_album"] = None
        self._send_json(200, {"ok": True, "album": d})

    def _get_backups(self):
        catalog = build_backup_catalog()
        items = [public_backup_item(x) for x in catalog]
        self._send_json(
            200, {"ok": True, "items": items, "retention_days": RETENTION_DAYS}
        )

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
                self._send_json(404, {"ok": False, "error": "Not found"})
        except Exception as ex:
            self._send_json(500, {"ok": False, "error": str(ex)})

    def _post_status(self, body: dict):
        name = body.get("name", "").strip()
        description = body.get("description", "")
        if not name:
            self._send_json(400, {"ok": False, "error": "name is required"})
            return
        with open_db() as conn:
            cur = conn.execute(
                "INSERT INTO status (name, description) VALUES (?, ?)",
                (name, description),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM status WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        self._send_json(201, {"ok": True, "id": cur.lastrowid, "status": dict(row)})

    def _post_model(self, body: dict):
        now = utc_now_iso()
        new_uuid = str(uuid.uuid4())
        fields = (
            "display_name", "primary_name", "description",
            "country", "ethnicity", "eye_color", "natural_hair_color",
        )
        vals = {f: body.get(f) for f in fields}
        with open_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO model
                    (uuid, display_name, primary_name, description, country, ethnicity,
                     eye_color, natural_hair_color, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_uuid,
                    vals["display_name"],
                    vals["primary_name"],
                    vals["description"],
                    vals["country"],
                    vals["ethnicity"],
                    vals["eye_color"],
                    vals["natural_hair_color"],
                    now,
                    now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM model WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        self._send_json(201, {"ok": True, "id": cur.lastrowid, "model": dict(row)})

    def _post_studio(self, body: dict):
        now = utc_now_iso()
        new_uuid = str(uuid.uuid4())
        with open_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO studio (uuid, name, website, description, media_scope, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_uuid,
                    body.get("name"),
                    body.get("website"),
                    body.get("description"),
                    body.get("media_scope"),
                    now,
                    now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM studio WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        self._send_json(201, {"ok": True, "id": cur.lastrowid, "studio": dict(row)})

    def _post_album(self, body: dict):
        now = utc_now_iso()
        new_uuid = str(uuid.uuid4())
        models = body.get("models", [])
        relations = body.get("relations", [])
        with open_db() as conn:
            try:
                conn.execute("BEGIN")
                cur = conn.execute(
                    """
                    INSERT INTO album
                        (uuid, studio_id, status_id, title, description, scene, location,
                         capture_date, publish_date, rating, path, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_uuid,
                        body.get("studio_id"),
                        body.get("status_id"),
                        body.get("title"),
                        body.get("description"),
                        body.get("scene"),
                        body.get("location"),
                        body.get("capture_date"),
                        body.get("publish_date"),
                        body.get("rating"),
                        body.get("path"),
                        now,
                        now,
                    ),
                )
                album_id = cur.lastrowid
                for m in models:
                    conn.execute(
                        """
                        INSERT INTO album_model (album_id, model_id, age_when_shot, role, remarks)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            album_id,
                            m.get("model_id"),
                            m.get("age_when_shot"),
                            m.get("role"),
                            m.get("remarks"),
                        ),
                    )
                for r in relations:
                    conn.execute(
                        """
                        INSERT INTO album_relation (album_id, related_album_id, relation_type, remarks)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            album_id,
                            r.get("related_album_id"),
                            r.get("relation_type"),
                            r.get("remarks"),
                        ),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        append_log({"timestamp": now, "action": "create_album", "album_id": album_id, "success": True})
        self._send_json(201, {"ok": True, "id": album_id})

    def _post_album_model(self, album_id: int, body: dict):
        with open_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_model (album_id, model_id, age_when_shot, role, remarks)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    album_id,
                    body.get("model_id"),
                    body.get("age_when_shot"),
                    body.get("role"),
                    body.get("remarks"),
                ),
            )
            conn.commit()
        self._send_json(201, {"ok": True, "id": cur.lastrowid})

    def _post_album_relation(self, album_id: int, body: dict):
        with open_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_relation (album_id, related_album_id, relation_type, remarks)
                VALUES (?, ?, ?, ?)
                """,
                (
                    album_id,
                    body.get("related_album_id"),
                    body.get("relation_type"),
                    body.get("remarks"),
                ),
            )
            conn.commit()
        self._send_json(201, {"ok": True, "id": cur.lastrowid})

    def _post_album_photo(self, album_id: int, body: dict):
        now = utc_now_iso()
        new_uuid = str(uuid.uuid4())
        with open_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO photo
                    (uuid, album_id, filename, relative_path, hash, width, height, capture_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_uuid,
                    album_id,
                    body.get("filename"),
                    body.get("relative_path"),
                    body.get("hash"),
                    body.get("width"),
                    body.get("height"),
                    body.get("capture_time"),
                    now,
                ),
            )
            conn.commit()
        self._send_json(201, {"ok": True, "id": cur.lastrowid})

    def _post_workspace_batch(self, body: dict):
        ids = body.get("ids", [])
        changes = body.get("changes", {})
        if not ids:
            self._send_json(400, {"ok": False, "error": "ids is required"})
            return

        allowed = {
            "status_id", "studio_name", "album_name", "primary_model",
            "additional_models", "remark", "expected_path", "ai_result",
            "belongs_to_album_id", "album_id",
        }
        filtered = {k: v for k, v in changes.items() if k in allowed}
        if not filtered:
            self._send_json(400, {"ok": False, "error": "No valid fields to update"})
            return

        try:
            snap = create_db_snapshot("workspace_batch")
            append_backup_log(
                {
                    "timestamp": utc_now_iso(),
                    "reason": "workspace_batch",
                    "ok": True,
                    "snapshot": str(snap),
                    "tag": "",
                }
            )
        except Exception as ex:
            append_backup_log(
                {"timestamp": utc_now_iso(), "reason": "workspace_batch", "ok": False, "error": str(ex), "tag": ""}
            )

        set_clauses = ", ".join(f"{k} = ?" for k in filtered)
        set_values = list(filtered.values())
        updated = 0
        with open_db() as conn:
            for wa_id in ids:
                conn.execute(
                    f"UPDATE workspace_album SET {set_clauses} WHERE id = ?",
                    set_values + [wa_id],
                )
                updated += 1
            conn.commit()
        self._send_json(200, {"ok": True, "updated": updated})

    def _post_import_preview(self, body: dict):
        items_in = body.get("items", [])
        global APP_CONFIG
        APP_CONFIG = load_app_config()
        archive_root = APP_CONFIG.get("archive_root", "")
        default_studio = APP_CONFIG.get("default_import_studio", "")

        preview_items = []
        for item in items_in:
            folder_name = item.get("folder_name", "")
            studio_name = item.get("studio_name") or default_studio
            model_name = item.get("model_name", "")
            album_name = item.get("album_name", "")

            if not model_name and not album_name and folder_name:
                model_name, album_name = parse_album_folder_name(folder_name)

            expected_path = build_archive_path(model_name, studio_name, album_name)
            full_path = Path(archive_root) / expected_path

            with open_db() as conn:
                studio_row = conn.execute(
                    "SELECT id, name FROM studio WHERE LOWER(name) = LOWER(?)",
                    (studio_name,),
                ).fetchone()
                studio_exists = studio_row is not None
                studio_id = studio_row["id"] if studio_row else None

                model_row = conn.execute(
                    "SELECT id FROM model WHERE LOWER(display_name) = LOWER(?) OR LOWER(primary_name) = LOWER(?)",
                    (model_name, model_name),
                ).fetchone()
                model_exists = model_row is not None
                model_id = model_row["id"] if model_row else None

                album_exists = False
                album_id = None
                if studio_id:
                    album_row = conn.execute(
                        "SELECT id FROM album WHERE studio_id = ? AND LOWER(title) = LOWER(?)",
                        (studio_id, album_name),
                    ).fetchone()
                    if album_row:
                        album_exists = True
                        album_id = album_row["id"]

            path_exists = full_path.exists()
            can_import = not album_exists and not path_exists

            preview_items.append(
                {
                    "folder_name": folder_name,
                    "model_name": model_name,
                    "album_name": album_name,
                    "studio_name": studio_name,
                    "expected_path": expected_path,
                    "source_path": item.get("source_path", ""),
                    "model_exists": model_exists,
                    "model_id": model_id,
                    "studio_exists": studio_exists,
                    "studio_id": studio_id,
                    "album_exists": album_exists,
                    "album_id": album_id,
                    "path_exists": path_exists,
                    "can_import": can_import,
                }
            )

        total = len(preview_items)
        importable = sum(1 for x in preview_items if x["can_import"])
        self._send_json(
            200,
            {
                "ok": True,
                "preview": {
                    "items": preview_items,
                    "summary": {
                        "total": total,
                        "importable": importable,
                        "skipped": total - importable,
                    },
                },
            },
        )

    def _post_import_execute(self, body: dict):
        items_in = body.get("items", [])
        if not items_in:
            self._send_json(400, {"ok": False, "error": "items is required"})
            return

        global APP_CONFIG
        APP_CONFIG = load_app_config()
        archive_root = APP_CONFIG.get("archive_root", "")
        default_studio = APP_CONFIG.get("default_import_studio", "")

        try:
            snap = create_db_snapshot("import")
            append_backup_log(
                {
                    "timestamp": utc_now_iso(),
                    "reason": "import",
                    "ok": True,
                    "snapshot": str(snap),
                    "tag": "",
                }
            )
        except Exception as ex:
            append_backup_log(
                {"timestamp": utc_now_iso(), "reason": "import", "ok": False, "error": str(ex), "tag": ""}
            )

        results = []
        created_albums = 0
        skipped = 0
        errors = 0

        for item in items_in:
            folder_name = item.get("folder_name", "")
            studio_name = item.get("studio_name") or default_studio
            model_name = item.get("model_name", "")
            album_name = item.get("album_name", "")
            source_path = item.get("source_path", "")

            if not model_name and not album_name and folder_name:
                model_name, album_name = parse_album_folder_name(folder_name)

            expected_path = build_archive_path(model_name, studio_name, album_name)
            full_dest = Path(archive_root) / expected_path

            result: dict = {
                "folder_name": folder_name,
                "model_name": model_name,
                "album_name": album_name,
                "studio_name": studio_name,
                "expected_path": expected_path,
                "ok": False,
                "skipped": False,
                "error": None,
            }

            try:
                now = utc_now_iso()
                with open_db() as conn:
                    # Find or create studio
                    studio_row = conn.execute(
                        "SELECT id FROM studio WHERE LOWER(name) = LOWER(?)",
                        (studio_name,),
                    ).fetchone()
                    if studio_row:
                        studio_id = studio_row["id"]
                    else:
                        new_uuid = str(uuid.uuid4())
                        cur = conn.execute(
                            "INSERT INTO studio (uuid, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                            (new_uuid, studio_name, now, now),
                        )
                        studio_id = cur.lastrowid

                    # Find or create model
                    model_row = conn.execute(
                        "SELECT id FROM model WHERE LOWER(display_name) = LOWER(?) OR LOWER(primary_name) = LOWER(?)",
                        (model_name, model_name),
                    ).fetchone()
                    if model_row:
                        model_id = model_row["id"]
                    else:
                        new_uuid = str(uuid.uuid4())
                        cur = conn.execute(
                            "INSERT INTO model (uuid, display_name, created_at, updated_at) VALUES (?, ?, ?, ?)",
                            (new_uuid, model_name, now, now),
                        )
                        model_id = cur.lastrowid

                    # Check if album exists
                    album_row = conn.execute(
                        "SELECT id FROM album WHERE studio_id = ? AND LOWER(title) = LOWER(?)",
                        (studio_id, album_name),
                    ).fetchone()
                    if album_row:
                        result["skipped"] = True
                        result["album_id"] = album_row["id"]
                        skipped += 1
                        results.append(result)
                        continue

                    # Create album
                    new_uuid = str(uuid.uuid4())
                    cur = conn.execute(
                        """
                        INSERT INTO album
                            (uuid, studio_id, title, path, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (new_uuid, studio_id, album_name, expected_path, now, now),
                    )
                    album_id = cur.lastrowid

                    # Create album_model
                    conn.execute(
                        "INSERT INTO album_model (album_id, model_id) VALUES (?, ?)",
                        (album_id, model_id),
                    )
                    conn.commit()

                # Move files if source provided
                if source_path and Path(source_path).exists():
                    full_dest.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(source_path, str(full_dest), dirs_exist_ok=True)

                result["ok"] = True
                result["album_id"] = album_id
                created_albums += 1
                append_log(
                    {
                        "timestamp": now,
                        "action": "import_album",
                        "album_id": album_id,
                        "model_name": model_name,
                        "studio_name": studio_name,
                        "success": True,
                    }
                )
            except Exception as ex:
                result["error"] = str(ex)
                errors += 1

            results.append(result)

        self._send_json(
            200,
            {
                "ok": True,
                "results": results,
                "summary": {
                    "total": len(items_in),
                    "created": created_albums,
                    "skipped": skipped,
                    "errors": errors,
                },
            },
        )

    def _post_backup(self, body: dict):
        reason = body.get("reason", "manual")
        tag = body.get("tag", "")
        try:
            snap = create_db_snapshot(reason, tag)
            entry = {
                "timestamp": utc_now_iso(),
                "reason": reason,
                "ok": True,
                "snapshot": str(snap),
                "tag": tag,
            }
            append_backup_log(entry)
            self._send_json(
                200, {"ok": True, "snapshot": str(snap), "filename": snap.name}
            )
        except Exception as ex:
            append_backup_log(
                {"timestamp": utc_now_iso(), "reason": reason, "ok": False, "error": str(ex), "tag": tag}
            )
            self._send_json(500, {"ok": False, "error": str(ex)})

    def _post_backup_cleanup(self):
        result = cleanup_expired_snapshots(RETENTION_DAYS)
        self._send_json(200, {"ok": True, **result})

    def _post_rollback(self, body: dict):
        mode = body.get("mode", "")
        selected = None

        if mode == "snapshot":
            snap_path_str = body.get("snapshot", "")
            if not snap_path_str:
                self._send_json(400, {"ok": False, "error": "snapshot path required"})
                return
            snap_path = Path(snap_path_str)
            if not snap_path.exists():
                self._send_json(404, {"ok": False, "error": "Snapshot not found"})
                return
            catalog = build_backup_catalog()
            for item in catalog:
                if Path(item["path"]).resolve() == snap_path.resolve():
                    selected = item
                    break
            if selected is None:
                selected = {
                    "path": str(snap_path),
                    "filename": snap_path.name,
                    "tag": parse_tag_from_name(snap_path),
                    "created_at": None,
                }
        elif mode == "tag":
            tag = body.get("tag", "").strip()
            if not tag:
                self._send_json(400, {"ok": False, "error": "tag required"})
                return
            selected = find_snapshot_by_tag(tag)
            if selected is None:
                self._send_json(404, {"ok": False, "error": f"No snapshot with tag '{tag}'"})
                return
        elif mode == "before_last_operation":
            last_entry = get_last_success_change_entry()
            if last_entry is None:
                self._send_json(404, {"ok": False, "error": "No successful change entry found"})
                return
            ts_str = last_entry.get("timestamp", "")
            try:
                target_dt = parse_iso_datetime(ts_str)
            except Exception:
                self._send_json(400, {"ok": False, "error": "Cannot parse timestamp from last entry"})
                return
            selected = find_snapshot_before_or_at(target_dt)
            if selected is None:
                self._send_json(404, {"ok": False, "error": "No snapshot found before last operation"})
                return
        else:
            self._send_json(400, {"ok": False, "error": f"Unknown mode: {mode}"})
            return

        snap_path = Path(selected["path"])
        if not snap_path.exists():
            self._send_json(404, {"ok": False, "error": "Snapshot file does not exist"})
            return

        # Create safety backup before rolling back
        try:
            safety = create_db_snapshot("pre_rollback")
            append_backup_log(
                {
                    "timestamp": utc_now_iso(),
                    "reason": "pre_rollback",
                    "ok": True,
                    "snapshot": str(safety),
                    "tag": "",
                }
            )
        except Exception as ex:
            append_backup_log(
                {"timestamp": utc_now_iso(), "reason": "pre_rollback", "ok": False, "error": str(ex), "tag": ""}
            )

        try:
            restore_database_from_snapshot(snap_path)
        except Exception as ex:
            append_rollback_log(
                {
                    "timestamp": utc_now_iso(),
                    "mode": mode,
                    "snapshot": str(snap_path),
                    "ok": False,
                    "error": str(ex),
                }
            )
            self._send_json(500, {"ok": False, "error": f"Restore failed: {ex}"})
            return

        append_rollback_log(
            {
                "timestamp": utc_now_iso(),
                "mode": mode,
                "snapshot": str(snap_path),
                "ok": True,
            }
        )
        self._send_json(
            200,
            {"ok": True, "selected_snapshot": public_backup_item(selected)},
        )

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
                self._send_json(404, {"ok": False, "error": "Not found"})
        except Exception as ex:
            self._send_json(500, {"ok": False, "error": str(ex)})

    def _put_status(self, status_id: int, body: dict):
        with open_db() as conn:
            conn.execute(
                "UPDATE status SET name = ?, description = ? WHERE id = ?",
                (body.get("name"), body.get("description"), status_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM status WHERE id = ?", (status_id,)
            ).fetchone()
        if row is None:
            self._send_json(404, {"ok": False, "error": "Status not found"})
            return
        self._send_json(200, {"ok": True, "status": dict(row)})

    def _put_model(self, model_id: int, body: dict):
        now = utc_now_iso()
        with open_db() as conn:
            conn.execute(
                """
                UPDATE model SET
                    display_name = ?, primary_name = ?, description = ?,
                    country = ?, ethnicity = ?, eye_color = ?, natural_hair_color = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    body.get("display_name"),
                    body.get("primary_name"),
                    body.get("description"),
                    body.get("country"),
                    body.get("ethnicity"),
                    body.get("eye_color"),
                    body.get("natural_hair_color"),
                    now,
                    model_id,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM model WHERE id = ?", (model_id,)
            ).fetchone()
        if row is None:
            self._send_json(404, {"ok": False, "error": "Model not found"})
            return
        append_log({"timestamp": now, "action": "update_model", "model_id": model_id, "success": True})
        self._send_json(200, {"ok": True, "model": dict(row)})

    def _put_studio(self, studio_id: int, body: dict):
        now = utc_now_iso()
        with open_db() as conn:
            conn.execute(
                """
                UPDATE studio SET
                    name = ?, website = ?, description = ?, media_scope = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    body.get("name"),
                    body.get("website"),
                    body.get("description"),
                    body.get("media_scope"),
                    now,
                    studio_id,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM studio WHERE id = ?", (studio_id,)
            ).fetchone()
        if row is None:
            self._send_json(404, {"ok": False, "error": "Studio not found"})
            return
        self._send_json(200, {"ok": True, "studio": dict(row)})

    def _put_album(self, album_id: int, body: dict):
        now = utc_now_iso()
        models = body.get("models", [])
        relations = body.get("relations", [])
        with open_db() as conn:
            try:
                conn.execute("BEGIN")
                conn.execute(
                    """
                    UPDATE album SET
                        studio_id = ?, status_id = ?, title = ?, description = ?,
                        scene = ?, location = ?, capture_date = ?, publish_date = ?,
                        rating = ?, path = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        body.get("studio_id"),
                        body.get("status_id"),
                        body.get("title"),
                        body.get("description"),
                        body.get("scene"),
                        body.get("location"),
                        body.get("capture_date"),
                        body.get("publish_date"),
                        body.get("rating"),
                        body.get("path"),
                        now,
                        album_id,
                    ),
                )
                conn.execute("DELETE FROM album_model WHERE album_id = ?", (album_id,))
                for m in models:
                    conn.execute(
                        "INSERT INTO album_model (album_id, model_id, age_when_shot, role, remarks) VALUES (?, ?, ?, ?, ?)",
                        (album_id, m.get("model_id"), m.get("age_when_shot"), m.get("role"), m.get("remarks")),
                    )
                conn.execute("DELETE FROM album_relation WHERE album_id = ?", (album_id,))
                for r in relations:
                    conn.execute(
                        "INSERT INTO album_relation (album_id, related_album_id, relation_type, remarks) VALUES (?, ?, ?, ?)",
                        (album_id, r.get("related_album_id"), r.get("relation_type"), r.get("remarks")),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        append_log({"timestamp": now, "action": "update_album", "album_id": album_id, "success": True})
        self._send_json(200, {"ok": True})

    def _put_album_model(self, album_id: int, am_id: int, body: dict):
        with open_db() as conn:
            conn.execute(
                """
                UPDATE album_model SET age_when_shot = ?, role = ?, remarks = ?
                WHERE id = ? AND album_id = ?
                """,
                (body.get("age_when_shot"), body.get("role"), body.get("remarks"), am_id, album_id),
            )
            conn.commit()
        self._send_json(200, {"ok": True})

    def _put_album_relation(self, album_id: int, relation_id: int, body: dict):
        with open_db() as conn:
            conn.execute(
                """
                UPDATE album_relation SET relation_type = ?, remarks = ?
                WHERE id = ? AND album_id = ?
                """,
                (body.get("relation_type"), body.get("remarks"), relation_id, album_id),
            )
            conn.commit()
        self._send_json(200, {"ok": True})

    def _put_photo(self, photo_id: int, body: dict):
        with open_db() as conn:
            conn.execute(
                """
                UPDATE photo SET
                    filename = ?, relative_path = ?, width = ?, height = ?, capture_time = ?
                WHERE id = ?
                """,
                (
                    body.get("filename"),
                    body.get("relative_path"),
                    body.get("width"),
                    body.get("height"),
                    body.get("capture_time"),
                    photo_id,
                ),
            )
            conn.commit()
        self._send_json(200, {"ok": True})

    def _put_workspace_album(self, wa_id: int, body: dict):
        allowed = {
            "current_path", "expected_path", "primary_model", "studio_name",
            "album_name", "additional_models", "status_id", "remark",
            "belongs_to_album_id", "ai_result", "album_id",
        }
        filtered = {k: v for k, v in body.items() if k in allowed}
        if not filtered:
            self._send_json(400, {"ok": False, "error": "No valid fields to update"})
            return
        set_clauses = ", ".join(f"{k} = ?" for k in filtered)
        set_values = list(filtered.values())
        with open_db() as conn:
            conn.execute(
                f"UPDATE workspace_album SET {set_clauses} WHERE id = ?",
                set_values + [wa_id],
            )
            conn.commit()
        self._send_json(200, {"ok": True})

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
                self._send_json(404, {"ok": False, "error": "Not found"})
        except Exception as ex:
            self._send_json(500, {"ok": False, "error": str(ex)})

    def _delete_status(self, status_id: int):
        with open_db() as conn:
            album_refs = conn.execute(
                "SELECT COUNT(*) FROM album WHERE status_id = ?", (status_id,)
            ).fetchone()[0]
            wa_refs = conn.execute(
                "SELECT COUNT(*) FROM workspace_album WHERE status_id = ?", (status_id,)
            ).fetchone()[0]
            if album_refs > 0 or wa_refs > 0:
                self._send_json(
                    409,
                    {
                        "ok": False,
                        "error": f"Status is referenced by {album_refs} album(s) and {wa_refs} workspace album(s)",
                    },
                )
                return
            conn.execute("DELETE FROM status WHERE id = ?", (status_id,))
            conn.commit()
        self._send_json(200, {"ok": True})

    def _delete_model(self, model_id: int):
        with open_db() as conn:
            refs = conn.execute(
                "SELECT COUNT(*) FROM album_model WHERE model_id = ?", (model_id,)
            ).fetchone()[0]
            if refs > 0:
                self._send_json(
                    409,
                    {"ok": False, "error": f"Model is referenced by {refs} album(s)"},
                )
                return
            conn.execute("DELETE FROM model WHERE id = ?", (model_id,))
            conn.commit()
        self._send_json(200, {"ok": True})

    def _delete_studio(self, studio_id: int):
        with open_db() as conn:
            refs = conn.execute(
                "SELECT COUNT(*) FROM album WHERE studio_id = ?", (studio_id,)
            ).fetchone()[0]
            if refs > 0:
                self._send_json(
                    409,
                    {"ok": False, "error": f"Studio is referenced by {refs} album(s)"},
                )
                return
            conn.execute("DELETE FROM studio WHERE id = ?", (studio_id,))
            conn.commit()
        self._send_json(200, {"ok": True})

    def _delete_album(self, album_id: int):
        now = utc_now_iso()
        with open_db() as conn:
            try:
                conn.execute("BEGIN")
                conn.execute("DELETE FROM album_model WHERE album_id = ?", (album_id,))
                conn.execute(
                    "DELETE FROM album_relation WHERE album_id = ? OR related_album_id = ?",
                    (album_id, album_id),
                )
                conn.execute("DELETE FROM photo WHERE album_id = ?", (album_id,))
                conn.execute("DELETE FROM album WHERE id = ?", (album_id,))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        append_log({"timestamp": now, "action": "delete_album", "album_id": album_id, "success": True})
        self._send_json(200, {"ok": True})

    def _delete_album_model(self, album_id: int, am_id: int):
        with open_db() as conn:
            conn.execute(
                "DELETE FROM album_model WHERE id = ? AND album_id = ?",
                (am_id, album_id),
            )
            conn.commit()
        self._send_json(200, {"ok": True})

    def _delete_album_relation(self, album_id: int, relation_id: int):
        with open_db() as conn:
            conn.execute(
                "DELETE FROM album_relation WHERE id = ? AND album_id = ?",
                (relation_id, album_id),
            )
            conn.commit()
        self._send_json(200, {"ok": True})

    def _delete_photo(self, photo_id: int):
        with open_db() as conn:
            conn.execute("DELETE FROM photo WHERE id = ?", (photo_id,))
            conn.commit()
        self._send_json(200, {"ok": True})


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
