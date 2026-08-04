#!/usr/bin/env python3
"""Application service layer for Curator Backend.

Services own business rules, workflow decisions, and transaction boundaries.
They are independent of HTTP and called by transport adapters (AppHandler).

Each service accepts its repository dependencies at construction time so they
can be tested in isolation without HTTP machinery or a real database.

Persistence is performed exclusively through repository methods; services
contain no SQL or direct database-connection handling.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import canonical_path as cpath
import repositories as repo


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

    def __init__(self, status_repo: repo.StatusRepository):
        self._repo = status_repo

    def delete(self, status_id: int) -> None:
        """Delete a status after verifying it has no references.

        Raises:
            ServiceConflict: If any album or workspace album references the
                status.
        """
        try:
            self._repo.delete(status_id)
        except repo.PersistenceConflict as exc:
            raise ServiceConflict(
                "BUSINESS_CONFLICT",
                "The status is still referenced and cannot be deleted.",
                exc.details,
            )


# ---------------------------------------------------------------------------
# ModelService
# ---------------------------------------------------------------------------

class ModelService:
    """Business rules for model management."""

    def __init__(self, model_repo: repo.ModelRepository, log_fn=None):
        self._repo = model_repo
        self._log = log_fn or (lambda _: None)

    def update_fields(self, model_id: int, data: dict) -> dict:
        """Update model fields and return the refreshed record.

        Raises:
            ServiceNotFound: If no model with ``model_id`` exists.
        """
        now = _utc_now_iso()
        result = self._repo.update_fields(model_id, data, now)
        if result is None:
            raise ServiceNotFound("Model not found.")
        self._log(
            {"timestamp": now, "action": "update_model", "model_id": model_id, "success": True}
        )
        return result

    def delete(self, model_id: int) -> None:
        """Delete a model after verifying it has no album references.

        Raises:
            ServiceConflict: If the model is referenced by any album.
        """
        try:
            self._repo.delete(model_id)
        except repo.PersistenceConflict as exc:
            raise ServiceConflict(
                "BUSINESS_CONFLICT",
                "The model is still referenced by albums and cannot be deleted.",
                exc.details,
            )


# ---------------------------------------------------------------------------
# StudioService
# ---------------------------------------------------------------------------

class StudioService:
    """Business rules for studio management."""

    def __init__(self, studio_repo: repo.StudioRepository):
        self._repo = studio_repo

    def delete(self, studio_id: int) -> None:
        """Delete a studio after verifying it has no album references.

        Raises:
            ServiceConflict: If any album references the studio.
        """
        try:
            self._repo.delete(studio_id)
        except repo.PersistenceConflict as exc:
            raise ServiceConflict(
                "BUSINESS_CONFLICT",
                "The studio is still referenced by albums and cannot be deleted.",
                exc.details,
            )


# ---------------------------------------------------------------------------
# AlbumService
# ---------------------------------------------------------------------------

class AlbumService:
    """Workflow owner for album create, update, and delete operations.

    Owns audit log writes for material album changes; delegates all
    persistence to AlbumRepository.
    """

    def __init__(self, album_repo: repo.AlbumRepository, log_fn):
        self._repo = album_repo
        self._log = log_fn

    def create(self, data: dict, models: list, relations: list) -> int:
        """Create an album with associated models and relations atomically.

        Returns:
            The new album's integer id.
        """
        now = _utc_now_iso()
        album_id = self._repo.create(data, models, relations, now)
        self._log(
            {"timestamp": now, "action": "create_album", "album_id": album_id, "success": True}
        )
        return album_id

    def update(
        self, album_id: int, data: dict, models: list, relations: list
    ) -> None:
        """Replace album fields, model list, and relation list atomically."""
        now = _utc_now_iso()
        self._repo.update(album_id, data, models, relations, now)
        self._log(
            {"timestamp": now, "action": "update_album", "album_id": album_id, "success": True}
        )

    def delete(self, album_id: int) -> None:
        """Delete an album and all its associated records atomically."""
        now = _utc_now_iso()
        self._repo.delete(album_id)
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

    def __init__(
        self,
        workspace_repo: repo.WorkspaceAlbumRepository,
        snapshot_fn,
        backup_log_fn,
    ):
        self._repo = workspace_repo
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

        return self._repo.batch_update(ids, self.ALLOWED_BATCH_FIELDS, changes)

    def update(self, wa_id: int, changes: dict) -> None:
        """Apply an allowed subset of changes to a single workspace album.

        Raises:
            ValueError: If ``changes`` contains no allowed fields.
        """
        self._repo.update(wa_id, self.ALLOWED_UPDATE_FIELDS, changes)


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
    """Return the single-letter (or ``"0-9"`` / ``"_"``) archive bucket.

    Delegates to :func:`canonical_path.alphabet_for_model`. Kept here for
    backward compatibility; new callers should use the canonical_path module
    directly.
    """
    return cpath.alphabet_for_model(cpath.canonicalize_component(model_name))


def build_archive_path(model_name: str, studio_name: str, album_name: str) -> str:
    """Build the canonical relative archive path for an album.

    Delegates to :func:`canonical_path.build_canonical_path`, which applies
    per-component whitespace trimming, Unicode NFC normalization, and the
    archive bucket derivation rule.
    """
    return cpath.build_canonical_path(model_name, studio_name, album_name)


# ---------------------------------------------------------------------------
# ImportService
# ---------------------------------------------------------------------------

class ImportService:
    """Workflow owner for album import preview and execution."""

    def __init__(
        self,
        import_repo: repo.ImportRepository,
        snapshot_fn,
        backup_log_fn,
        change_log_fn,
    ):
        self._repo = import_repo
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

            model_name = cpath.canonicalize_component(model_name)
            studio_name = cpath.canonicalize_component(studio_name)
            album_name = cpath.canonicalize_component(album_name)
            expected_path = build_archive_path(model_name, studio_name, album_name)
            full_path = Path(archive_root) / expected_path

            lookup = self._repo.lookup_preview_item(studio_name, model_name, album_name)
            path_exists = full_path.exists()
            can_import = not lookup["album_exists"] and not path_exists

            preview_items.append(
                {
                    "folder_name": folder_name,
                    "model_name": model_name,
                    "album_name": album_name,
                    "studio_name": studio_name,
                    "expected_path": expected_path,
                    "source_path": item.get("source_path", ""),
                    "model_exists": lookup["model_exists"],
                    "model_id": lookup["model_id"],
                    "studio_exists": lookup["studio_exists"],
                    "studio_id": lookup["studio_id"],
                    "album_exists": lookup["album_exists"],
                    "album_id": lookup["album_id"],
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

            model_name = cpath.canonicalize_component(model_name)
            studio_name = cpath.canonicalize_component(studio_name)
            album_name = cpath.canonicalize_component(album_name)
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
                item_result = self._repo.create_item(
                    studio_name, model_name, album_name, expected_path, item_now
                )
                album_id = item_result["album_id"]

                if item_result["status"] == "skipped":
                    result["skipped"] = True
                    result["album_id"] = album_id
                    skipped += 1
                    results.append(result)
                    continue

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
