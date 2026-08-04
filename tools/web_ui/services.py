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
import uuid as _uuid_mod
from datetime import datetime, timezone
from pathlib import Path

import canonical_path as cpath
import repositories as repo

# Import Action constants — passed by callers to ImportService.execute().
IMPORT_ACTION_DATABASE_ONLY: str = "DATABASE_ONLY"
IMPORT_ACTION_COPY: str = "COPY"
IMPORT_ACTION_MOVE: str = "MOVE"


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


# Lifecycle state labels as module-level constants so callers can reference
# them without importing magic strings.
LIFECYCLE_ACTIVE: str = "active"
LIFECYCLE_REVIEW: str = "review"
LIFECYCLE_CLOSED: str = "closed"
LIFECYCLE_ARCHIVED_RETIRED: str = "archived_retired"

# Allowed forward and backward transitions: {from_state: frozenset(to_states)}
_LIFECYCLE_TRANSITIONS: dict[str, frozenset[str]] = {
    LIFECYCLE_ACTIVE: frozenset({LIFECYCLE_REVIEW}),
    LIFECYCLE_REVIEW: frozenset({LIFECYCLE_ACTIVE, LIFECYCLE_CLOSED}),
    LIFECYCLE_CLOSED: frozenset({LIFECYCLE_ARCHIVED_RETIRED}),
    LIFECYCLE_ARCHIVED_RETIRED: frozenset(),
}


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

    ALLOWED_CREATE_FIELDS: frozenset[str] = frozenset({
        "studio_name", "album_name", "primary_model", "additional_models",
        "status_id", "remark", "current_path", "expected_path", "ai_result",
        "belongs_to_album_id", "album_id",
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

    def create(self, fields: dict) -> dict:
        """Create a new workspace album with initial lifecycle_state ``'active'``.

        Only fields in :attr:`ALLOWED_CREATE_FIELDS` are forwarded to the
        repository; ``lifecycle_state`` is always set to ``'active'`` by the
        repository, not by callers.

        Returns:
            The normalized workspace album read model for the new record.
        """
        filtered = {k: v for k, v in fields.items() if k in self.ALLOWED_CREATE_FIELDS}
        return self._repo.create(filtered)

    def _transition(self, wa_id: int, to_state: str) -> None:
        """Validate the requested lifecycle transition and persist it.

        Args:
            wa_id: Integer primary key of the target workspace album.
            to_state: Lifecycle state string to transition to.

        Raises:
            ServiceNotFound: When no workspace album with ``wa_id`` exists.
            ServiceConflict: When the requested transition is not permitted
                from the workspace album's current lifecycle state.
        """
        current = self._repo.get_lifecycle_state(wa_id)
        if current is None:
            raise ServiceNotFound(
                f"Workspace album {wa_id} not found."
            )
        allowed_targets = _LIFECYCLE_TRANSITIONS.get(current, frozenset())
        if to_state not in allowed_targets:
            raise ServiceConflict(
                "BUSINESS_CONFLICT",
                (
                    f"Cannot transition workspace album {wa_id} "
                    f"from '{current}' to '{to_state}'."
                ),
                {"current_state": current, "requested_state": to_state},
            )
        self._repo.set_lifecycle_state(wa_id, to_state)

    def submit_for_review(self, wa_id: int) -> None:
        """Transition a workspace album from ``active`` to ``review``.

        Raises:
            ServiceNotFound: When the workspace album does not exist.
            ServiceConflict: When the current state is not ``active``.
        """
        self._transition(wa_id, LIFECYCLE_REVIEW)

    def return_to_active(self, wa_id: int) -> None:
        """Transition a workspace album from ``review`` back to ``active``.

        Raises:
            ServiceNotFound: When the workspace album does not exist.
            ServiceConflict: When the current state is not ``review``.
        """
        self._transition(wa_id, LIFECYCLE_ACTIVE)

    def close(self, wa_id: int) -> None:
        """Transition a workspace album from ``review`` to ``closed``.

        Raises:
            ServiceNotFound: When the workspace album does not exist.
            ServiceConflict: When the current state is not ``review``.
        """
        self._transition(wa_id, LIFECYCLE_CLOSED)

    def archive(self, wa_id: int) -> None:
        """Transition a workspace album from ``closed`` to ``archived_retired``.

        Raises:
            ServiceNotFound: When the workspace album does not exist.
            ServiceConflict: When the current state is not ``closed``.
        """
        self._transition(wa_id, LIFECYCLE_ARCHIVED_RETIRED)


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
        """Build a deterministic import preview for the supplied candidate items.

        Normalizes each candidate's path components, detects within-batch
        canonical-path duplicates, and checks for database and filesystem
        collisions — all without mutating any persistent state.

        Each item in the returned ``items`` list includes a ``validation_errors``
        field containing zero or more structured error dicts, each with a stable
        machine-readable ``code`` and a human-readable ``message``. The
        ``can_import`` flag is ``True`` only when ``validation_errors`` is empty.

        Validation error codes:
        - ``DUPLICATE_IN_BATCH``: Two or more items in this batch share the
          same canonical path comparison key.
        - ``ALBUM_EXISTS``: An album with a matching title already exists in
          the studio in the database.
        - ``PATH_EXISTS``: The target filesystem path already exists.
        - ``PATH_COLLISION``: Another album in the database already occupies
          the same canonical path (caught via ``album.path`` comparison key).

        Returns a dict with ``items`` (per-candidate outcome) and ``summary``
        (total / importable / skipped counts).
        """
        # ---------------------------------------------------------------
        # Pass 1 — normalize all candidates, compute comparison keys.
        # ---------------------------------------------------------------
        normalized: list[dict] = []
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
            ck = cpath.comparison_key(expected_path)

            normalized.append(
                {
                    "folder_name": folder_name,
                    "model_name": model_name,
                    "album_name": album_name,
                    "studio_name": studio_name,
                    "expected_path": expected_path,
                    "source_path": item.get("source_path", ""),
                    "_ck": ck,
                    "validation_errors": [],
                }
            )

        # Locate all within-batch canonical-path duplicates.
        ck_indices: dict[str, list[int]] = {}
        for i, n in enumerate(normalized):
            ck_indices.setdefault(n["_ck"], []).append(i)
        batch_duplicate_indices: set[int] = set()
        for indices in ck_indices.values():
            if len(indices) > 1:
                batch_duplicate_indices.update(indices)

        # ---------------------------------------------------------------
        # Pass 2 — run lookups and assemble per-item validation outcomes.
        # ---------------------------------------------------------------
        preview_items: list[dict] = []
        for i, n in enumerate(normalized):
            ck = n.pop("_ck")
            errors: list[dict] = n["validation_errors"]

            if i in batch_duplicate_indices:
                errors.append(
                    {
                        "code": "DUPLICATE_IN_BATCH",
                        "message": (
                            "Multiple items in this import batch share the "
                            "same canonical path."
                        ),
                    }
                )

            lookup = self._repo.lookup_preview_item(
                n["studio_name"], n["model_name"], n["album_name"]
            )
            if lookup["album_exists"]:
                errors.append(
                    {
                        "code": "ALBUM_EXISTS",
                        "message": (
                            "An album with this name already exists in the studio."
                        ),
                    }
                )
            elif self._repo.lookup_path_collision(ck):
                errors.append(
                    {
                        "code": "PATH_COLLISION",
                        "message": (
                            "Another album in the database already occupies "
                            "the same canonical path."
                        ),
                    }
                )

            full_path = Path(archive_root) / n["expected_path"]
            path_exists = full_path.exists()
            if path_exists:
                errors.append(
                    {
                        "code": "PATH_EXISTS",
                        "message": (
                            f"The target filesystem path already exists: "
                            f"{n['expected_path']}"
                        ),
                    }
                )

            preview_items.append(
                {
                    **n,
                    "model_exists": lookup["model_exists"],
                    "model_id": lookup["model_id"],
                    "studio_exists": lookup["studio_exists"],
                    "studio_id": lookup["studio_id"],
                    "album_exists": lookup["album_exists"],
                    "album_id": lookup["album_id"],
                    "path_exists": path_exists,
                    "can_import": not errors,
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
        self,
        items: list,
        archive_root: str,
        default_studio: str,
        import_action: str = IMPORT_ACTION_MOVE,
    ) -> dict:
        """Execute the import for the supplied items.

        Execution stages per item
        -------------------------
        1. Normalize path components and derive the canonical destination path.
        2. Write the Album, Studio, and Model records to the database atomically
           via the repository.
        3. Determine the effective Import Action:
           - When the source directory is already located at the canonical
             destination, the workflow automatically uses ``DATABASE_ONLY``
             regardless of the requested action.
           - Otherwise, the caller-supplied *import_action* governs the
             filesystem step: ``COPY`` copies the source tree; ``MOVE`` moves
             it; ``DATABASE_ONLY`` skips any filesystem work.
        4. Execute the filesystem step (or skip it for ``DATABASE_ONLY``).
           If persistence succeeded but the filesystem step fails, the item is
           recorded as ``needs_repair=True`` so the Repair Workflow can resolve
           the inconsistency. The persisted database record is **not** deleted.

        Parameters
        ----------
        items:
            List of import candidate dicts. Each may include ``folder_name``,
            ``model_name``, ``album_name``, ``studio_name``, and
            ``source_path``.
        archive_root:
            Absolute root path of the managed archive.
        default_studio:
            Studio name used when an item does not supply one.
        import_action:
            The filesystem action to apply: ``"COPY"``, ``"MOVE"`` (default),
            or ``"DATABASE_ONLY"``.

        Returns
        -------
        dict
            ``{results: [...], summary: {...}, import_uuid: "..."}``

            Per-item result fields include ``ok``, ``skipped``,
            ``needs_repair``, ``effective_action``, ``error``, and
            ``album_id``.  Summary counts are ``total``, ``created``,
            ``skipped``, ``errors``, and ``needs_repair``.
        """
        import_uuid = str(_uuid_mod.uuid4())
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
        needs_repair_count = 0

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
                "needs_repair": False,
                "effective_action": None,
                "error": None,
            }

            try:
                item_now = _utc_now_iso()
                item_result = self._repo.create_item(
                    studio_name, model_name, album_name, expected_path, item_now
                )
                album_id = item_result["album_id"]
                result["album_id"] = album_id

                if item_result["status"] == "skipped":
                    result["skipped"] = True
                    result["effective_action"] = IMPORT_ACTION_DATABASE_ONLY
                    skipped += 1
                    results.append(result)
                    continue

                # ----------------------------------------------------------
                # Determine effective Import Action.
                # If the source is already at the canonical destination, use
                # DATABASE_ONLY automatically regardless of the requested action.
                # ----------------------------------------------------------
                src = Path(source_path) if source_path else None
                if src and src.resolve() == full_dest.resolve():
                    effective_action = IMPORT_ACTION_DATABASE_ONLY
                else:
                    effective_action = import_action

                result["effective_action"] = effective_action

                # ----------------------------------------------------------
                # Filesystem stage.  Any exception here means DB succeeded
                # but filesystem is inconsistent → NeedsRepair.
                # ----------------------------------------------------------
                try:
                    if effective_action == IMPORT_ACTION_COPY:
                        if src is None:
                            pass  # No source given — metadata-only
                        elif not src.exists():
                            raise FileNotFoundError(
                                f"Source path does not exist: {source_path!r}"
                            )
                        else:
                            full_dest.mkdir(parents=True, exist_ok=True)
                            shutil.copytree(str(src), str(full_dest), dirs_exist_ok=True)
                    elif effective_action == IMPORT_ACTION_MOVE:
                        if src is None:
                            pass  # No source given — metadata-only
                        elif not src.exists():
                            raise FileNotFoundError(
                                f"Source path does not exist: {source_path!r}"
                            )
                        else:
                            full_dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(src), str(full_dest))
                    # DATABASE_ONLY: no filesystem work
                except Exception as fs_ex:
                    # Persistence succeeded; filesystem step failed.
                    # Record NeedsRepair without deleting the DB record.
                    result["needs_repair"] = True
                    result["error"] = str(fs_ex)
                    needs_repair_count += 1
                    self._change_log(
                        {
                            "timestamp": item_now,
                            "action": "import_album",
                            "import_uuid": import_uuid,
                            "album_id": album_id,
                            "model_name": model_name,
                            "studio_name": studio_name,
                            "effective_action": effective_action,
                            "success": False,
                            "needs_repair": True,
                            "error": str(fs_ex),
                        }
                    )
                    results.append(result)
                    continue

                result["ok"] = True
                created_albums += 1
                self._change_log(
                    {
                        "timestamp": item_now,
                        "action": "import_album",
                        "import_uuid": import_uuid,
                        "album_id": album_id,
                        "model_name": model_name,
                        "studio_name": studio_name,
                        "effective_action": effective_action,
                        "success": True,
                        "needs_repair": False,
                    }
                )

            except Exception as ex:
                result["error"] = str(ex)
                errors += 1

            results.append(result)

        return {
            "import_uuid": import_uuid,
            "results": results,
            "summary": {
                "total": len(items),
                "created": created_albums,
                "skipped": skipped,
                "errors": errors,
                "needs_repair": needs_repair_count,
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


# ---------------------------------------------------------------------------
# Repair workflow state machine constants
# ---------------------------------------------------------------------------

REPAIR_STATE_NEEDS_REPAIR: str = "NeedsRepair"
REPAIR_STATE_REPAIRING: str = "Repairing"
REPAIR_STATE_PENDING_VERIFICATION: str = "PendingVerification"
REPAIR_STATE_RESOLVED: str = "Resolved"
REPAIR_STATE_MANUAL_CONFLICT: str = "ManualConflict"
REPAIR_STATE_IGNORED: str = "Ignored"

REPAIR_CATEGORY_AUTOMATIC: str = "Automatic"
REPAIR_CATEGORY_ASSISTED: str = "Assisted"
REPAIR_CATEGORY_MANUAL_CONFLICT: str = "ManualConflict"

_REPAIR_TRANSITIONS: dict[str, frozenset[str]] = {
    REPAIR_STATE_NEEDS_REPAIR: frozenset({
        REPAIR_STATE_REPAIRING,
        REPAIR_STATE_MANUAL_CONFLICT,
        REPAIR_STATE_IGNORED,
    }),
    REPAIR_STATE_REPAIRING: frozenset({
        REPAIR_STATE_PENDING_VERIFICATION,
    }),
    REPAIR_STATE_PENDING_VERIFICATION: frozenset({
        REPAIR_STATE_RESOLVED,
        REPAIR_STATE_NEEDS_REPAIR,
    }),
    REPAIR_STATE_RESOLVED: frozenset(),
    REPAIR_STATE_MANUAL_CONFLICT: frozenset({
        REPAIR_STATE_REPAIRING,
        REPAIR_STATE_IGNORED,
    }),
    REPAIR_STATE_IGNORED: frozenset(),
}

# Issue lifecycle constants
ISSUE_STATE_OPEN: str = "Open"
ISSUE_STATE_IN_PROGRESS: str = "InProgress"
ISSUE_STATE_RESOLVED: str = "Resolved"
ISSUE_STATE_ARCHIVED: str = "Archived"

_ISSUE_TRANSITIONS: dict[str, frozenset[str]] = {
    ISSUE_STATE_OPEN: frozenset({
        ISSUE_STATE_IN_PROGRESS,
        ISSUE_STATE_ARCHIVED,
    }),
    ISSUE_STATE_IN_PROGRESS: frozenset({
        ISSUE_STATE_OPEN,
        ISSUE_STATE_RESOLVED,
        ISSUE_STATE_ARCHIVED,
    }),
    ISSUE_STATE_RESOLVED: frozenset({
        ISSUE_STATE_ARCHIVED,
    }),
    ISSUE_STATE_ARCHIVED: frozenset(),
}


# ---------------------------------------------------------------------------
# RepairService
# ---------------------------------------------------------------------------

class RepairService:
    """Orchestrates the repair workflow state machine.

    Transitions (via :meth:`_transition`):
    - ``NeedsRepair``       → ``Repairing``, ``ManualConflict``, ``Ignored``
    - ``Repairing``         → ``PendingVerification``
    - ``PendingVerification`` → ``Resolved`` | ``NeedsRepair``
    - ``ManualConflict``    → ``Repairing``, ``Ignored``
    - ``Resolved``          (terminal)
    - ``Ignored``           (terminal)

    Automatic repairs require no confirmation.
    Assisted and ManualConflict repairs require :meth:`confirm` before
    :meth:`start_repair` will succeed.
    """

    def __init__(self, repair_repo, issue_repo):
        self._repair = repair_repo
        self._issue = issue_repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        operation_uuid: str | None,
        album_uuid: str | None,
        expected_path: str | None,
        category: str = REPAIR_CATEGORY_ASSISTED,
        failure_reason: str | None = None,
        issue_fields: dict | None = None,
    ) -> dict:
        """Register a new repair case in state ``NeedsRepair``.

        Also creates a linked Issue in state ``Open`` describing the problem.

        Args:
            operation_uuid: UUID of the import/other operation that triggered
                the repair need.
            album_uuid: UUID of the affected album (may be ``None`` if unknown).
            expected_path: Canonical path the album should occupy.
            category: One of ``'Automatic'``, ``'Assisted'``,
                ``'ManualConflict'``.  Defaults to ``'Assisted'``.
            failure_reason: Short description of what went wrong.
            issue_fields: Extra fields to merge into the linked Issue record.

        Returns:
            ``{'repair': <repair_case dict>, 'issue': <issue dict>}``
        """
        repair = self._repair.create(
            {
                "operation_uuid": operation_uuid,
                "album_uuid": album_uuid,
                "expected_path": expected_path,
                "category": category,
                "failure_reason": failure_reason,
            }
        )
        base_issue = {
            "category": "Repair",
            "description": failure_reason or "Repair case detected",
            "affected_operation": operation_uuid,
            "suggested_resolution": "Review the repair case and select an action",
            "source_workflow": "RepairService",
        }
        if issue_fields:
            base_issue.update(issue_fields)
        issue = self._issue.create(base_issue)
        return {"repair": repair, "issue": issue}

    def confirm(self, repair_uuid: str, confirmation: str) -> dict:
        """Record confirmation text for an Assisted or ManualConflict repair.

        Required before :meth:`start_repair` for non-Automatic categories.

        Args:
            repair_uuid: UUID of the repair case.
            confirmation: Free-text confirmation provided by the user.

        Returns:
            Updated repair case dict.

        Raises:
            ServiceNotFound: When *repair_uuid* does not exist.
        """
        repair = self._repair.get_by_uuid(repair_uuid)
        if repair is None:
            raise ServiceNotFound(f"Repair case not found: {repair_uuid}")
        self._repair.set_confirmation(repair_uuid, confirmation)
        return self._repair.get_by_uuid(repair_uuid)

    def start_repair(self, repair_uuid: str) -> dict:
        """Transition a repair case from ``NeedsRepair`` or ``ManualConflict``
        to ``Repairing``.

        Automatic repairs may start without confirmation.  Assisted and
        ManualConflict repairs require a non-empty :meth:`confirm` value first.

        Args:
            repair_uuid: UUID of the repair case.

        Returns:
            Updated repair case dict.

        Raises:
            ServiceNotFound: When *repair_uuid* does not exist.
            ServiceConflict: When confirmation is required but missing, or the
                transition is not permitted.
        """
        repair = self._repair.get_by_uuid(repair_uuid)
        if repair is None:
            raise ServiceNotFound(f"Repair case not found: {repair_uuid}")
        if repair["category"] != REPAIR_CATEGORY_AUTOMATIC:
            if not repair.get("confirmation"):
                raise ServiceConflict(
                    "CONFIRMATION_REQUIRED",
                    f"Repair {repair_uuid} ({repair['category']}) requires confirmation before starting.",
                    {"repair_uuid": repair_uuid, "category": repair["category"]},
                )
        return self._transition(repair_uuid, REPAIR_STATE_REPAIRING)

    def escalate_to_manual(self, repair_uuid: str) -> dict:
        """Transition ``NeedsRepair`` → ``ManualConflict``.

        Used when no safe automatic resolution can be determined.

        Args:
            repair_uuid: UUID of the repair case.

        Returns:
            Updated repair case dict.

        Raises:
            ServiceNotFound: When *repair_uuid* does not exist.
            ServiceConflict: When the transition is not permitted.
        """
        return self._transition(repair_uuid, REPAIR_STATE_MANUAL_CONFLICT)

    def complete_action(self, repair_uuid: str) -> dict:
        """Transition ``Repairing`` → ``PendingVerification``.

        Called once the repair action (file move / rename / DB update) is done.

        Args:
            repair_uuid: UUID of the repair case.

        Returns:
            Updated repair case dict.

        Raises:
            ServiceNotFound: When *repair_uuid* does not exist.
            ServiceConflict: When the transition is not permitted.
        """
        return self._transition(repair_uuid, REPAIR_STATE_PENDING_VERIFICATION)

    def verify(self, repair_uuid: str, passed: bool, result: str | None = None) -> dict:
        """Transition ``PendingVerification`` → ``Resolved`` or back to
        ``NeedsRepair`` when validation fails.

        Args:
            repair_uuid: UUID of the repair case.
            passed: ``True`` → ``Resolved``; ``False`` → ``NeedsRepair``.
            result: Optional textual verification result to persist.

        Returns:
            Updated repair case dict.

        Raises:
            ServiceNotFound: When *repair_uuid* does not exist.
            ServiceConflict: When the transition is not permitted.
        """
        if result is not None:
            self._repair.set_verification_result(repair_uuid, result)
        target = REPAIR_STATE_RESOLVED if passed else REPAIR_STATE_NEEDS_REPAIR
        return self._transition(repair_uuid, target)

    def ignore(self, repair_uuid: str) -> dict:
        """Transition ``NeedsRepair`` or ``ManualConflict`` → ``Ignored``.

        Records an explicit decision to skip remediation.

        Args:
            repair_uuid: UUID of the repair case.

        Returns:
            Updated repair case dict.

        Raises:
            ServiceNotFound: When *repair_uuid* does not exist.
            ServiceConflict: When the transition is not permitted.
        """
        return self._transition(repair_uuid, REPAIR_STATE_IGNORED)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _transition(self, repair_uuid: str, to_state: str) -> dict:
        """Validate and apply a state transition.

        Raises:
            ServiceNotFound: When *repair_uuid* does not exist.
            ServiceConflict: When *to_state* is not reachable from the current
                state.
        """
        repair = self._repair.get_by_uuid(repair_uuid)
        if repair is None:
            raise ServiceNotFound(f"Repair case not found: {repair_uuid}")
        from_state = repair["state"]
        allowed = _REPAIR_TRANSITIONS.get(from_state, frozenset())
        if to_state not in allowed:
            raise ServiceConflict(
                "INVALID_TRANSITION",
                f"Cannot transition repair {repair_uuid} from '{from_state}' to '{to_state}'.",
                {"from": from_state, "to": to_state, "allowed": sorted(allowed)},
            )
        self._repair.set_state(repair_uuid, to_state)
        return self._repair.get_by_uuid(repair_uuid)


# ---------------------------------------------------------------------------
# IssueService
# ---------------------------------------------------------------------------

class IssueService:
    """Orchestrates the issue management lifecycle.

    Transitions:
    - ``Open``        → ``InProgress``, ``Archived``
    - ``InProgress``  → ``Open``, ``Resolved``, ``Archived``
    - ``Resolved``    → ``Archived``
    - ``Archived``    (terminal)
    """

    def __init__(self, issue_repo):
        self._issue = issue_repo

    def create(self, fields: dict) -> dict:
        """Create a new issue in state ``Open``.

        Args:
            fields: Must include ``category``, ``description``, and
                ``source_workflow``; all other columns are optional.

        Returns:
            Normalised issue dict.
        """
        fields = dict(fields)
        fields.setdefault("state", ISSUE_STATE_OPEN)
        return self._issue.create(fields)

    def begin_work(self, issue_uuid: str) -> dict:
        """Transition ``Open`` → ``InProgress``."""
        return self._transition(issue_uuid, ISSUE_STATE_IN_PROGRESS)

    def reopen(self, issue_uuid: str) -> dict:
        """Transition ``InProgress`` → ``Open``."""
        return self._transition(issue_uuid, ISSUE_STATE_OPEN)

    def resolve(self, issue_uuid: str) -> dict:
        """Transition ``InProgress`` → ``Resolved``."""
        return self._transition(issue_uuid, ISSUE_STATE_RESOLVED)

    def archive(self, issue_uuid: str) -> dict:
        """Transition ``Open``, ``InProgress``, or ``Resolved`` → ``Archived``."""
        return self._transition(issue_uuid, ISSUE_STATE_ARCHIVED)

    def _transition(self, issue_uuid: str, to_state: str) -> dict:
        issue = self._issue.get_by_uuid(issue_uuid)
        if issue is None:
            raise ServiceNotFound(f"Issue not found: {issue_uuid}")
        from_state = issue["state"]
        allowed = _ISSUE_TRANSITIONS.get(from_state, frozenset())
        if to_state not in allowed:
            raise ServiceConflict(
                "INVALID_TRANSITION",
                f"Cannot transition issue {issue_uuid} from '{from_state}' to '{to_state}'.",
                {"from": from_state, "to": to_state, "allowed": sorted(allowed)},
            )
        self._issue.set_state(issue_uuid, to_state)
        return self._issue.get_by_uuid(issue_uuid)
