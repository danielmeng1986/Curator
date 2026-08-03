#!/usr/bin/env python3
"""Application service layer for Curator Backend.

Services own business rules, workflow decisions, and transaction boundaries.
They are independent of HTTP and called by transport adapters (AppHandler).

Each service accepts its infrastructure dependencies (db_factory, snapshot and
logging callables) at construction time so they can be tested in isolation
without HTTP machinery.

Persistence notes
-----------------
Services call ``open_db()`` (supplied as ``db_factory``) directly for now.
Formal repository boundaries are deferred to BT-005 (Centralise Repository
Access).
"""

from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Service exceptions
# ---------------------------------------------------------------------------

class ServiceConflict(Exception):
    """Raised when a business or data conflict prevents an operation.

    Attributes:
        code: Stable error code family (e.g. ``"BUSINESS_CONFLICT"``).
        details: Optional structured context for the caller.
    """

    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details


class ServiceNotFound(Exception):
    """Raised when a required resource cannot be located."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# StatusService
# ---------------------------------------------------------------------------

class StatusService:
    """Business rules for status management."""

    def __init__(self, db_factory):
        self._db = db_factory

    def delete(self, status_id: int) -> None:
        """Delete a status after verifying it has no references.

        Raises:
            ServiceConflict: If any album or workspace album references the
                status.
        """
        with self._db() as conn:
            album_refs = conn.execute(
                "SELECT COUNT(*) FROM album WHERE status_id = ?", (status_id,)
            ).fetchone()[0]
            wa_refs = conn.execute(
                "SELECT COUNT(*) FROM workspace_album WHERE status_id = ?",
                (status_id,),
            ).fetchone()[0]
            if album_refs > 0 or wa_refs > 0:
                raise ServiceConflict(
                    "BUSINESS_CONFLICT",
                    "The status is still referenced and cannot be deleted.",
                    {"album_refs": album_refs, "workspace_album_refs": wa_refs},
                )
            conn.execute("DELETE FROM status WHERE id = ?", (status_id,))
            conn.commit()


# ---------------------------------------------------------------------------
# ModelService
# ---------------------------------------------------------------------------

class ModelService:
    """Business rules for model management."""

    def __init__(self, db_factory, log_fn=None):
        self._db = db_factory
        self._log = log_fn or (lambda _: None)

    def update_fields(self, model_id: int, data: dict) -> dict:
        """Update model fields and return the refreshed record.

        Raises:
            ServiceNotFound: If no model with ``model_id`` exists.
        """
        now = _utc_now_iso()
        with self._db() as conn:
            conn.execute(
                """
                UPDATE model SET
                    display_name = ?, primary_name = ?, description = ?,
                    country = ?, ethnicity = ?, eye_color = ?, natural_hair_color = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    data.get("display_name"),
                    data.get("primary_name"),
                    data.get("description"),
                    data.get("country"),
                    data.get("ethnicity"),
                    data.get("eye_color"),
                    data.get("natural_hair_color"),
                    now,
                    model_id,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM model WHERE id = ?", (model_id,)
            ).fetchone()
        if row is None:
            raise ServiceNotFound("Model not found.")
        self._log(
            {"timestamp": now, "action": "update_model", "model_id": model_id, "success": True}
        )
        return dict(row)

    def delete(self, model_id: int) -> None:
        """Delete a model after verifying it has no album references.

        Raises:
            ServiceConflict: If the model is referenced by any album.
        """
        with self._db() as conn:
            refs = conn.execute(
                "SELECT COUNT(*) FROM album_model WHERE model_id = ?", (model_id,)
            ).fetchone()[0]
            if refs > 0:
                raise ServiceConflict(
                    "BUSINESS_CONFLICT",
                    "The model is still referenced by albums and cannot be deleted.",
                    {"album_refs": refs},
                )
            conn.execute("DELETE FROM model WHERE id = ?", (model_id,))
            conn.commit()


# ---------------------------------------------------------------------------
# StudioService
# ---------------------------------------------------------------------------

class StudioService:
    """Business rules for studio management."""

    def __init__(self, db_factory):
        self._db = db_factory

    def delete(self, studio_id: int) -> None:
        """Delete a studio after verifying it has no album references.

        Raises:
            ServiceConflict: If any album references the studio.
        """
        with self._db() as conn:
            refs = conn.execute(
                "SELECT COUNT(*) FROM album WHERE studio_id = ?", (studio_id,)
            ).fetchone()[0]
            if refs > 0:
                raise ServiceConflict(
                    "BUSINESS_CONFLICT",
                    "The studio is still referenced by albums and cannot be deleted.",
                    {"album_refs": refs},
                )
            conn.execute("DELETE FROM studio WHERE id = ?", (studio_id,))
            conn.commit()


# ---------------------------------------------------------------------------
# AlbumService
# ---------------------------------------------------------------------------

class AlbumService:
    """Workflow owner for album create, update, and delete operations.

    Owns transaction boundaries and audit log writes for material album
    changes.
    """

    def __init__(self, db_factory, log_fn):
        self._db = db_factory
        self._log = log_fn

    def create(self, data: dict, models: list, relations: list) -> int:
        """Create an album with associated models and relations atomically.

        Returns:
            The new album's integer id.
        """
        now = _utc_now_iso()
        new_uuid = str(uuid.uuid4())
        with self._db() as conn:
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
                        data.get("studio_id"),
                        data.get("status_id"),
                        data.get("title"),
                        data.get("description"),
                        data.get("scene"),
                        data.get("location"),
                        data.get("capture_date"),
                        data.get("publish_date"),
                        data.get("rating"),
                        data.get("path"),
                        now,
                        now,
                    ),
                )
                album_id = cur.lastrowid
                for m in models:
                    conn.execute(
                        """
                        INSERT INTO album_model
                            (album_id, model_id, age_when_shot, role, remarks)
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
                        INSERT INTO album_relation
                            (album_id, related_album_id, relation_type, remarks)
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
        self._log(
            {"timestamp": now, "action": "create_album", "album_id": album_id, "success": True}
        )
        return album_id

    def update(
        self, album_id: int, data: dict, models: list, relations: list
    ) -> None:
        """Replace album fields, model list, and relation list atomically."""
        now = _utc_now_iso()
        with self._db() as conn:
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
                        data.get("studio_id"),
                        data.get("status_id"),
                        data.get("title"),
                        data.get("description"),
                        data.get("scene"),
                        data.get("location"),
                        data.get("capture_date"),
                        data.get("publish_date"),
                        data.get("rating"),
                        data.get("path"),
                        now,
                        album_id,
                    ),
                )
                conn.execute("DELETE FROM album_model WHERE album_id = ?", (album_id,))
                for m in models:
                    conn.execute(
                        """
                        INSERT INTO album_model
                            (album_id, model_id, age_when_shot, role, remarks)
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
                conn.execute(
                    "DELETE FROM album_relation WHERE album_id = ?", (album_id,)
                )
                for r in relations:
                    conn.execute(
                        """
                        INSERT INTO album_relation
                            (album_id, related_album_id, relation_type, remarks)
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
        self._log(
            {"timestamp": now, "action": "update_album", "album_id": album_id, "success": True}
        )

    def delete(self, album_id: int) -> None:
        """Delete an album and all its associated records atomically."""
        now = _utc_now_iso()
        with self._db() as conn:
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
        self._log(
            {"timestamp": now, "action": "delete_album", "album_id": album_id, "success": True}
        )


# ---------------------------------------------------------------------------
# WorkspaceAlbumService
# ---------------------------------------------------------------------------

class WorkspaceAlbumService:
    """Workflow and field-validation owner for workspace album operations."""

    ALLOWED_BATCH_FIELDS: frozenset[str] = frozenset({
        "status_id", "studio_name", "album_name", "primary_model",
        "additional_models", "remark", "expected_path", "ai_result",
        "belongs_to_album_id", "album_id",
    })

    ALLOWED_UPDATE_FIELDS: frozenset[str] = frozenset({
        "current_path", "expected_path", "primary_model", "studio_name",
        "album_name", "additional_models", "status_id", "remark",
        "belongs_to_album_id", "ai_result", "album_id",
    })

    def __init__(self, db_factory, snapshot_fn, backup_log_fn):
        self._db = db_factory
        self._snapshot = snapshot_fn
        self._backup_log = backup_log_fn

    def batch_update(self, ids: list, changes: dict) -> int:
        """Apply an allowed subset of changes to multiple workspace albums.

        Takes a pre-write snapshot before applying any changes.

        Returns:
            The number of rows updated.

        Raises:
            ValueError: If ``changes`` contains no allowed fields.
        """
        filtered = {k: v for k, v in changes.items() if k in self.ALLOWED_BATCH_FIELDS}
        if not filtered:
            raise ValueError("No valid fields to update were supplied.")

        now = _utc_now_iso()
        try:
            snap = self._snapshot("workspace_batch")
            self._backup_log(
                {"timestamp": now, "reason": "workspace_batch", "ok": True, "snapshot": str(snap), "tag": ""}
            )
        except Exception as ex:
            self._backup_log(
                {"timestamp": now, "reason": "workspace_batch", "ok": False, "error": str(ex), "tag": ""}
            )

        set_clauses = ", ".join(f"{k} = ?" for k in filtered)
        set_values = list(filtered.values())
        updated = 0
        with self._db() as conn:
            for wa_id in ids:
                conn.execute(
                    f"UPDATE workspace_album SET {set_clauses} WHERE id = ?",
                    set_values + [wa_id],
                )
                updated += 1
            conn.commit()
        return updated

    def update(self, wa_id: int, changes: dict) -> None:
        """Apply an allowed subset of changes to a single workspace album.

        Raises:
            ValueError: If ``changes`` contains no allowed fields.
        """
        filtered = {k: v for k, v in changes.items() if k in self.ALLOWED_UPDATE_FIELDS}
        if not filtered:
            raise ValueError("No valid fields to update were supplied.")
        set_clauses = ", ".join(f"{k} = ?" for k in filtered)
        set_values = list(filtered.values())
        with self._db() as conn:
            conn.execute(
                f"UPDATE workspace_album SET {set_clauses} WHERE id = ?",
                set_values + [wa_id],
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Import path helpers (pure functions, no I/O)
# ---------------------------------------------------------------------------

_ALBUM_FOLDER_RE = re.compile(r"^(.+?)\s+in\s+(.+)$", re.IGNORECASE)


def parse_album_folder_name(folder_name: str) -> tuple[str, str]:
    """Split ``"Model in Studio"`` folder names into ``(model, studio)``.

    Returns:
        A ``(model_name, album_name)`` tuple. Both elements are empty strings
        when the pattern is not matched.
    """
    m = _ALBUM_FOLDER_RE.match(folder_name.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", folder_name.strip()


def alphabet_for_model(model_name: str) -> str:
    """Return the single-letter (or ``"0-9"`` / ``"_"``) archive bucket."""
    if not model_name:
        return "_"
    first = model_name[0]
    if first.isalpha():
        return first.upper()
    if first.isdigit():
        return "0-9"
    return "_"


def build_archive_path(model_name: str, studio_name: str, album_name: str) -> str:
    """Build the relative archive path for an album."""
    alpha = alphabet_for_model(model_name)
    return f"{alpha}/{model_name}/p/{studio_name}/{album_name}"


# ---------------------------------------------------------------------------
# ImportService
# ---------------------------------------------------------------------------

class ImportService:
    """Workflow owner for album import preview and execution."""

    def __init__(self, db_factory, snapshot_fn, backup_log_fn, change_log_fn):
        self._db = db_factory
        self._snapshot = snapshot_fn
        self._backup_log = backup_log_fn
        self._change_log = change_log_fn

    def preview(
        self, items: list, archive_root: str, default_studio: str
    ) -> dict:
        """Build an import preview for the supplied candidate items.

        Returns a dict with ``items`` (per-candidate outcome) and ``summary``
        (total / importable / skipped counts).
        """
        preview_items = []
        for item in items:
            folder_name = item.get("folder_name", "")
            studio_name = item.get("studio_name") or default_studio
            model_name = item.get("model_name", "")
            album_name = item.get("album_name", "")

            if not model_name and not album_name and folder_name:
                model_name, album_name = parse_album_folder_name(folder_name)

            expected_path = build_archive_path(model_name, studio_name, album_name)
            full_path = Path(archive_root) / expected_path

            with self._db() as conn:
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
        return {
            "items": preview_items,
            "summary": {
                "total": total,
                "importable": importable,
                "skipped": total - importable,
            },
        }

    def execute(
        self, items: list, archive_root: str, default_studio: str
    ) -> dict:
        """Execute the import for the supplied items.

        Takes a pre-import snapshot, then processes each item: finds or creates
        the studio and model, skips albums that already exist, creates the album
        record and album_model link, and copies files when a source path is
        provided.

        Returns a dict with ``results`` (per-item outcome) and ``summary``
        (total / created / skipped / errors counts).
        """
        now = _utc_now_iso()
        try:
            snap = self._snapshot("import")
            self._backup_log(
                {"timestamp": now, "reason": "import", "ok": True, "snapshot": str(snap), "tag": ""}
            )
        except Exception as ex:
            self._backup_log(
                {"timestamp": now, "reason": "import", "ok": False, "error": str(ex), "tag": ""}
            )

        results = []
        created_albums = 0
        skipped = 0
        errors = 0

        for item in items:
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
                item_now = _utc_now_iso()
                with self._db() as conn:
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
                            (new_uuid, studio_name, item_now, item_now),
                        )
                        studio_id = cur.lastrowid

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
                            (new_uuid, model_name, item_now, item_now),
                        )
                        model_id = cur.lastrowid

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

                    new_uuid = str(uuid.uuid4())
                    cur = conn.execute(
                        """
                        INSERT INTO album (uuid, studio_id, title, path, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (new_uuid, studio_id, album_name, expected_path, item_now, item_now),
                    )
                    album_id = cur.lastrowid
                    conn.execute(
                        "INSERT INTO album_model (album_id, model_id) VALUES (?, ?)",
                        (album_id, model_id),
                    )
                    conn.commit()

                if source_path and Path(source_path).exists():
                    full_dest.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(source_path, str(full_dest), dirs_exist_ok=True)

                result["ok"] = True
                result["album_id"] = album_id
                created_albums += 1
                self._change_log(
                    {
                        "timestamp": item_now,
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

        return {
            "results": results,
            "summary": {
                "total": len(items),
                "created": created_albums,
                "skipped": skipped,
                "errors": errors,
            },
        }


# ---------------------------------------------------------------------------
# BackupService
# ---------------------------------------------------------------------------

def _parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime string, defaulting to UTC when unaware."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _find_snapshot_by_tag(catalog: list, tag: str) -> dict | None:
    for item in catalog:
        if item.get("tag") == tag:
            return item
    return None


def _find_snapshot_before_or_at(catalog: list, target_dt: datetime) -> dict | None:
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)
    candidates = [
        x for x in catalog
        if x.get("_created_at_dt") is not None and x["_created_at_dt"] <= target_dt
    ]
    if not candidates:
        return None
    return candidates[0]  # catalog is already sorted newest-first


class BackupService:
    """Workflow owner for snapshot creation, cleanup, and rollback operations.

    All snapshot-creation and restore decisions belong here; handlers only
    translate the outcome to HTTP.
    """

    def __init__(
        self,
        snapshot_fn,
        restore_fn,
        backup_log_fn,
        rollback_log_fn,
        catalog_fn,
        last_change_fn,
        public_item_fn,
        parse_tag_fn,
        cleanup_fn=None,
    ):
        self._snapshot = snapshot_fn
        self._restore = restore_fn
        self._backup_log = backup_log_fn
        self._rollback_log = rollback_log_fn
        self._catalog = catalog_fn
        self._last_change = last_change_fn
        self._public_item = public_item_fn
        self._parse_tag = parse_tag_fn
        self._cleanup = cleanup_fn

    def create(self, reason: str, tag: str = "") -> dict:
        """Create a named snapshot and log the outcome.

        Returns:
            A dict with ``snapshot`` (path string) and ``filename``.

        Raises:
            Exception: If the snapshot operation fails (caller maps to 500).
        """
        snap = self._snapshot(reason, tag)
        entry = {
            "timestamp": _utc_now_iso(),
            "reason": reason,
            "ok": True,
            "snapshot": str(snap),
            "tag": tag,
        }
        self._backup_log(entry)
        return {"snapshot": str(snap), "filename": snap.name}

    def create_failed(self, reason: str, tag: str, error: Exception) -> None:
        """Log a failed snapshot attempt."""
        self._backup_log(
            {
                "timestamp": _utc_now_iso(),
                "reason": reason,
                "ok": False,
                "error": str(error),
                "tag": tag,
            }
        )

    def cleanup(self, retention_days: int) -> dict:
        """Delegate to the injected cleanup callable and return its result."""
        if self._cleanup is None:
            raise RuntimeError("No cleanup function was provided to BackupService.")
        return self._cleanup(retention_days)

    def rollback(self, mode: str, body: dict) -> dict:
        """Execute a rollback operation in the requested mode.

        Modes
        -----
        ``"snapshot"``
            Roll back to the explicitly specified snapshot path.
        ``"tag"``
            Roll back to the most recent snapshot with the given tag.
        ``"before_last_operation"``
            Roll back to the snapshot taken just before the last recorded
            successful change.

        Returns:
            A dict with ``selected_snapshot`` (public item shape).

        Raises:
            ValueError: If the mode or a required body field is invalid.
            ServiceNotFound: If the required snapshot cannot be located.
            Exception: If the restore operation itself fails.
        """
        catalog = self._catalog()
        selected = None

        if mode == "snapshot":
            snap_path_str = body.get("snapshot", "")
            if not snap_path_str:
                raise ValueError("The 'snapshot' path is required.")
            snap_path = Path(snap_path_str)
            if not snap_path.exists():
                raise ServiceNotFound("The specified snapshot was not found.")
            for item in catalog:
                if Path(item["path"]).resolve() == snap_path.resolve():
                    selected = item
                    break
            if selected is None:
                selected = {
                    "path": str(snap_path),
                    "filename": snap_path.name,
                    "tag": self._parse_tag(snap_path),
                    "created_at": None,
                }

        elif mode == "tag":
            tag = body.get("tag", "").strip()
            if not tag:
                raise ValueError("The 'tag' field is required.")
            selected = _find_snapshot_by_tag(catalog, tag)
            if selected is None:
                raise ServiceNotFound("No snapshot found with the specified tag.")

        elif mode == "before_last_operation":
            last_entry = self._last_change()
            if last_entry is None:
                raise ServiceNotFound("No successful change entry was found.")
            ts_str = last_entry.get("timestamp", "")
            try:
                target_dt = _parse_iso_datetime(ts_str)
            except Exception:
                raise ValueError(
                    "The timestamp from the last change entry could not be parsed."
                )
            selected = _find_snapshot_before_or_at(catalog, target_dt)
            if selected is None:
                raise ServiceNotFound(
                    "No snapshot was found before the last operation."
                )

        else:
            raise ValueError("The rollback mode is not recognised.")

        snap_path = Path(selected["path"])
        if not snap_path.exists():
            raise ServiceNotFound("The snapshot file no longer exists.")

        # Create a safety pre-rollback snapshot before restoring.
        now = _utc_now_iso()
        try:
            safety = self._snapshot("pre_rollback")
            self._backup_log(
                {
                    "timestamp": now,
                    "reason": "pre_rollback",
                    "ok": True,
                    "snapshot": str(safety),
                    "tag": "",
                }
            )
        except Exception as ex:
            self._backup_log(
                {
                    "timestamp": now,
                    "reason": "pre_rollback",
                    "ok": False,
                    "error": str(ex),
                    "tag": "",
                }
            )

        try:
            self._restore(snap_path)
        except Exception as ex:
            self._rollback_log(
                {
                    "timestamp": _utc_now_iso(),
                    "mode": mode,
                    "snapshot": str(snap_path),
                    "ok": False,
                    "error": str(ex),
                }
            )
            raise

        self._rollback_log(
            {
                "timestamp": _utc_now_iso(),
                "mode": mode,
                "snapshot": str(snap_path),
                "ok": True,
            }
        )
        return {"selected_snapshot": self._public_item(selected)}
