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
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import canonical_path as cpath
import repositories as repo

# Import Action constants — passed by callers to ImportService.execute().
IMPORT_ACTION_DATABASE_ONLY: str = "DATABASE_ONLY"
IMPORT_ACTION_COPY: str = "COPY"
IMPORT_ACTION_MOVE: str = "MOVE"

# ---------------------------------------------------------------------------
# Snapshot policy constants
# ---------------------------------------------------------------------------

# Retention classes
SNAP_RETENTION_ORDINARY: str = "ordinary"
SNAP_RETENTION_HIGH_RISK: str = "high-risk"

# Retention period in days per class
SNAP_RETENTION_DAYS: dict[str, int] = {
    SNAP_RETENTION_ORDINARY: 30,
    SNAP_RETENTION_HIGH_RISK: 180,
}

# Protection states
SNAP_PROTECTION_NONE: str = "unprotected"
SNAP_PROTECTION_PROTECTED: str = "protected"

# Operation-type identifiers used for risk assessment
SNAP_OP_DATA_MIGRATION: str = "data_migration"
SNAP_OP_RESTORE: str = "restore"
SNAP_OP_BULK_IMPORT: str = "bulk_import"
SNAP_OP_BULK_DELETE: str = "bulk_delete"
SNAP_OP_BULK_RENAME: str = "bulk_rename"
SNAP_OP_BULK_QUARANTINE: str = "bulk_quarantine"
SNAP_OP_WORKSPACE_PROMOTION: str = "workspace_promotion"
SNAP_OP_RELATIONSHIP_REBUILD: str = "relationship_rebuild"

# Always-high-risk operation types (snapshot always required)
_SNAP_ALWAYS_HIGH_RISK: frozenset[str] = frozenset({
    SNAP_OP_DATA_MIGRATION,
    SNAP_OP_RESTORE,
})

# Conditionally-high-risk operation types (snapshot required only when
# the service-side item count meets or exceeds the threshold below)
_SNAP_CONDITIONALLY_HIGH_RISK: frozenset[str] = frozenset({
    SNAP_OP_BULK_IMPORT,
    SNAP_OP_BULK_DELETE,
    SNAP_OP_BULK_RENAME,
    SNAP_OP_BULK_QUARANTINE,
    SNAP_OP_WORKSPACE_PROMOTION,
    SNAP_OP_RELATIONSHIP_REBUILD,
})

# Item-count threshold above which a conditionally-high-risk operation is
# classified as high-risk and a snapshot is required.
SNAP_BULK_THRESHOLD: int = 50


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


class AuthenticationFailure(Exception):
    """Credential failure that the API adapter maps to a 401 response."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class AuthorizationFailure(Exception):
    """Scope failure that the API adapter maps to a 403 response."""

    def __init__(self, required_scope: str):
        super().__init__("The token does not have the required permission.")
        self.code = "AUTHORIZATION_INSUFFICIENT_SCOPE"
        self.required_scope = required_scope


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Device authentication lifecycle
# ---------------------------------------------------------------------------

AUTH_ROLE_SCOPES: dict[str, frozenset[str]] = {
    "reader": frozenset({"read"}),
    "writer": frozenset({"read", "write"}),
    "admin": frozenset({"read", "write", "admin"}),
}
AUTH_DEFAULT_TOKEN_VALIDITY = timedelta(days=365)


class AuthenticationService:
    """Own the approved-device and bearer-token lifecycle.

    The service never persists plaintext credentials.  Token plaintext exists
    only in the return value from the two administrator-approved issuance
    methods, allowing the API/UI to display it exactly once.
    """

    def __init__(
        self,
        auth_repo: repo.AuthRepository,
        *,
        registration_secret: str | None = None,
        now_fn=None,
        issue_service=None,
        operation_service=None,
    ):
        self._repo = auth_repo
        self._registration_secret = registration_secret
        self._now = now_fn or (lambda: datetime.now(timezone.utc))
        self._issues = issue_service
        self._operations = operation_service

    def _record_operation(self, operation_type: str, entity_uuid: str, summary: str, issue_uuid: str | None = None) -> dict | None:
        if self._operations is None:
            return None
        operation = self._operations.begin(operation_type, "System", entity_uuid=entity_uuid, issue_uuid=issue_uuid, summary=summary)
        return self._operations.succeed(operation["uuid"], summary)

    def _now_utc(self) -> datetime:
        value = self._now()
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    @staticmethod
    def _validate_role_and_scopes(role: str, scopes: list[str] | None) -> tuple[str, list[str]]:
        if role not in AUTH_ROLE_SCOPES:
            raise ValueError("The requested role is not supported.")
        requested = list(scopes or AUTH_ROLE_SCOPES[role])
        if not requested or any(not isinstance(scope, str) or scope not in AUTH_ROLE_SCOPES[role] for scope in requested):
            raise ValueError("The requested scopes are not permitted for the role.")
        return role, sorted(set(requested))

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def request_registration(
        self,
        *,
        device_name: str,
        device_identity: str,
        requested_role: str,
        requested_scopes: list[str] | None,
        registration_proof: str,
    ) -> dict:
        """Record a reviewable registration request; this never grants access."""
        if not all(isinstance(value, str) and value.strip() for value in (device_name, device_identity, registration_proof)):
            raise ValueError("Device name, stable device identity, and registration proof are required.")
        if not self._registration_secret or not hmac.compare_digest(registration_proof, self._registration_secret):
            raise AuthenticationFailure("AUTHENTICATION_INVALID_REGISTRATION_PROOF", "The registration proof is invalid.")
        role, scopes = self._validate_role_and_scopes(requested_role, requested_scopes)
        try:
            registration = self._repo.create_registration({
                "device_name": device_name.strip(), "device_identity": device_identity.strip(),
                "requested_role": role, "requested_scopes": scopes,
            })
            issue = None
            if self._issues is not None:
                issue = self._issues.create({
                    "category": "Device Registration",
                    "description": f"Device registration requires administrator review: {registration['device_name']}",
                    "suggested_resolution": "Review and approve or reject the registration request.",
                    "source_workflow": "AuthenticationService",
                })
                self._issues.link(issue["uuid"], "affected_entity", registration["uuid"])
            operation = self._record_operation("device_registration", registration["uuid"], "Device registration requested.", issue["uuid"] if issue else None)
            if issue is not None and operation is not None:
                self._issues.link(issue["uuid"], "triggering_operation", operation["uuid"])
            return registration
        except repo.PersistenceConflict as exc:
            raise ServiceConflict("BUSINESS_CONFLICT", "A registration already exists for this device identity.", exc.details)

    def approve_registration(
        self,
        registration_uuid: str,
        *,
        approved_role: str | None = None,
        approved_scopes: list[str] | None = None,
        validity: timedelta | None = None,
        trusted: bool = True,
    ) -> dict:
        registration = self._repo.get_registration(registration_uuid)
        if registration is None:
            raise ServiceNotFound("Registration request not found.")
        if registration["status"] != "PendingApproval":
            raise ServiceConflict("BUSINESS_CONFLICT", "The registration request is no longer awaiting approval.")
        role, scopes = self._validate_role_and_scopes(
            approved_role or registration["requested_role"],
            approved_scopes if approved_scopes is not None else registration["requested_scopes"],
        )
        registration = self._repo.approve_registration(registration_uuid, role, scopes, trusted)
        if registration is None:
            raise ServiceNotFound("Registration request not found.")
        issued = self._issue_token(registration, scopes, validity)
        self._record_operation("device_token_issuance", registration["uuid"], "Approved device token issued.")
        return issued

    def reject_registration(self, registration_uuid: str) -> None:
        registration = self._repo.get_registration(registration_uuid)
        if registration is None:
            raise ServiceNotFound("Registration request not found.")
        if registration["status"] != "PendingApproval":
            raise ServiceConflict("BUSINESS_CONFLICT", "The registration request is no longer awaiting approval.")
        self._repo.reject_registration(registration_uuid)

    def _issue_token(self, registration: dict, scopes: list[str], validity: timedelta | None) -> dict:
        if registration["status"] != "Approved" or not registration["trusted"]:
            raise ServiceConflict("BUSINESS_CONFLICT", "Only approved trusted devices can receive tokens.")
        lifetime = validity or AUTH_DEFAULT_TOKEN_VALIDITY
        if lifetime <= timedelta(0):
            raise ValueError("Token validity must be positive.")
        now = self._now_utc()
        plaintext = secrets.token_urlsafe(32)
        token = self._repo.create_token({
            "uuid": str(_uuid_mod.uuid4()), "token_hash": self._hash_token(plaintext),
            "registration_uuid": registration["uuid"], "device_name": registration["device_name"],
            "scopes": scopes, "created_at": now.isoformat(),
            "expires_at": (now + lifetime).isoformat(),
        })
        # The persisted shape deliberately excludes token_hash from caller data.
        token.pop("token_hash", None)
        return {"token": plaintext, "token_record": token}

    def authenticate(self, token_plaintext: str, required_scope: str | None = None) -> dict:
        if not isinstance(token_plaintext, str) or not token_plaintext:
            raise AuthenticationFailure("AUTHENTICATION_MISSING_TOKEN", "A bearer token is required.")
        token = self._repo.get_token_by_hash(self._hash_token(token_plaintext))
        if token is None:
            raise AuthenticationFailure("AUTHENTICATION_INVALID_TOKEN", "The bearer token is invalid.")
        if token["revoked_at"] is not None:
            raise AuthenticationFailure("AUTHENTICATION_REVOKED_TOKEN", "The bearer token has been revoked.")
        expires_at = datetime.fromisoformat(token["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= self._now_utc():
            raise AuthenticationFailure("AUTHENTICATION_EXPIRED_TOKEN", "The bearer token has expired.")
        registration = self._repo.get_registration(token["registration_uuid"])
        if registration is None or registration["status"] != "Approved" or not registration["trusted"]:
            raise AuthenticationFailure("AUTHENTICATION_UNAPPROVED_DEVICE", "The device is not approved for access.")
        if required_scope is not None and required_scope not in token["scopes"]:
            raise AuthorizationFailure(required_scope)
        self._repo.touch_token(token["uuid"], self._now_utc().isoformat())
        return {"device_name": token["device_name"], "registration_uuid": token["registration_uuid"], "scopes": token["scopes"]}

    def request_renewal(self, token_plaintext: str, *, device_identity: str) -> dict:
        principal = self.authenticate(token_plaintext)
        registration = self._repo.get_registration(principal["registration_uuid"])
        if registration is None or registration["device_identity"] != device_identity:
            raise AuthenticationFailure("AUTHENTICATION_INVALID_DEVICE", "The device identity does not match the token.")
        old_token = self._repo.get_token_by_hash(self._hash_token(token_plaintext))
        return self._repo.create_renewal_request({
            "registration_uuid": registration["uuid"], "previous_token_uuid": old_token["uuid"],
            "requested_role": registration["approved_role"], "requested_scopes": registration["approved_scopes"],
        })

    def approve_renewal(self, renewal_uuid: str, *, validity: timedelta | None = None) -> dict:
        renewal = self._repo.get_renewal_request(renewal_uuid)
        if renewal is None:
            raise ServiceNotFound("Token renewal request not found.")
        if renewal["status"] != "PendingApproval":
            raise ServiceConflict("BUSINESS_CONFLICT", "The token renewal request is no longer awaiting approval.")
        registration = self._repo.get_registration(renewal["registration_uuid"])
        if registration is None:
            raise ServiceNotFound("Registered device not found.")
        approved = self._repo.approve_renewal(renewal_uuid)
        issued = self._issue_token(registration, approved["requested_scopes"], validity)
        self._repo.revoke_token(renewal["previous_token_uuid"], replaced_by_uuid=issued["token_record"]["uuid"])
        return issued

    def revoke_token(self, token_uuid: str) -> None:
        if not self._repo.revoke_token(token_uuid):
            raise ServiceNotFound("Active token not found.")
        self._record_operation("device_token_revocation", token_uuid, "Device token revoked.")


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
        self._require_active_for_edit(ids)
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
        self._require_active_for_edit([wa_id])
        self._repo.update(wa_id, self.ALLOWED_UPDATE_FIELDS, changes)

    def _require_active_for_edit(self, workspace_ids: list[int]) -> None:
        """Reject ordinary edits outside an Active workspace lifecycle state.

        The Workspace Workflow reserves Review changes for a dataset-specific
        editing contract.  ``workspace_album`` has no such contract yet, so
        only Active records may receive its general update or batch-update
        operations.  Closed and Archived / Retired records are always
        historical and read-only.
        """
        for wa_id in workspace_ids:
            state = self._repo.get_lifecycle_state(wa_id)
            if state is None:
                raise ServiceNotFound(f"Workspace album {wa_id} not found.")
            if state != LIFECYCLE_ACTIVE:
                raise ServiceConflict(
                    "LIFECYCLE_EDIT_NOT_ALLOWED",
                    (
                        f"Workspace album {wa_id} in '{state}' does not allow "
                        "ordinary business editing."
                    ),
                    {"workspace_id": wa_id, "current_state": state},
                )

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


def _source_is_canonical_destination(source_path: str, destination: Path) -> bool:
    """Return whether an existing source directory is already the destination.

    This is the narrow Import Workflow exception to the normal occupied-path
    rejection: a source Album already located at its own computed canonical
    destination needs metadata persistence only, not a filesystem operation.
    """
    if not source_path:
        return False
    source = Path(source_path)
    return source.is_dir() and source.resolve() == destination.resolve()


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
        operation_service,
        initiator: str = "CLI",
    ):
        self._repo = import_repo
        self._snapshot = snapshot_fn
        self._backup_log = backup_log_fn
        self._change_log = change_log_fn
        self._operations = operation_service
        self._initiator = initiator

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
            source_at_canonical_destination = _source_is_canonical_destination(
                n["source_path"], full_path
            )
            if path_exists and not source_at_canonical_destination:
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
                    "source_at_canonical_destination": source_at_canonical_destination,
                    "effective_action": (
                        IMPORT_ACTION_DATABASE_ONLY
                        if source_at_canonical_destination else None
                    ),
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
        operation = self._operations.begin(
            "import",
            self._initiator,
            summary="Import execution started.",
            import_uuid=import_uuid,
        )
        operation_uuid = operation["uuid"]

        try:
            snap = self._snapshot("import")
            self._backup_log(
                {
                    "timestamp": now,
                    "reason": "import",
                    "ok": True,
                    "snapshot": str(snap),
                    "tag": "",
                    "operation_uuid": operation_uuid,
                    "import_uuid": import_uuid,
                }
            )
        except Exception as ex:
            self._backup_log(
                {
                    "timestamp": now,
                    "reason": "import",
                    "ok": False,
                    "error": str(ex),
                    "tag": "",
                    "operation_uuid": operation_uuid,
                    "import_uuid": import_uuid,
                }
            )

        results = []
        created_albums = 0
        skipped = 0
        errors = 0
        needs_repair_count = 0
        first_execution_error: str | None = None
        first_needs_repair_error: str | None = None

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
                if _source_is_canonical_destination(source_path, full_dest):
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
                    if first_needs_repair_error is None:
                        first_needs_repair_error = str(fs_ex)
                    self._change_log(
                        {
                            "timestamp": item_now,
                            "action": "import_album",
                            "operation_uuid": operation_uuid,
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
                        "operation_uuid": operation_uuid,
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
                if first_execution_error is None:
                    first_execution_error = str(ex)

            results.append(result)

        if needs_repair_count:
            self._operations.mark_needs_repair(
                operation_uuid,
                "filesystem",
                "filesystem.write-failed",
                summary="Import execution requires filesystem repair.",
                error_details=first_needs_repair_error,
                repair_state="NeedsRepair",
                recovery_context=(
                    f"Review filesystem repair for import {import_uuid}; "
                    f"{needs_repair_count} item(s) require verification."
                ),
            )
        elif errors:
            self._operations.fail(
                operation_uuid,
                "database",
                "database.transaction-failed",
                summary="Import execution failed before a verified outcome.",
                error_details=first_execution_error,
                recovery_context=(
                    f"Review failed items for import {import_uuid}; "
                    f"{errors} item(s) did not complete."
                ),
            )
        else:
            self._operations.succeed(
                operation_uuid,
                summary="Import execution completed successfully.",
            )

        return {
            "operation_uuid": operation_uuid,
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


def assess_operation_risk(
    operation_type: str,
    item_count: int = 0,
) -> tuple[bool, str]:
    """Determine whether a snapshot is required and which retention class applies.

    Policy:
    - Always-high-risk operations (``data_migration``, ``restore``) always
      require a snapshot with retention class ``'high-risk'``.
    - Conditionally-high-risk operations require a snapshot with retention
      class ``'high-risk'`` when *item_count* ≥ :data:`SNAP_BULK_THRESHOLD`.
      Below the threshold no snapshot is required (retention class ``'ordinary'``
      is returned as an informational default).
    - All other operations do not require a snapshot.

    Args:
        operation_type: One of the ``SNAP_OP_*`` constants, or any custom
            string for operations not listed in the policy table.
        item_count: Number of entities affected by the operation; used as the
            service-side signal for conditionally-high-risk operations.

    Returns:
        ``(snapshot_required, retention_class)`` — a 2-tuple where the first
        element is ``True`` when a snapshot must be taken before executing the
        operation and the second is the applicable retention class string.
    """
    if operation_type in _SNAP_ALWAYS_HIGH_RISK:
        return True, SNAP_RETENTION_HIGH_RISK
    if operation_type in _SNAP_CONDITIONALLY_HIGH_RISK:
        if item_count >= SNAP_BULK_THRESHOLD:
            return True, SNAP_RETENTION_HIGH_RISK
        return False, SNAP_RETENTION_ORDINARY
    return False, SNAP_RETENTION_ORDINARY


def is_retention_eligible(
    snapshot_record: dict,
    now: datetime | None = None,
) -> bool:
    """Return ``True`` when *snapshot_record* may be deleted by automated cleanup.

    Cleanup eligibility is a hard gate: a snapshot is eligible only when its
    retention period has expired **and** it is not protected.  Both conditions
    must be satisfied; neither may be treated as a soft recommendation.

    Args:
        snapshot_record: A catalog dict with at minimum:
            - ``created_at`` (ISO 8601 string or ``None``)
            - ``retention_class`` (``'ordinary'`` | ``'high-risk'`` | ``None``)
            - ``protection_state`` (``'protected'`` | anything else)
        now: Reference timestamp for age calculation; defaults to the current
            UTC time when ``None``.

    Returns:
        ``True`` when the snapshot may be deleted; ``False`` otherwise.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Protected snapshots must never be deleted by automated cleanup.
    if snapshot_record.get("protection_state") == SNAP_PROTECTION_PROTECTED:
        return False

    created_at_str = snapshot_record.get("created_at")
    if not created_at_str:
        # No creation timestamp → treat as not eligible to avoid silent loss.
        return False

    try:
        created_at = _parse_iso_datetime(created_at_str)
    except Exception:
        return False

    retention_class = snapshot_record.get("retention_class", SNAP_RETENTION_ORDINARY)
    retain_days = SNAP_RETENTION_DAYS.get(retention_class, SNAP_RETENTION_DAYS[SNAP_RETENTION_ORDINARY])

    age_days = (now - created_at).total_seconds() / 86400
    return age_days >= retain_days


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

    def assess(self, operation_type: str, item_count: int = 0) -> dict:
        """Return the snapshot decision for *operation_type* with *item_count* items.

        Delegates to the module-level :func:`assess_operation_risk` pure function
        and returns the result as a dict suitable for inclusion in an Operation
        record or API response.

        Args:
            operation_type: One of the ``SNAP_OP_*`` constants.
            item_count: Number of entities affected; used for conditionally
                high-risk threshold evaluation.

        Returns:
            ``{'snapshot_required': bool, 'retention_class': str}``
        """
        required, retention_class = assess_operation_risk(operation_type, item_count)
        return {"snapshot_required": required, "retention_class": retention_class}

    def purge_eligible(
        self,
        catalog_records: list,
        now: datetime | None = None,
    ) -> list:
        """Filter *catalog_records* and return only those eligible for deletion.

        Applies the hard cleanup-eligibility gate defined by the snapshot
        policy:
        - A snapshot is eligible only when its retention period has expired
          **and** it is not protected.
        - Protected snapshots are never included, regardless of age.
        - Records with no ``created_at`` value are never included.

        Args:
            catalog_records: List of snapshot catalog dicts.  Each dict should
                contain at minimum: ``created_at``, ``retention_class``, and
                ``protection_state``.
            now: Reference timestamp; defaults to the current UTC time.

        Returns:
            Subset of *catalog_records* that may be deleted by automated
            cleanup.  The order of records is preserved.
        """
        return [r for r in catalog_records if is_retention_eligible(r, now)]

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

ISSUE_CATEGORIES: frozenset[str] = frozenset({
    "Validation", "Filesystem", "Import", "Repair", "AI Processing",
    "Security", "Device Registration",
})
ISSUE_PRIORITIES: frozenset[str] = frozenset({"Normal", "High", "Critical"})
ISSUE_LINK_RELATIONSHIPS: frozenset[str] = frozenset({
    "triggering_operation", "related_operation", "affected_entity",
})
ISSUE_ADMIN_ROLE = "admin"


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
        # Repair is an Issue integration point; category validation and Issue
        # lifecycle policy remain owned by the shared Issue service.
        self._issues = IssueService(issue_repo)

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
        issue = self._issues.create(base_issue)
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
# Repair decision policy
# ---------------------------------------------------------------------------

class RepairDecisionService:
    """Apply the bounded repair-selection policy before filesystem work.

    This boundary intentionally accepts relative paths only, so every repair
    action remains confined to the configured managed root.
    """

    def __init__(self, repair_service, operation_service, suppression_repo, managed_root, audit_log_fn=None):
        self._repair_service = repair_service
        self._operations = operation_service
        self._suppressions = suppression_repo
        self._root = Path(managed_root).resolve()
        self._audit = audit_log_fn or (lambda _: None)

    def classify(self, observed_paths: list[str], expected_path: str, *, authoritative_path: str | None = None) -> dict:
        """Classify candidates without mutating files or repair state."""
        expected = self._under_root(expected_path)
        candidates = [self._under_root(path) for path in observed_paths]
        automatic = (
            len(candidates) == 1 and candidates[0].is_dir() and not expected.exists()
            and self._canonicalization_only(candidates[0], expected)
        )
        if automatic:
            return {"category": REPAIR_CATEGORY_AUTOMATIC, "candidate": self._relative(candidates[0]), "evidence": "canonicalization-only"}
        if len(candidates) != 1 or authoritative_path != self._relative(candidates[0]):
            return {"category": REPAIR_CATEGORY_MANUAL_CONFLICT, "candidate": None, "evidence": "ambiguous-or-insufficient"}
        return {"category": REPAIR_CATEGORY_ASSISTED, "candidate": self._relative(candidates[0]), "evidence": "authoritative-provenance"}

    def execute_automatic_rename(self, repair_uuid: str, observed_path: str, expected_path: str, *, initiator: str = "System") -> dict:
        decision = self.classify([observed_path], expected_path)
        if decision["category"] != REPAIR_CATEGORY_AUTOMATIC:
            raise ServiceConflict("AUTOMATIC_POLICY_REJECTED", "Repair is not eligible for an automatic rename.", decision)
        repair = self._repair_service.start_repair(repair_uuid)
        operation = self._operations.begin("repair_automatic_rename", initiator, repair_uuid=repair_uuid, related_operation_uuid=repair["operation_uuid"])
        source = self._under_root(observed_path)
        destination = self._under_root(expected_path)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
            self._repair_service.complete_action(repair_uuid)
            self._operations.succeed(operation["uuid"], "Automatic canonicalization-only rename completed.")
            self._audit({"action": "repair_automatic_rename", "repair_uuid": repair_uuid, "operation_uuid": operation["uuid"], "success": True})
            return operation
        except OSError as exc:
            self._operations.mark_needs_repair(operation["uuid"], "filesystem", "filesystem.rename-failed", summary="Automatic repair rename failed.", error_details=str(exc), repair_state=REPAIR_STATE_NEEDS_REPAIR)
            self._audit({"action": "repair_automatic_rename", "repair_uuid": repair_uuid, "operation_uuid": operation["uuid"], "success": False})
            raise

    def create_suppression(self, *, fingerprint: str, scope_path: str, reason: str, creator: str, actor_role: str, expires_at: str) -> dict:
        self._require_admin(actor_role)
        record = self._suppressions.create({"fingerprint": fingerprint, "scope_path": scope_path, "reason": reason, "creator": creator, "expires_at": expires_at})
        self._audit({"action": "repair_suppression_created", "suppression_uuid": record["uuid"], "creator": creator})
        return record

    def revoke_suppression(self, suppression_uuid: str, *, actor: str, actor_role: str) -> dict:
        self._require_admin(actor_role)
        record = self._suppressions.revoke(suppression_uuid, actor)
        if record is None:
            raise ServiceNotFound(f"Repair suppression not found: {suppression_uuid}")
        self._audit({"action": "repair_suppression_revoked", "suppression_uuid": suppression_uuid, "creator": actor})
        return record

    def is_suppressed(self, fingerprint: str, scope_path: str, *, now: datetime | None = None) -> bool:
        at = (now or datetime.now(timezone.utc)).isoformat()
        record = self._suppressions.find_active(fingerprint, scope_path, at)
        if record:
            self._audit({"action": "repair_suppression_applied", "suppression_uuid": record["uuid"]})
        return record is not None

    def _under_root(self, relative_path: str) -> Path:
        path = Path(relative_path)
        if path.is_absolute():
            raise ValueError("Repair paths must be relative to the managed root.")
        resolved = (self._root / path).resolve()
        if resolved == self._root or self._root not in resolved.parents:
            raise ValueError("Repair path escapes the managed root.")
        return resolved

    def _relative(self, path: Path) -> str:
        return path.relative_to(self._root).as_posix()

    @staticmethod
    def _canonicalization_only(source: Path, destination: Path) -> bool:
        source_parts, dest_parts = source.parts, destination.parts
        if len(source_parts) != len(dest_parts) or source == destination:
            return False
        return all(
            cpath.canonicalize_component(left).casefold() == cpath.canonicalize_component(right).casefold()
            for left, right in zip(source_parts, dest_parts)
        )

    @staticmethod
    def _require_admin(actor_role: str) -> None:
        if actor_role != ISSUE_ADMIN_ROLE:
            raise ServiceConflict("ADMIN_REQUIRED", "This repair suppression action requires an administrator.")


class QuarantineService:
    """Administrator-only intact-directory quarantine and restoration."""
    def __init__(self, quarantine_repo, operation_service, archive_root, quarantine_root, snapshot_fn, audit_log_fn=None):
        self._repo, self._operations = quarantine_repo, operation_service
        self._archive, self._quarantine = Path(archive_root).resolve(), Path(quarantine_root).resolve()
        self._snapshot, self._audit = snapshot_fn, audit_log_fn or (lambda _: None)

    def quarantine(self, relative_path, *, repair_uuid, reason, actor_role, initiator="System", item_count=1):
        self._admin(actor_role); source = self._within(self._archive, relative_path)
        if not source.is_dir(): raise ServiceNotFound("Managed directory was not found.")
        snapshot = self._snapshot("repair_quarantine") if item_count > 1 else None
        if item_count > 1 and snapshot is None: raise ServiceConflict("SNAPSHOT_REQUIRED", "A required snapshot was not created.")
        op = self._operations.begin("repair_quarantine", initiator, repair_uuid=repair_uuid, summary=f"Quarantine {relative_path}")
        item_uuid = str(_uuid_mod.uuid4()); target = self._quarantine / item_uuid
        inventory = "\n".join(sorted(p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()))
        shutil.move(str(source), str(target))
        record = self._repo.create({"uuid": item_uuid, "original_path": relative_path, "quarantine_path": item_uuid, "repair_uuid": repair_uuid, "operation_uuid": op["uuid"], "reason": reason, "inventory": inventory, "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()})
        self._operations.succeed(op["uuid"], "Directory quarantined intact.")
        self._audit({"action":"quarantine","quarantine_uuid":item_uuid,"operation_uuid":op["uuid"],"snapshot":str(snapshot) if snapshot else None})
        return record

    def restore(self, item_uuid, destination, *, actor_role, initiator="System"):
        self._admin(actor_role); item = self._repo.get(item_uuid)
        if not item: raise ServiceNotFound("Quarantine item was not found.")
        source = self._within(self._quarantine, item["quarantine_path"]); target = self._within(self._archive, destination)
        if target.exists(): raise ServiceConflict("RESTORE_DESTINATION_EXISTS", "Restore destination already exists.")
        snapshot = self._snapshot("repair_restore")
        if snapshot is None: raise ServiceConflict("SNAPSHOT_REQUIRED", "A required snapshot was not created.")
        op = self._operations.begin("repair_restore", initiator, repair_uuid=item["repair_uuid"], related_operation_uuid=item["operation_uuid"])
        target.parent.mkdir(parents=True, exist_ok=True); shutil.move(str(source), str(target))
        self._operations.succeed(op["uuid"], "Quarantined directory restored intact.")
        self._audit({"action":"restore","quarantine_uuid":item_uuid,"operation_uuid":op["uuid"],"snapshot":str(snapshot)})
        return op

    def list_items(self, *, actor_role): self._admin(actor_role); return self._repo.list()
    @staticmethod
    def _admin(role):
        if role != ISSUE_ADMIN_ROLE: raise ServiceConflict("ADMIN_REQUIRED", "This quarantine action requires an administrator.")
    @staticmethod
    def _within(root, relative):
        p = Path(relative)
        if p.is_absolute(): raise ValueError("Quarantine paths must be relative.")
        resolved = (root / p).resolve()
        if root not in resolved.parents: raise ValueError("Quarantine path escapes its root.")
        return resolved


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
        category = fields.get("category")
        if category not in ISSUE_CATEGORIES:
            raise ValueError("The Issue category is not supported.")
        if not isinstance(fields.get("description"), str) or not fields["description"].strip():
            raise ValueError("Issue description is required.")
        if not isinstance(fields.get("source_workflow"), str) or not fields["source_workflow"].strip():
            raise ValueError("Issue source workflow is required.")
        if fields.get("priority", "Normal") not in ISSUE_PRIORITIES:
            raise ValueError("The Issue priority is not supported.")
        # Ownership is an administrative action even when supplied alongside
        # creation; integrations create unowned Issues by default.
        fields.pop("owner", None)
        fields.setdefault("state", ISSUE_STATE_OPEN)
        return self._issue.create(fields)

    def categorize(self, issue_uuid: str, category: str) -> dict:
        """Apply one of the documented cross-cutting Issue categories."""
        if category not in ISSUE_CATEGORIES:
            raise ValueError("The Issue category is not supported.")
        self._require_issue(issue_uuid)
        self._issue.set_category(issue_uuid, category)
        return self._issue.get_by_uuid(issue_uuid)

    def assign(self, issue_uuid: str, owner: str | None, *, actor_role: str) -> dict:
        """Assign or clear ownership; only administrators may do this."""
        self._require_admin(actor_role)
        self._require_issue(issue_uuid)
        if owner is not None and (not isinstance(owner, str) or not owner.strip()):
            raise ValueError("Issue owner must be a non-empty name or null.")
        self._issue.set_owner(issue_uuid, owner.strip() if owner else None)
        return self._issue.get_by_uuid(issue_uuid)

    def begin_work(self, issue_uuid: str) -> dict:
        """Transition ``Open`` → ``InProgress``."""
        return self._transition(issue_uuid, ISSUE_STATE_IN_PROGRESS)

    def reopen(self, issue_uuid: str) -> dict:
        """Transition ``InProgress`` → ``Open``."""
        return self._transition(issue_uuid, ISSUE_STATE_OPEN)

    def resolve(self, issue_uuid: str, verification: str, *, actor_role: str) -> dict:
        """Transition ``InProgress`` → ``Resolved`` after verified resolution."""
        self._require_admin(actor_role)
        if not isinstance(verification, str) or not verification.strip():
            raise ValueError("Resolution requires workflow verification.")
        return self._transition(
            issue_uuid, ISSUE_STATE_RESOLVED,
            resolution_verification=verification.strip(), resolved_by=actor_role,
        )

    def archive(self, issue_uuid: str, *, actor_role: str) -> dict:
        """Transition ``Open``, ``InProgress``, or ``Resolved`` → ``Archived``."""
        self._require_admin(actor_role)
        return self._transition(issue_uuid, ISSUE_STATE_ARCHIVED)

    def link(self, issue_uuid: str, relationship: str, target_uuid: str) -> list[dict]:
        """Link an Issue to the triggering Operation or affected entity."""
        self._require_issue(issue_uuid)
        if relationship not in ISSUE_LINK_RELATIONSHIPS:
            raise ValueError("The Issue link relationship is not supported.")
        if not isinstance(target_uuid, str) or not target_uuid.strip():
            raise ValueError("Issue link target must be a stable identifier.")
        self._issue.add_link(issue_uuid, relationship, target_uuid.strip())
        return self._issue.list_links(issue_uuid)

    def links(self, issue_uuid: str) -> list[dict]:
        """Return links after confirming the Issue exists."""
        self._require_issue(issue_uuid)
        return self._issue.list_links(issue_uuid)

    def _require_issue(self, issue_uuid: str) -> dict:
        issue = self._issue.get_by_uuid(issue_uuid)
        if issue is None:
            raise ServiceNotFound(f"Issue not found: {issue_uuid}")
        return issue

    @staticmethod
    def _require_admin(actor_role: str) -> None:
        if actor_role != ISSUE_ADMIN_ROLE:
            raise AuthorizationFailure("admin")

    def _transition(self, issue_uuid: str, to_state: str, **state_fields) -> dict:
        issue = self._require_issue(issue_uuid)
        from_state = issue["state"]
        allowed = _ISSUE_TRANSITIONS.get(from_state, frozenset())
        if to_state not in allowed:
            raise ServiceConflict(
                "INVALID_TRANSITION",
                f"Cannot transition issue {issue_uuid} from '{from_state}' to '{to_state}'.",
                {"from": from_state, "to": to_state, "allowed": sorted(allowed)},
            )
        self._issue.set_state(issue_uuid, to_state, **state_fields)
        return self._issue.get_by_uuid(issue_uuid)


# ---------------------------------------------------------------------------
# Operation logging constants
# ---------------------------------------------------------------------------

# Status vocabulary — every Operation has exactly one of these at any time.
OP_STATUS_PENDING: str = "Pending"
OP_STATUS_RUNNING: str = "Running"
OP_STATUS_SUCCEEDED: str = "Succeeded"
OP_STATUS_FAILED: str = "Failed"
OP_STATUS_NEEDS_REPAIR: str = "NeedsRepair"
OP_STATUS_CANCELLED: str = "Cancelled"

# Initiator vocabulary — who or what triggered the operation.
OP_INITIATOR_WEB_UI: str = "WebUI"
OP_INITIATOR_AI_WORKER: str = "AIWorker"
OP_INITIATOR_CLI: str = "CLI"
OP_INITIATOR_SYSTEM: str = "System"

# Terminal statuses — operations in these states must not be transitioned
# to a success status after the fact.
_OP_TERMINAL_STATUSES: frozenset[str] = frozenset({
    OP_STATUS_SUCCEEDED,
    OP_STATUS_FAILED,
    OP_STATUS_NEEDS_REPAIR,
    OP_STATUS_CANCELLED,
})


# ---------------------------------------------------------------------------
# OperationService
# ---------------------------------------------------------------------------

class OperationService:
    """Records durable Operation history for material backend writes.

    This service is the single path for creating and completing Operation
    records.  All material writes that require a database-backed Operation
    record (imports, bulk actions, snapshots, restores, repairs, etc.) call
    this service to open and close their records.

    Supporting log output (JSONL) remains the responsibility of the caller;
    this service owns only the database-backed record.

    Lifecycle
    ---------
    1. Call :meth:`begin` at the start of the material work (or just before
       it starts) to create the Operation in ``Pending`` or ``Running`` state.
    2. Call one of :meth:`succeed`, :meth:`fail`, :meth:`mark_needs_repair`,
       or :meth:`cancel` when the work completes or is stopped.

    The service does not enforce the status transition graph because the
    Operation record is append-only in business meaning: corrections and
    follow-up are recorded as linked subsequent activity, not by erasing the
    original outcome.  It does enforce the prohibition on moving a terminal
    Operation to ``Succeeded``.
    """

    def __init__(self, operation_repo):
        self._repo = operation_repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def begin(
        self,
        operation_type: str,
        initiator: str,
        *,
        status: str = OP_STATUS_RUNNING,
        summary: str | None = None,
        entity_uuid: str | None = None,
        import_uuid: str | None = None,
        batch_uuid: str | None = None,
        repair_uuid: str | None = None,
        related_operation_uuid: str | None = None,
        parent_operation_uuid: str | None = None,
        issue_uuid: str | None = None,
        recovery_context: str | None = None,
    ) -> dict:
        """Create and persist a new Operation record.

        Sets ``started_at`` to the current UTC time.  The initial status
        defaults to ``'Running'``.

        Args:
            operation_type: Stable type identifier for the operation family.
            initiator: One of the ``OP_INITIATOR_*`` constants.
            status: Initial status; usually ``'Pending'`` (work has been
                accepted but not started) or ``'Running'`` (work is in
                progress).
            summary: Optional short human-readable description.
            entity_uuid: UUID of the primary entity affected, when applicable.
            import_uuid: UUID of the import batch, for import operations.
            batch_uuid: UUID of the batch, for batch and promotion operations.
            repair_uuid: UUID of the repair case, for repair operations.
            related_operation_uuid: UUID of a non-parent related Operation.
            parent_operation_uuid: UUID of the direct parent Operation.
            issue_uuid: UUID of the tracking Issue, for issue-driven workflows.
            recovery_context: Instructions or context for recovery.

        Returns:
            Normalised Operation dict.
        """
        return self._repo.create(
            {
                "operation_type": operation_type,
                "initiator": initiator,
                "status": status,
                "summary": summary,
                "entity_uuid": entity_uuid,
                "import_uuid": import_uuid,
                "batch_uuid": batch_uuid,
                "repair_uuid": repair_uuid,
                "related_operation_uuid": related_operation_uuid,
                "parent_operation_uuid": parent_operation_uuid,
                "issue_uuid": issue_uuid,
                "recovery_context": recovery_context,
            }
        )

    def succeed(self, op_uuid: str, summary: str | None = None) -> dict:
        """Mark an Operation as ``Succeeded`` and return its updated record.

        Args:
            op_uuid: UUID of the Operation to complete.
            summary: Optional outcome summary to persist.

        Returns:
            Updated normalised Operation dict.

        Raises:
            ServiceNotFound: When *op_uuid* does not exist.
            ServiceConflict: When the Operation is already in a terminal
                status and cannot be moved to ``Succeeded``.
        """
        op = self._repo.get_by_uuid(op_uuid)
        if op is None:
            raise ServiceNotFound(f"Operation not found: {op_uuid}")
        if op["status"] in _OP_TERMINAL_STATUSES and op["status"] != OP_STATUS_SUCCEEDED:
            raise ServiceConflict(
                "TERMINAL_STATUS",
                (
                    f"Operation {op_uuid} is already in terminal status "
                    f"'{op['status']}' and cannot be moved to Succeeded."
                ),
                {"current_status": op["status"]},
            )
        self._repo.set_status(op_uuid, OP_STATUS_SUCCEEDED, summary=summary)
        return self._repo.get_by_uuid(op_uuid)

    def fail(
        self,
        op_uuid: str,
        error_category: str,
        error_code: str,
        summary: str | None = None,
        error_details: str | None = None,
        recovery_context: str | None = None,
    ) -> dict:
        """Mark an Operation as ``Failed`` and return its updated record.

        Args:
            op_uuid: UUID of the Operation.
            error_category: Coarse error category from the permitted set
                (e.g. ``'filesystem'``, ``'database'``, ``'validation'``).
            error_code: Stable error code refining the category
                (e.g. ``'filesystem.write-failed'``).
            summary: Human-readable failure summary.
            error_details: Free-text diagnostic detail (not for API exposure
                to unprivileged clients).
            recovery_context: Recovery instructions or context.

        Returns:
            Updated normalised Operation dict.

        Raises:
            ServiceNotFound: When *op_uuid* does not exist.
        """
        op = self._repo.get_by_uuid(op_uuid)
        if op is None:
            raise ServiceNotFound(f"Operation not found: {op_uuid}")
        self._repo.set_status(
            op_uuid,
            OP_STATUS_FAILED,
            summary=summary,
            error_category=error_category,
            error_code=error_code,
            error_details=error_details,
            recovery_context=recovery_context,
        )
        return self._repo.get_by_uuid(op_uuid)

    def mark_needs_repair(
        self,
        op_uuid: str,
        error_category: str,
        error_code: str,
        summary: str | None = None,
        error_details: str | None = None,
        repair_state: str | None = None,
        recovery_context: str | None = None,
    ) -> dict:
        """Mark an Operation as ``NeedsRepair`` and return its updated record.

        Use this when material work ended unsuccessfully and a filesystem
        repair workflow is required before the affected state is resolved.
        The original Operation remains intact; follow-up repair is recorded
        as linked subsequent activity.

        Args:
            op_uuid: UUID of the Operation.
            error_category: Coarse error category.
            error_code: Stable error code.
            summary: Human-readable summary.
            error_details: Free-text diagnostic detail.
            repair_state: Current state of the associated repair case.
            recovery_context: Instructions for recovery.

        Returns:
            Updated normalised Operation dict.

        Raises:
            ServiceNotFound: When *op_uuid* does not exist.
        """
        op = self._repo.get_by_uuid(op_uuid)
        if op is None:
            raise ServiceNotFound(f"Operation not found: {op_uuid}")
        self._repo.set_status(
            op_uuid,
            OP_STATUS_NEEDS_REPAIR,
            summary=summary,
            error_category=error_category,
            error_code=error_code,
            error_details=error_details,
            repair_state=repair_state,
            recovery_context=recovery_context,
        )
        return self._repo.get_by_uuid(op_uuid)

    def cancel(self, op_uuid: str, summary: str | None = None) -> dict:
        """Mark an Operation as ``Cancelled`` and return its updated record.

        Args:
            op_uuid: UUID of the Operation.
            summary: Optional cancellation reason.

        Returns:
            Updated normalised Operation dict.

        Raises:
            ServiceNotFound: When *op_uuid* does not exist.
        """
        op = self._repo.get_by_uuid(op_uuid)
        if op is None:
            raise ServiceNotFound(f"Operation not found: {op_uuid}")
        self._repo.set_status(op_uuid, OP_STATUS_CANCELLED, summary=summary)
        return self._repo.get_by_uuid(op_uuid)
