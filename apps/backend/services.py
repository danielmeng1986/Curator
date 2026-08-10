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
import os
import shutil
import uuid as _uuid_mod
import hashlib
import hmac
import secrets
import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:  # Package execution: python3 -m apps.backend
    from . import canonical_path as cpath
    from . import repositories as repo
except ImportError:  # Focused test discovery still loads sibling modules directly.
    import canonical_path as cpath
    import repositories as repo

# Import Action constants — passed by callers to ImportService.execute().
IMPORT_ACTION_DATABASE_ONLY: str = "DATABASE_ONLY"
IMPORT_ACTION_COPY: str = "COPY"
IMPORT_ACTION_MOVE: str = "MOVE"
IMPORT_ACTIONS: frozenset[str] = frozenset({
    IMPORT_ACTION_DATABASE_ONLY, IMPORT_ACTION_COPY, IMPORT_ACTION_MOVE,
})

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

    def __init__(self, required_scope: str, code: str = "AUTHORIZATION_INSUFFICIENT_SCOPE",
                 message: str = "The token does not have the required permission."):
        super().__init__(message)
        self.code = code
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
AUTH_BOOTSTRAP_CODE_VALIDITY = timedelta(minutes=10)
AUTH_BOOTSTRAP_MAX_ATTEMPTS = 5


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
        # Compare bytes rather than Unicode strings.  ``compare_digest``
        # rejects non-ASCII string inputs, but an invalid registration proof
        # must be a normal authentication failure rather than an unhandled
        # transport error.
        proof_matches = bool(self._registration_secret) and hmac.compare_digest(
            registration_proof.encode("utf-8"),
            self._registration_secret.encode("utf-8"),
        )
        if not proof_matches:
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

    def bootstrap_first_admin(
        self,
        *,
        device_name: str,
        device_identity: str,
        validity: timedelta | None = None,
    ) -> dict:
        """Issue the first Admin Token under the local-console trust boundary."""
        if not all(isinstance(value, str) and value.strip() for value in (device_name, device_identity)):
            raise ValueError("Device name and stable device identity are required.")
        lifetime = validity or AUTH_DEFAULT_TOKEN_VALIDITY
        if lifetime <= timedelta(0):
            raise ValueError("Token validity must be positive.")
        now = self._now_utc()
        if self._repo.has_bootstrapped_admin():
            raise ServiceConflict(
                "AUTHENTICATION_BOOTSTRAP_CLOSED",
                "Administrator bootstrap is closed because an Admin has already been established.",
            )
        plaintext = secrets.token_urlsafe(32)
        registration_uuid = str(_uuid_mod.uuid4())
        token_uuid = str(_uuid_mod.uuid4())
        registration = {
            "uuid": registration_uuid,
            "device_name": device_name.strip(),
            "device_identity": device_identity.strip(),
            "scopes": sorted(AUTH_ROLE_SCOPES["admin"]),
        }
        token = {
            "uuid": token_uuid,
            "token_hash": self._hash_token(plaintext),
            "created_at": now.isoformat(),
            "expires_at": (now + lifetime).isoformat(),
        }
        try:
            persisted_registration, persisted_token = self._repo.bootstrap_first_admin(
                registration, token, now.isoformat()
            )
        except repo.PersistenceConflict as exc:
            raise ServiceConflict(
                "AUTHENTICATION_BOOTSTRAP_CLOSED",
                "Administrator bootstrap is closed because an Admin has already been established.",
                exc.details,
            )
        try:
            self._record_operation(
                "administrator_bootstrap",
                registration_uuid,
                "Initial administrator device and Token issued from the local console.",
            )
        except Exception:
            self._repo.rollback_bootstrap(registration_uuid, token_uuid)
            raise
        persisted_token.pop("token_hash", None)
        return {
            "token": plaintext,
            "token_record": persisted_token,
            "registration": persisted_registration,
        }

    def bootstrap_status(self) -> dict:
        initialized = self._repo.has_bootstrapped_admin()
        current = None if initialized else self._repo.get_current_bootstrap_code()
        now = self._now_utc()
        code_available = bool(
            current
            and current["used_at"] is None
            and current["locked_at"] is None
            and datetime.fromisoformat(current["expires_at"]) > now
        )
        return {"initialized": initialized, "code_available": code_available}

    def create_bootstrap_code(self, *, validity: timedelta | None = None) -> dict:
        """Create one console-disclosed, short-lived Code for loopback bootstrap."""
        if self._repo.has_bootstrapped_admin():
            raise ServiceConflict(
                "AUTHENTICATION_BOOTSTRAP_CLOSED",
                "Administrator bootstrap is closed because an Admin has already been established.",
            )
        lifetime = validity or AUTH_BOOTSTRAP_CODE_VALIDITY
        if lifetime <= timedelta(0) or lifetime > AUTH_BOOTSTRAP_CODE_VALIDITY:
            raise ValueError("Bootstrap Code validity must be between zero and ten minutes.")
        now = self._now_utc()
        plaintext = secrets.token_urlsafe(12)
        record = self._repo.create_bootstrap_code({
            "uuid": str(_uuid_mod.uuid4()),
            "code_hash": self._hash_token(plaintext),
            "created_at": now.isoformat(),
            "expires_at": (now + lifetime).isoformat(),
        })
        return {"code": plaintext, "record": record}

    def complete_bootstrap_with_code(
        self,
        *,
        code: str,
        device_name: str,
        device_identity: str,
    ) -> dict:
        """Consume the active Code and establish the first Admin device."""
        now = self._now_utc()
        if self._repo.has_bootstrapped_admin():
            self._record_operation(
                "administrator_bootstrap_rejected", "bootstrap",
                "Administrator UI bootstrap was rejected because initialization is closed.",
            )
            raise ServiceConflict("AUTHENTICATION_BOOTSTRAP_CLOSED", "Administrator bootstrap is closed.")
        current = self._repo.get_current_bootstrap_code()
        if current is None:
            raise AuthenticationFailure("AUTHENTICATION_BOOTSTRAP_CODE_REQUIRED", "A current Bootstrap Code is required.")
        expires_at = datetime.fromisoformat(current["expires_at"])
        if current["locked_at"] is not None:
            raise AuthenticationFailure("AUTHENTICATION_BOOTSTRAP_CODE_LOCKED", "The Bootstrap Code is locked.")
        if expires_at <= now:
            self._record_operation(
                "administrator_bootstrap_rejected", current["uuid"],
                "Administrator UI bootstrap was rejected because the Code expired.",
            )
            raise AuthenticationFailure("AUTHENTICATION_BOOTSTRAP_CODE_EXPIRED", "The Bootstrap Code has expired.")
        supplied_hash = self._hash_token(code if isinstance(code, str) else "")
        if not hmac.compare_digest(supplied_hash, current["code_hash"]):
            failed = self._repo.fail_bootstrap_code(current["uuid"], now.isoformat(), AUTH_BOOTSTRAP_MAX_ATTEMPTS)
            self._record_operation(
                "administrator_bootstrap_rejected", current["uuid"],
                "Administrator UI bootstrap was rejected because the Code was invalid.",
            )
            error_code = "AUTHENTICATION_BOOTSTRAP_CODE_LOCKED" if failed and failed["locked_at"] else "AUTHENTICATION_INVALID_BOOTSTRAP_CODE"
            raise AuthenticationFailure(error_code, "The Bootstrap Code is invalid or locked.")
        issued = self.bootstrap_first_admin(
            device_name=device_name,
            device_identity=device_identity,
        )
        if not self._repo.consume_bootstrap_code(current["uuid"], now.isoformat()):
            raise ServiceConflict("AUTHENTICATION_BOOTSTRAP_CODE_USED", "The Bootstrap Code is no longer available.")
        return issued

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
        requested_role = registration["requested_role"]
        role_order = {"reader": 0, "writer": 1, "admin": 2}
        candidate_role = approved_role or requested_role
        if candidate_role not in role_order or role_order[candidate_role] > role_order[requested_role]:
            raise ServiceConflict("AUTHORIZATION_ELEVATION_NOT_REQUESTED", "Approval cannot exceed the requested role.")
        candidate_scopes = approved_scopes if approved_scopes is not None else registration["requested_scopes"]
        if not set(candidate_scopes).issubset(set(registration["requested_scopes"])):
            raise ServiceConflict("AUTHORIZATION_SCOPE_NOT_REQUESTED", "Approval cannot exceed requested scopes.")
        role, scopes = self._validate_role_and_scopes(
            candidate_role, candidate_scopes,
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
        self._record_operation("device_registration_rejection", registration_uuid, "Device registration rejected.")

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
        used_at = self._now_utc().isoformat()
        self._repo.touch_token(token["uuid"], used_at)
        renewal = self._repo.get_pending_renewal_for_token(token["uuid"])
        return {
            "device_name": token["device_name"],
            "device_identity": registration["device_identity"],
            "registration_uuid": token["registration_uuid"],
            "token_uuid": token["uuid"],
            "scopes": token["scopes"],
            "role": registration["approved_role"],
            "created_at": token["created_at"],
            "expires_at": token["expires_at"],
            "last_used_at": used_at,
            "renewal": renewal,
        }

    def request_renewal(self, token_plaintext: str, *, device_identity: str) -> dict:
        principal = self.authenticate(token_plaintext)
        registration = self._repo.get_registration(principal["registration_uuid"])
        if registration is None or registration["device_identity"] != device_identity:
            raise AuthenticationFailure("AUTHENTICATION_INVALID_DEVICE", "The device identity does not match the token.")
        old_token = self._repo.get_token_by_hash(self._hash_token(token_plaintext))
        existing = self._repo.get_pending_renewal_for_token(old_token["uuid"])
        if existing is not None:
            raise ServiceConflict(
                "BUSINESS_CONFLICT",
                "A renewal request is already pending for this Token.",
                {"renewal_uuid": existing["uuid"]},
            )
        renewal = self._repo.create_renewal_request({
            "registration_uuid": registration["uuid"], "previous_token_uuid": old_token["uuid"],
            "requested_role": registration["approved_role"], "requested_scopes": registration["approved_scopes"],
        })
        self._record_operation(
            "device_token_renewal", renewal["uuid"], "Device Token renewal requested."
        )
        return renewal

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
        self._record_operation("device_token_renewal_approval", renewal_uuid, "Device Token renewal approved and previous Token replaced.")
        return issued

    def reject_renewal(self, renewal_uuid: str) -> None:
        renewal = self._repo.get_renewal_request(renewal_uuid)
        if renewal is None: raise ServiceNotFound("Token renewal request not found.")
        if renewal["status"] != "PendingApproval": raise ServiceConflict("BUSINESS_CONFLICT", "The renewal request is no longer awaiting approval.")
        self._repo.reject_renewal(renewal_uuid)
        self._record_operation("device_token_renewal_rejection", renewal_uuid, "Device Token renewal rejected.")

    def revoke_token(self, token_uuid: str) -> None:
        try:
            revoked = self._repo.revoke_token_preserving_admin(token_uuid, self._now_utc().isoformat())
        except repo.PersistenceConflict as exc:
            raise ServiceConflict("LAST_USABLE_ADMIN", "The final usable Admin Token cannot be revoked.", exc.details) from exc
        if not revoked: raise ServiceNotFound("Active token not found.")
        self._record_operation("device_token_revocation", token_uuid, "Device token revoked.")

    def admin_read_model(self) -> dict:
        return {"registrations": self._repo.list_registrations(), "tokens": self._repo.list_tokens(),
                "renewals": self._repo.list_renewals()}


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

    BATCH_FIELDS = frozenset({
        "studio_id", "status_id", "rating", "description", "scene", "location",
        "capture_date", "publish_date", "remark",
    })

    def __init__(
        self, album_repo: repo.AlbumRepository, log_fn,
        *, preview_secret: bytes | None = None, operation_service=None,
        initiator: str = "WebUI",
    ):
        self._repo = album_repo
        self._log = log_fn
        self._preview_secret = preview_secret
        self._operations = operation_service
        self._initiator = initiator

    def _validate_relationships(self, album_id: int | None, models: list, relations: list) -> None:
        model_ids = [item.get("model_id") for item in models]
        related_ids = [item.get("related_album_id") for item in relations]
        if any(not isinstance(value, int) for value in model_ids + related_ids):
            raise ValueError("Relationship identifiers must be integers.")
        if len(model_ids) != len(set(model_ids)):
            raise ServiceConflict("ALBUM_MODEL_DUPLICATE", "A Model can appear only once in an Album.")
        relation_keys = [
            (item["related_album_id"], item.get("relation_type") or "BELONGS_TO")
            for item in relations
        ]
        if len(relation_keys) != len(set(relation_keys)):
            raise ServiceConflict("ALBUM_RELATION_DUPLICATE", "The Album relationship already exists.")
        if album_id is not None and album_id in related_ids:
            raise ServiceConflict("ALBUM_RELATION_SELF", "An Album cannot relate to itself.")
        found_models, found_albums = self._repo.relationship_targets_exist(
            set(model_ids), set(related_ids)
        )
        missing_models = sorted(set(model_ids) - found_models)
        missing_albums = sorted(set(related_ids) - found_albums)
        if missing_models or missing_albums:
            raise ValueError(
                f"Relationship targets do not exist: models={missing_models}, albums={missing_albums}."
            )

    def create(self, data: dict, models: list, relations: list) -> int:
        """Create an album with associated models and relations atomically.

        Returns:
            The new album's integer id.
        """
        if not str(data.get("title") or "").strip():
            raise ValueError("Album title is required.")
        self._validate_relationships(None, models, relations)
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
        if not str(data.get("title") or "").strip():
            raise ValueError("Album title is required.")
        if self._repo.get_by_id(album_id) is None:
            raise ServiceNotFound("Album not found.")
        self._validate_relationships(album_id, models, relations)
        now = _utc_now_iso()
        self._repo.update(album_id, data, models, relations, now)
        self._log(
            {"timestamp": now, "action": "update_album", "album_id": album_id, "success": True}
        )

    @staticmethod
    def _non_empty(value) -> bool:
        return value not in (None, "")

    def _validated_batch_request(self, album_ids: list, changes: dict) -> tuple[list[int], dict]:
        if not album_ids or any(not isinstance(value, int) for value in album_ids):
            raise ValueError("Album ids must be a non-empty list of integers.")
        ids = sorted(set(album_ids))
        if len(ids) != len(album_ids):
            raise ValueError("Album ids must not contain duplicates.")
        unknown = set(changes) - self.BATCH_FIELDS
        if not changes or unknown:
            raise ValueError(f"Unsupported Album batch fields: {sorted(unknown)}.")
        return ids, {key: changes[key] for key in sorted(changes)}

    def _sign_preview(self, payload: dict) -> str:
        if not self._preview_secret:
            raise RuntimeError("Album batch preview signing is not configured.")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        encoded = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        signature = hmac.new(self._preview_secret, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def _read_preview(self, token: str) -> dict:
        if not self._preview_secret or "." not in token:
            raise ServiceConflict("ALBUM_BATCH_PREVIEW_INVALID", "The Album batch preview is invalid.")
        encoded, signature = token.rsplit(".", 1)
        expected = hmac.new(self._preview_secret, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ServiceConflict("ALBUM_BATCH_PREVIEW_INVALID", "The Album batch preview is invalid.")
        try:
            raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
            payload = json.loads(raw)
            if datetime.fromisoformat(payload["expires_at"]) <= datetime.now(timezone.utc):
                raise ServiceConflict("ALBUM_BATCH_PREVIEW_EXPIRED", "The Album batch preview has expired.")
            return payload
        except ServiceConflict:
            raise
        except Exception as exc:
            raise ServiceConflict("ALBUM_BATCH_PREVIEW_INVALID", "The Album batch preview is invalid.") from exc

    def preview_batch(self, album_ids: list, changes: dict, *, overwrite_non_empty: bool = False) -> dict:
        ids, normalized = self._validated_batch_request(album_ids, changes)
        rows = self._repo.get_batch_state(ids)
        if len(rows) != len(ids):
            found = {row["id"] for row in rows}
            raise ValueError(f"Albums do not exist: {sorted(set(ids) - found)}.")
        items = []
        for row in rows:
            conflicts = [
                field for field, value in normalized.items()
                if self._non_empty(row.get(field)) and row.get(field) != value
            ]
            items.append({
                "album_id": row["id"], "album_uuid": row["uuid"], "title": row["title"],
                "changes": normalized, "non_empty_overwrites": conflicts,
                "eligible": overwrite_non_empty or not conflicts,
            })
        payload = {
            "ids": ids, "changes": normalized, "overwrite_non_empty": bool(overwrite_non_empty),
            "versions": {str(row["id"]): row["updated_at"] for row in rows},
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        }
        return {
            "preview_token": self._sign_preview(payload), "items": items,
            "summary": {"total": len(items), "eligible": sum(item["eligible"] for item in items),
                        "blocked": sum(not item["eligible"] for item in items)},
        }

    def execute_batch(self, preview_token: str) -> dict:
        payload = self._read_preview(preview_token)
        current_rows = self._repo.get_batch_state(payload["ids"])
        current_versions = {str(row["id"]): row["updated_at"] for row in current_rows}
        if current_versions != payload["versions"]:
            raise ServiceConflict("ALBUM_BATCH_STALE", "Album data changed after preview.")
        if not payload["overwrite_non_empty"]:
            current = self.preview_batch(payload["ids"], payload["changes"])
            if current["summary"]["blocked"]:
                raise ServiceConflict(
                    "ALBUM_BATCH_OVERWRITE_NOT_REVIEWED",
                    "The batch would overwrite non-empty Album fields.",
                    {"blocked": current["summary"]["blocked"]},
                )
        operation = None
        if self._operations:
            operation = self._operations.begin(
                "AlbumBatchUpdate", self._initiator, batch_uuid=str(_uuid_mod.uuid4()),
                summary=f"Updating {len(payload['ids'])} Albums",
            )
        try:
            rows = self._repo.batch_update(
                payload["ids"], payload["changes"],
                {int(key): value for key, value in payload["versions"].items()}, _utc_now_iso(),
            )
        except repo.PersistenceConflict as exc:
            if operation:
                self._operations.fail(operation["uuid"], "database", "album.batch-stale", summary="Album batch rejected as stale")
            raise ServiceConflict("ALBUM_BATCH_STALE", "Album data changed after preview.", exc.details) from exc
        except Exception:
            if operation:
                self._operations.fail(
                    operation["uuid"], "database", "album.batch-failed",
                    summary="Album batch update failed",
                )
            raise
        if operation:
            operation = self._operations.succeed(operation["uuid"], f"Updated {len(rows)} Albums")
        return {
            "items": [{"album_id": row["id"], "status": "Succeeded", "operation_uuid": operation["uuid"] if operation else None} for row in rows],
            "summary": {"total": len(rows), "succeeded": len(rows), "failed": 0},
            "operation_uuid": operation["uuid"] if operation else None,
        }

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
        preview_secret: bytes | None = None,
    ):
        self._repo = import_repo
        self._snapshot = snapshot_fn
        self._backup_log = backup_log_fn
        self._change_log = change_log_fn
        self._operations = operation_service
        self._initiator = initiator
        self._preview_secret = preview_secret

    @staticmethod
    def _source_fingerprint(source_path: str) -> dict:
        """Return deterministic source state without serializing it to public results."""
        if not source_path:
            return {"exists": False, "kind": "absent", "digest": None}
        source = Path(source_path)
        if not source.exists():
            return {"exists": False, "kind": "missing", "digest": None}
        entries = []
        if source.is_dir():
            for item in sorted(source.rglob("*"), key=lambda value: str(value.relative_to(source))):
                stat = item.stat()
                entries.append([
                    str(item.relative_to(source)), "dir" if item.is_dir() else "file",
                    stat.st_size, stat.st_mtime_ns,
                ])
            kind = "directory"
        else:
            stat = source.stat()
            entries.append([source.name, "file", stat.st_size, stat.st_mtime_ns])
            kind = "file"
        digest = hashlib.sha256(
            json.dumps(entries, ensure_ascii=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {"exists": True, "kind": kind, "digest": digest}

    def _sign_import_preview(self, payload: dict) -> str:
        if not self._preview_secret:
            raise RuntimeError("Import preview signing is not configured.")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        encoded = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        signature = hmac.new(self._preview_secret, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def _read_import_preview(self, token: str) -> dict:
        if not self._preview_secret or "." not in token:
            raise ServiceConflict("IMPORT_PREVIEW_INVALID", "The Import preview is invalid.")
        encoded, signature = token.rsplit(".", 1)
        expected = hmac.new(self._preview_secret, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ServiceConflict("IMPORT_PREVIEW_INVALID", "The Import preview is invalid.")
        try:
            payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if datetime.fromisoformat(payload["expires_at"]) <= datetime.now(timezone.utc):
                raise ServiceConflict("IMPORT_PREVIEW_EXPIRED", "The Import preview has expired.")
            return payload
        except ServiceConflict:
            raise
        except Exception as exc:
            raise ServiceConflict("IMPORT_PREVIEW_INVALID", "The Import preview is invalid.") from exc

    def preview(
        self, items: list, archive_root: str, default_studio: str,
        import_action: str | None = None,
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
        if import_action is not None and import_action not in IMPORT_ACTIONS:
            raise ValueError("Import Action must be COPY, MOVE, or DATABASE_ONLY.")
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
            source_state = self._source_fingerprint(n["source_path"])
            if import_action in {IMPORT_ACTION_COPY, IMPORT_ACTION_MOVE} and not source_state["exists"]:
                errors.append(
                    {"code": "SOURCE_NOT_FOUND", "message": "The selected source no longer exists."}
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
                        if source_at_canonical_destination else import_action
                    ),
                    "can_import": not errors,
                }
            )

        total = len(preview_items)
        importable = sum(1 for x in preview_items if x["can_import"])
        result = {
            "items": preview_items,
            "summary": {
                "total": total,
                "importable": importable,
                "skipped": total - importable,
            },
        }
        if self._preview_secret and import_action is not None and importable:
            token_items = [
                {
                    "folder_name": item["folder_name"], "model_name": item["model_name"],
                    "album_name": item["album_name"], "studio_name": item["studio_name"],
                    "source_path": item["source_path"], "expected_path": item["expected_path"],
                    "source_state": self._source_fingerprint(item["source_path"]),
                }
                for item in preview_items if item["can_import"]
            ]
            payload = {
                "preview_uuid": str(_uuid_mod.uuid4()), "items": token_items,
                "import_action": import_action,
                "archive_root": str(Path(archive_root).resolve()),
                "default_studio": default_studio,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            }
            result["preview_token"] = self._sign_import_preview(payload)
            result["preview_uuid"] = payload["preview_uuid"]
            result["expires_at"] = payload["expires_at"]
            result["import_action"] = import_action
        return result

    def execute_preview(self, preview_token: str, archive_root: str, default_studio: str) -> dict:
        """Revalidate, claim, and execute exactly one reviewed Import preview."""
        payload = self._read_import_preview(preview_token)
        if self._repo.preview_is_claimed(payload["preview_uuid"]):
            raise ServiceConflict("IMPORT_PREVIEW_REPLAYED", "The Import preview was already used.")
        if str(Path(archive_root).resolve()) != payload["archive_root"] or default_studio != payload["default_studio"]:
            raise ServiceConflict("IMPORT_PREVIEW_STALE", "Import configuration changed after preview.")
        executable_items = []
        for item in payload["items"]:
            if self._source_fingerprint(item["source_path"]) != item["source_state"]:
                raise ServiceConflict("IMPORT_PREVIEW_STALE", "An Import source changed after preview.")
            executable_items.append({key: item[key] for key in (
                "folder_name", "model_name", "album_name", "studio_name", "source_path"
            )})
        revalidated = self.preview(
            executable_items, archive_root, default_studio,
            import_action=payload["import_action"],
        )
        if len(revalidated["items"]) != len(executable_items) or any(
            not item["can_import"] for item in revalidated["items"]
        ):
            raise ServiceConflict("IMPORT_PREVIEW_STALE", "Import state changed after preview.")
        try:
            self._repo.claim_preview(payload["preview_uuid"], _utc_now_iso())
        except repo.PersistenceConflict as exc:
            raise ServiceConflict("IMPORT_PREVIEW_REPLAYED", "The Import preview was already used.", exc.details) from exc
        return self.execute(
            executable_items, archive_root, default_studio,
            import_action=payload["import_action"],
        )

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


class AIModelConfigurationService:
    """Validate and manage portable llama.cpp execution configurations."""

    REQUIRED = ("name", "model_identifier", "model_file", "vision_prompt_version", "writer_prompt_version",
                "sample_count", "context_size", "threads", "gpu_layers", "max_tokens", "temperature", "image_max_tokens")

    def __init__(self, config_repo, operation_service=None):
        self._repo, self._operations = config_repo, operation_service

    def _validated(self, fields):
        for key in self.REQUIRED:
            if fields.get(key) in (None, ""): raise ValueError(f"{key} is required.")
        text_limits = {"name": 120, "model_identifier": 200, "model_repository": 300, "model_file": 300,
                       "vision_prompt_version": 100, "writer_prompt_version": 100}
        for key, limit in text_limits.items():
            value = str(fields.get(key) or "").strip()
            if len(value) > limit: raise ValueError(f"{key} is too long.")
            if key in {"model_file", "model_repository"} and (value.startswith(("/", "\\")) or ":\\" in value):
                raise ValueError(f"{key} must be portable and cannot be an absolute path.")
            fields[key] = value or None
        bounds = {"sample_count": (1,32), "context_size": (512,262144), "threads": (1,256),
                  "gpu_layers": (0,999), "max_tokens": (1,32768), "temperature": (0,2),
                  "image_max_tokens": (1,8192)}
        for key, (low, high) in bounds.items():
            value = fields[key]
            if isinstance(value, bool) or not isinstance(value, (int,float)) or not low <= value <= high:
                raise ValueError(f"{key} must be between {low} and {high}.")
        extra = fields.get("additional_parameters", {})
        if not isinstance(extra, dict) or len(json.dumps(extra)) > 4000: raise ValueError("additional_parameters must be a bounded object.")
        forbidden = ("path", "token", "secret", "password", "cli", "executable")
        if any(any(word in str(key).lower() for word in forbidden) for key in extra):
            raise ValueError("additional_parameters contains a host path or secret field.")
        fields["provider_type"] = "llama_cpp"; fields["additional_parameters_json"] = json.dumps(extra, sort_keys=True)
        fields["updated_at"] = _utc_now_iso()
        return fields

    def create(self, fields):
        item = self._repo.create(self._validated(dict(fields)))
        self._record("ai_model_configuration_create", item, "AI model configuration created")
        return item

    def list(self, admin=False): return self._repo.list(enabled_only=not admin)

    def get(self, config_uuid, admin=False):
        item = self._repo.get(config_uuid)
        if not item or (not admin and not item["enabled"]): raise ServiceNotFound("AI model configuration not found.")
        return item

    def update(self, config_uuid, expected_version, fields):
        current = self.get(config_uuid, admin=True)
        if current["version"] != expected_version: raise ServiceConflict("AI_MODEL_CONFIGURATION_STALE", "The configuration changed after it was read.")
        merged = {key: current.get(key) for key in self.REQUIRED + ("model_repository",)}
        merged["additional_parameters"] = current["additional_parameters"]; merged.update(fields)
        updated = self._repo.update(config_uuid, expected_version, self._validated(merged))
        if not updated: raise ServiceConflict("AI_MODEL_CONFIGURATION_STALE", "The configuration changed during update.")
        self._record("ai_model_configuration_update", updated, "AI model configuration updated"); return updated

    def set_enabled(self, config_uuid, expected_version, enabled):
        current = self.get(config_uuid, admin=True)
        if current["version"] != expected_version: raise ServiceConflict("AI_MODEL_CONFIGURATION_STALE", "The configuration changed after it was read.")
        updated = self._repo.set_enabled(config_uuid, expected_version, enabled, _utc_now_iso())
        if not updated: raise ServiceConflict("AI_MODEL_CONFIGURATION_STALE", "The configuration changed during update.")
        self._record("ai_model_configuration_enable" if enabled else "ai_model_configuration_disable", updated, "AI model configuration availability changed")
        return updated

    def snapshot(self, config_uuid):
        item = self.get(config_uuid)
        return {key: value for key, value in item.items() if key not in {"id", "created_at", "updated_at"}}

    def _record(self, operation_type, item, summary):
        if self._operations:
            op = self._operations.begin(operation_type, OP_INITIATOR_WEB_UI, entity_uuid=item["uuid"], summary=summary)
            self._operations.succeed(op["uuid"], summary=summary)


class AIWorkItemService:
    """Own Album AI queue creation, Worker leases, failures, cancellation and retry."""

    def __init__(self, item_repo, workspace_repo, album_repo, configuration_service, operation_service=None, now_fn=None):
        self._repo, self._workspaces, self._albums = item_repo, workspace_repo, album_repo
        self._configs, self._operations = configuration_service, operation_service
        self._now = now_fn or (lambda: datetime.now(timezone.utc))

    def create(self, workspace_uuid, album_id, configuration_uuid):
        workspace = self._workspaces.get(workspace_uuid)
        if not workspace: raise ServiceNotFound("AI Workspace not found.")
        if workspace["lifecycle_state"] != "Open": raise ServiceConflict("AI_WORKSPACE_NOT_OPEN", "New Work Items require an Open AI Workspace.")
        if not isinstance(album_id, int) or not self._albums.get_by_id(album_id): raise ServiceNotFound("Album not found.")
        snapshot = self._configs.snapshot(configuration_uuid)
        item = self._repo.create({"workspace_uuid":workspace_uuid, "album_id":album_id,
            "ai_model_configuration_uuid":configuration_uuid,
            "configuration_snapshot_json":json.dumps(snapshot, sort_keys=True), "created_at":self._now().isoformat()})
        self._record("ai_work_item_create", item, "Album AI Work Item queued"); return item

    def list(self, workspace_uuid):
        if not self._workspaces.get(workspace_uuid): raise ServiceNotFound("AI Workspace not found.")
        return self._repo.list(workspace_uuid)

    def get(self, item_uuid, include_attempts=False):
        item = self._repo.get(item_uuid)
        if not item: raise ServiceNotFound("AI Work Item not found.")
        if include_attempts: item["attempts"] = self._repo.attempts(item_uuid)
        return item

    def claim_next(self, worker_token_uuid, lease_seconds=300):
        if not isinstance(lease_seconds, int) or not 60 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be an integer from 60 to 3600.")
        now = self._now(); item = self._repo.claim_next(worker_token_uuid, now.isoformat(),
            (now + timedelta(seconds=lease_seconds)).isoformat())
        if item: self._record("ai_work_item_claim", item, f"AI Worker claimed attempt {item['attempt_count']}", OP_INITIATOR_AI_WORKER)
        return item

    def heartbeat(self, item_uuid, worker_token_uuid, lease_seconds=300):
        if not isinstance(lease_seconds, int) or not 60 <= lease_seconds <= 3600: raise ValueError("lease_seconds must be an integer from 60 to 3600.")
        now = self._now(); item = self._repo.heartbeat(item_uuid, worker_token_uuid, now.isoformat(),
            (now + timedelta(seconds=lease_seconds)).isoformat())
        if not item: raise ServiceConflict("AI_WORK_ITEM_CLAIM_INVALID", "The Worker does not own an active lease.")
        return item

    def fail(self, item_uuid, worker_token_uuid, error_code, message):
        if not re.fullmatch(r"[A-Z0-9_]{2,80}", str(error_code or "")): raise ValueError("error_code is invalid.")
        message = str(message or "").strip()
        if not message or len(message) > 1000: raise ValueError("error message must contain 1 to 1000 characters.")
        item = self._repo.fail(item_uuid, worker_token_uuid, self._now().isoformat(), error_code, message)
        if not item: raise ServiceConflict("AI_WORK_ITEM_CLAIM_INVALID", "The Worker does not own the claimed Item.")
        self._record("ai_work_item_fail", item, f"AI Work Item failed: {error_code}", OP_INITIATOR_AI_WORKER); return item

    def retry(self, item_uuid, expected_version):
        return self._admin_transition(item_uuid, expected_version, ("Failed",), "Pending", "ai_work_item_retry")

    def cancel(self, item_uuid, expected_version):
        return self._admin_transition(item_uuid, expected_version, ("Pending","Failed"), "Cancelled", "ai_work_item_cancel")

    def _admin_transition(self, item_uuid, expected_version, from_states, to_state, op_type):
        current = self.get(item_uuid)
        if current["version"] != expected_version or current["run_state"] not in from_states:
            raise ServiceConflict("AI_WORK_ITEM_STALE", "The Work Item state or version changed.", {"current":current})
        updated = self._repo.admin_transition(item_uuid, expected_version, from_states, to_state, self._now().isoformat())
        if not updated: raise ServiceConflict("AI_WORK_ITEM_STALE", "The Work Item changed during transition.")
        self._record(op_type, updated, f"AI Work Item transitioned to {to_state}"); return updated

    def _record(self, operation_type, item, summary, initiator=None):
        if self._operations:
            op = self._operations.begin(operation_type, initiator or "WebUI", entity_uuid=item["uuid"], summary=summary)
            self._operations.succeed(op["uuid"], summary=summary)


class AlbumNameAnalysisDispatchAdapter:
    """First Worker-kind adapter; result and Photo eligibility arrive later."""

    worker_kind = "album_name_analysis"
    dataset_type = "album_analysis"
    schema_version = 1
    item_kind = "workspace_album_ai_worker"

    def eligibility(self, album, context=None):
        if not album:
            return {"can_dispatch": False, "eligibility": "ALBUM_NOT_FOUND",
                    "reason": "Album not found.", "warnings": []}
        return {"can_dispatch": True, "eligibility": "ELIGIBLE",
                "reason": None, "warnings": []}


class WorkDispatchAdapterRegistry:
    """Stable Worker-kind lookup without coupling dispatch to Item schemas."""

    def __init__(self, adapters=None):
        adapters = adapters or (AlbumNameAnalysisDispatchAdapter(),)
        self._adapters = {adapter.worker_kind: adapter for adapter in adapters}
        if len(self._adapters) != len(adapters):
            raise ValueError("Worker kind registrations must be unique.")

    def get(self, worker_kind):
        adapter = self._adapters.get(str(worker_kind or ""))
        if not adapter:
            raise ValueError("worker_kind is not supported.")
        return adapter

    def describe(self):
        return [{"worker_kind": adapter.worker_kind, "dataset_type": adapter.dataset_type,
                 "schema_version": adapter.schema_version, "item_kind": adapter.item_kind}
                for adapter in self._adapters.values()]


class WorkDispatchService:
    """Foundation for generic Batches, exclusive Album Groups, and Item links."""

    FILTER_FIELDS = frozenset({"q", "studio_id", "status_id", "model_id", "rating_min", "rating_max",
        "capture_date_from", "capture_date_to", "publish_date_from", "publish_date_to", "sort"})
    SORT_FIELDS = frozenset({"title", "studio_name", "publish_date", "rating", "updated_at", "capture_date"})
    MAX_PREVIEW_ALBUMS = 100

    def __init__(self, dispatch_repo, album_repo, adapter_registry=None, now_fn=None,
                 workspace_repo=None, configuration_service=None, preview_secret=None):
        self._repo, self._albums = dispatch_repo, album_repo
        self._adapters = adapter_registry or WorkDispatchAdapterRegistry()
        self._now = now_fn or (lambda: datetime.now(timezone.utc))
        self._workspaces, self._configs = workspace_repo, configuration_service
        self._preview_secret = preview_secret

    def worker_kinds(self):
        return self._adapters.describe()

    def eligibility(self, worker_kind, album_id, context=None):
        adapter = self._adapters.get(worker_kind)
        if not isinstance(album_id, int):
            raise ValueError("album_id must be an integer.")
        result = adapter.eligibility(self._albums.get_by_id(album_id), context)
        reservation = self._repo.active_reservation(album_id)
        if reservation:
            return {"can_dispatch": False, "eligibility": "ALBUM_ALREADY_RESERVED",
                    "reason": "Album already belongs to an active Work Dispatch Group.",
                    "warnings": result.get("warnings", []), "active_reservation": reservation}
        return result

    def _normalized_filters(self, filters):
        if filters is None: return {}
        if not isinstance(filters, dict): raise ValueError("filters must be an object.")
        unknown = set(filters) - self.FILTER_FIELDS
        if unknown: raise ValueError(f"Unsupported dispatch filters: {sorted(unknown)}.")
        result = {key: str(value).strip() for key, value in filters.items() if value not in (None, "")}
        for key in ("capture_date_from", "capture_date_to", "publish_date_from", "publish_date_to"):
            if key in result:
                try: datetime.strptime(result[key], "%Y-%m-%d")
                except ValueError as exc: raise ValueError(f"{key} must use YYYY-MM-DD format.") from exc
        for prefix in ("capture_date", "publish_date"):
            if result.get(f"{prefix}_from") and result.get(f"{prefix}_to") and result[f"{prefix}_from"] > result[f"{prefix}_to"]:
                raise ValueError(f"{prefix}_from must not be later than {prefix}_to.")
        if result.get("sort", "updated_at") not in self.SORT_FIELDS:
            raise ValueError("sort is not supported.")
        return result

    def candidates(self, worker_kind, filters=None, *, availability="available", limit=50, offset=0):
        adapter = self._adapters.get(worker_kind); normalized = self._normalized_filters(filters)
        if not isinstance(limit, int) or not 1 <= limit <= 100 or not isinstance(offset, int) or offset < 0:
            raise ValueError("Candidate pagination is invalid.")
        if availability not in {"available", "reserved", "all"}:
            raise ValueError("availability must be available, reserved, or all.")
        self._repo.prepare()
        rows, total = self._albums.search(**normalized, limit=limit, offset=offset,
            dispatch_availability=availability, include_dispatch=True)
        for item in rows:
            base = adapter.eligibility(item)
            if item["active_reservation"]:
                item.update({"can_dispatch":False, "eligibility":"ALBUM_ALREADY_RESERVED",
                    "eligibility_reason":"Album already belongs to an active Work Dispatch Group.",
                    "warnings":base.get("warnings", [])})
            else:
                item.update({"can_dispatch":bool(base["can_dispatch"]), "eligibility":base["eligibility"],
                    "eligibility_reason":base.get("reason"), "warnings":base.get("warnings", [])})
        return {"items":rows, "total":total, "limit":limit, "offset":offset,
            "availability":availability, "filters":normalized, "worker_kind":adapter.worker_kind}

    def _sign_dispatch_preview(self, payload):
        if not self._preview_secret: raise RuntimeError("Work Dispatch preview signing is not configured.")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        encoded = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        signature = hmac.new(self._preview_secret, encoded.encode(), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def read_preview(self, token):
        if not self._preview_secret or not isinstance(token, str) or "." not in token:
            raise ServiceConflict("DISPATCH_PREVIEW_INVALID", "The Work Dispatch preview is invalid.")
        encoded, signature = token.rsplit(".", 1)
        expected = hmac.new(self._preview_secret, encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ServiceConflict("DISPATCH_PREVIEW_INVALID", "The Work Dispatch preview is invalid.")
        try:
            payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if datetime.fromisoformat(payload["expires_at"]) <= self._now():
                raise ServiceConflict("DISPATCH_PREVIEW_EXPIRED", "The Work Dispatch preview has expired.")
            return payload
        except ServiceConflict: raise
        except Exception as exc:
            raise ServiceConflict("DISPATCH_PREVIEW_INVALID", "The Work Dispatch preview is invalid.") from exc

    def validate_preview_state(self, token, created_by_token_uuid=None):
        """Verify the signed review still describes current zero-write state."""
        payload = self.read_preview(token)
        if created_by_token_uuid is not None and payload.get("created_by_token_uuid") != created_by_token_uuid:
            raise ServiceConflict("DISPATCH_PREVIEW_INVALID", "The Work Dispatch preview belongs to another Admin.")
        workspace = self._workspaces.get(payload["workspace"]["uuid"]) if self._workspaces else None
        if not workspace or workspace["version"] != payload["workspace"]["version"] \
                or workspace["lifecycle_state"] != payload["workspace"]["lifecycle_state"]:
            raise ServiceConflict("DISPATCH_PREVIEW_STALE", "Workspace state changed after dispatch preview.")
        try:
            configs = [self._configs.get(item["uuid"]) for item in payload["configurations"]]
        except ServiceNotFound as exc:
            raise ServiceConflict("DISPATCH_PREVIEW_STALE", "Model configuration changed after dispatch preview.") from exc
        if [item["version"] for item in configs] != [item["version"] for item in payload["configurations"]]:
            raise ServiceConflict("DISPATCH_PREVIEW_STALE", "Model configuration changed after dispatch preview.")
        rows = self._albums.get_batch_state([item["id"] for item in payload["albums"]])
        current = [{"id":row["id"], "uuid":row["uuid"], "updated_at":row["updated_at"]} for row in rows]
        if current != payload["albums"]:
            raise ServiceConflict("DISPATCH_PREVIEW_STALE", "Album state changed after dispatch preview.")
        conflicts = [item["id"] for item in payload["albums"] if self._repo.active_reservation(item["id"])]
        if conflicts:
            raise ServiceConflict("ALBUM_WORK_RESERVATION_CONFLICT",
                "An Album was reserved after dispatch preview.", {"album_ids":conflicts})
        return payload

    def preview(self, worker_kind, workspace_uuid, configuration_uuids, *, album_ids=None,
                filters=None, first_n=None, created_by_token_uuid=None):
        adapter = self._adapters.get(worker_kind)
        if not self._workspaces or not self._configs:
            raise RuntimeError("Work Dispatch preview dependencies are not configured.")
        workspace = self._workspaces.get(str(workspace_uuid or ""))
        if not workspace: raise ServiceNotFound("AI Workspace not found.")
        if workspace["lifecycle_state"] != "Open":
            raise ServiceConflict("AI_WORKSPACE_NOT_OPEN", "Dispatch preview requires an Open AI Workspace.")
        if workspace["dataset_type"] != adapter.dataset_type or workspace["schema_version"] != adapter.schema_version:
            raise ServiceConflict("DISPATCH_DATASET_MISMATCH", "Workspace Dataset does not match the Worker kind.")
        if not isinstance(configuration_uuids, list) or not configuration_uuids or any(not isinstance(x, str) or not x for x in configuration_uuids):
            raise ValueError("configuration_uuids must be a non-empty list.")
        if len(set(configuration_uuids)) != len(configuration_uuids):
            raise ValueError("configuration_uuids must not contain duplicates.")
        configurations = [self._configs.get(value) for value in configuration_uuids]

        normalized_filters = self._normalized_filters(filters)
        if album_ids is not None and first_n is not None:
            raise ValueError("Choose explicit album_ids or first_n, not both.")
        if album_ids is not None:
            if not isinstance(album_ids, list) or not album_ids or any(not isinstance(x, int) for x in album_ids):
                raise ValueError("album_ids must be a non-empty list of integers.")
            if len(set(album_ids)) != len(album_ids) or len(album_ids) > self.MAX_PREVIEW_ALBUMS:
                raise ValueError("album_ids must be unique and contain at most 100 Albums.")
            states = self._albums.get_batch_state(sorted(album_ids))
            if len(states) != len(album_ids): raise ValueError("One or more Albums do not exist.")
            selection = {"mode":"ids", "album_ids":sorted(album_ids)}
        else:
            if not isinstance(first_n, int) or not 1 <= first_n <= self.MAX_PREVIEW_ALBUMS:
                raise ValueError("first_n must be an integer from 1 to 100.")
            self._repo.prepare()
            rows, _ = self._albums.search(**normalized_filters, limit=first_n, offset=0,
                dispatch_availability="available", include_dispatch=True)
            states = self._albums.get_batch_state([row["id"] for row in rows])
            selection = {"mode":"first_n", "first_n":first_n, "filters":normalized_filters,
                "sort":normalized_filters.get("sort", "updated_at")}
        if not states: raise ValueError("The dispatch selection contains no Albums.")

        items, blocked = [], 0
        for row in states:
            result = self.eligibility(worker_kind, row["id"])
            can_dispatch = bool(result["can_dispatch"]); blocked += int(not can_dispatch)
            items.append({"album_id":row["id"], "album_uuid":row["uuid"], "title":row["title"],
                "can_dispatch":can_dispatch, "eligibility":result["eligibility"],
                "reason":result.get("reason"), "warnings":result.get("warnings", []),
                "expected_group_count":1, "expected_work_item_count":len(configurations)})
        now = self._now()
        payload = {"preview_uuid":str(_uuid_mod.uuid4()), "worker_kind":adapter.worker_kind,
            "dataset_type":adapter.dataset_type, "schema_version":adapter.schema_version,
            "workspace":{"uuid":workspace["uuid"], "version":workspace["version"], "lifecycle_state":workspace["lifecycle_state"]},
            "configurations":[{"uuid":item["uuid"], "version":item["version"]} for item in configurations],
            "albums":[{"id":row["id"], "uuid":row["uuid"], "updated_at":row["updated_at"]} for row in states],
            "selection":selection, "created_by_token_uuid":created_by_token_uuid,
            "issued_at":now.isoformat(), "expires_at":(now + timedelta(minutes=10)).isoformat()}
        response = {"preview_uuid":payload["preview_uuid"], "expires_at":payload["expires_at"],
            "worker_kind":adapter.worker_kind, "workspace":workspace,
            "configurations":configurations, "items":items,
            "summary":{"albums":len(items), "eligible":len(items)-blocked, "blocked":blocked,
                "groups":len(items), "work_items":len(items)*len(configurations)}, "selection":selection}
        if not blocked: response["preview_token"] = self._sign_dispatch_preview(payload)
        return response

    def execute(self, preview_token, created_by_token_uuid):
        payload = self.read_preview(preview_token)
        if payload.get("created_by_token_uuid") != created_by_token_uuid:
            raise ServiceConflict("DISPATCH_PREVIEW_INVALID", "The Work Dispatch preview belongs to another Admin.")
        adapter = self._adapters.get(payload.get("worker_kind"))
        if adapter.worker_kind != "album_name_analysis":
            raise ServiceConflict("DISPATCH_ADAPTER_NOT_EXECUTABLE", "The Worker adapter cannot execute this dispatch.")
        try:
            return self._repo.execute(payload, self._now().isoformat())
        except repo.PersistenceConflict as exc:
            code = exc.details.get("code", "ALBUM_WORK_RESERVATION_CONFLICT")
            messages = {"DISPATCH_PREVIEW_REPLAYED":"The Work Dispatch preview was already executed.",
                "DISPATCH_PREVIEW_STALE":"Dispatch state changed after preview.",
                "ALBUM_WORK_RESERVATION_CONFLICT":"An Album is already reserved."}
            raise ServiceConflict(code, messages.get(code, "Work Dispatch execution conflicted with current state."), exc.details) from exc

    def batch_detail(self, batch_uuid):
        result = self._repo.get_batch_detail(batch_uuid)
        if not result: raise ServiceNotFound("Work Dispatch Batch not found.")
        return result

    def create_batch(self, worker_kind, workspace_uuid=None, created_by_token_uuid=None):
        adapter = self._adapters.get(worker_kind)
        return self._repo.create_batch({"worker_kind": adapter.worker_kind,
            "dataset_type": adapter.dataset_type, "schema_version": adapter.schema_version,
            "workspace_uuid": workspace_uuid, "created_by_token_uuid": created_by_token_uuid,
            "created_at": self._now().isoformat()})

    def reserve_album(self, batch_uuid, album_id):
        batch = self._repo.get_batch(batch_uuid)
        if not batch:
            raise ServiceNotFound("Work Dispatch Batch not found.")
        adapter = self._adapters.get(batch["worker_kind"])
        eligible = self.eligibility(adapter.worker_kind, album_id)
        if not eligible["can_dispatch"]:
            raise ServiceConflict(eligible["eligibility"], eligible["reason"], eligible)
        try:
            return self._repo.reserve_album(batch_uuid, album_id,
                {"worker_kind": adapter.worker_kind, "dataset_type": adapter.dataset_type,
                 "schema_version": adapter.schema_version, "created_at": self._now().isoformat()})
        except repo.PersistenceConflict as exc:
            raise ServiceConflict("ALBUM_WORK_RESERVATION_CONFLICT",
                "Album already belongs to an active Work Dispatch Group.", exc.details) from exc

    def attach_item(self, group_uuid, item_uuid, configuration_uuid=None):
        group = self._repo.get_group(group_uuid)
        if not group:
            raise ServiceNotFound("Work Dispatch Group not found.")
        if group["group_state"] != "Active":
            raise ServiceConflict("WORK_GROUP_NOT_ACTIVE", "Work Items require an active Group.")
        adapter = self._adapters.get(group["worker_kind"])
        try:
            return self._repo.attach_item(group_uuid, adapter.item_kind, item_uuid,
                configuration_uuid, self._now().isoformat())
        except repo.PersistenceConflict as exc:
            raise ServiceConflict(exc.details["code"], "Work Item is already assigned to a Group.", exc.details) from exc


class AIPhotoEvidenceManifestService:
    """Discover, select, hash, persist, and revalidate Album evidence."""

    SUPPORTED = {".jpg":"image/jpeg", ".jpeg":"image/jpeg", ".png":"image/png", ".webp":"image/webp"}
    MAX_BYTES = 32 * 1024 * 1024
    SELECTION_METHOD = "mean-size-band-30pct-then-nearest-v1"

    def __init__(self, evidence_repo, item_repo, album_repo, archive_root, issue_repo=None, now_fn=None):
        self._repo, self._items, self._albums = evidence_repo, item_repo, album_repo
        self._root = Path(archive_root).resolve(); self._issues = issue_repo
        self._now = now_fn or (lambda:datetime.now(timezone.utc))

    @staticmethod
    def _mime(path):
        with path.open("rb") as stream: head = stream.read(16)
        if head.startswith(b"\xff\xd8\xff"): return "image/jpeg"
        if head.startswith(b"\x89PNG\r\n\x1a\n"): return "image/png"
        if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP": return "image/webp"
        return None

    def _album_root(self, album):
        raw = Path(str(album["album"].get("path") or ""))
        target = (raw if raw.is_absolute() else self._root / raw).resolve()
        try: target.relative_to(self._root)
        except ValueError as exc: raise ServiceConflict("EVIDENCE_PATH_INVALID", "Album path is outside the archive root.") from exc
        if not target.is_dir(): raise ServiceConflict("EVIDENCE_IMAGES_UNAVAILABLE", "Album directory is unavailable.")
        return target

    def _discover(self, root):
        accepted, excluded = [], {"unsupported":0,"oversized":0,"symlink":0,"unreadable":0}
        for base, dirs, files in os.walk(root, followlinks=False):
            base_path = Path(base)
            kept = []
            for name in sorted(dirs):
                path = base_path / name
                if path.is_symlink(): excluded["symlink"] += 1
                else: kept.append(name)
            dirs[:] = kept
            for name in sorted(files):
                path = base_path / name; suffix = path.suffix.lower()
                if path.is_symlink(): excluded["symlink"] += 1; continue
                if suffix not in self.SUPPORTED: excluded["unsupported"] += 1; continue
                try:
                    stat = path.stat()
                    if not path.is_file(): excluded["unsupported"] += 1; continue
                    if stat.st_size > self.MAX_BYTES: excluded["oversized"] += 1; continue
                    mime = self._mime(path)
                    if mime != self.SUPPORTED[suffix]: excluded["unsupported"] += 1; continue
                    relative = path.resolve().relative_to(root).as_posix()
                    accepted.append({"path":path,"relative_path":relative,"filename":path.name,
                        "size_bytes":stat.st_size,"modified_time_ns":stat.st_mtime_ns,"mime_type":mime})
                except (OSError, ValueError): excluded["unreadable"] += 1
        accepted.sort(key=lambda item:item["relative_path"].casefold())
        return accepted, excluded

    @staticmethod
    def _even(items, count):
        if count == 1: return [items[len(items)//2]]
        return [items[round(index*(len(items)-1)/(count-1))] for index in range(count)]

    def _report(self, item, code, message, eligible, required):
        issue = self._issues.create({"category":"AI Evidence", "description":message,
            "suggested_resolution":"Add or compress supported Album images, then rebuild the evidence Manifest.",
            "source_workflow":"AIPhotoEvidenceManifest", "priority":"High"}) if self._issues else None
        details = {"work_item_uuid":item["uuid"],"album_id":item["album_id"],
            "eligible_image_count":eligible,"required_sample_count":required}
        if issue: details["issue_uuid"] = issue["uuid"]
        raise ServiceConflict(code,message,details)

    def create(self, item_uuid):
        existing = self._repo.get_by_item(item_uuid)
        if existing: return self.revalidate(item_uuid)
        item = self._items.get(item_uuid)
        if not item: raise ServiceNotFound("AI Work Item not found.")
        if item["run_state"] not in {"Pending","Failed"}:
            raise ServiceConflict("EVIDENCE_MANIFEST_STATE_INVALID", "Evidence must be selected before Worker processing.")
        sample_count = int(item["configuration_snapshot"]["sample_count"])
        album = self._albums.get_by_id(item["album_id"])
        if not album: raise ServiceNotFound("Album not found.")
        try: root = self._album_root(album)
        except ServiceConflict as exc:
            if exc.code == "EVIDENCE_IMAGES_UNAVAILABLE":
                self._report(item,exc.code,str(exc),0,sample_count)
            raise
        images, excluded = self._discover(root)
        if not images: self._report(item,"EVIDENCE_IMAGES_UNAVAILABLE","Album contains no usable supported images.",0,sample_count)
        if len(images) < sample_count:
            self._report(item,"EVIDENCE_SAMPLE_INSUFFICIENT","Album contains fewer usable images than the configured sample count.",len(images),sample_count)
        mean = sum(item["size_bytes"] for item in images) / len(images); low, high = mean*.7, mean*1.3
        band = [item for item in images if low <= item["size_bytes"] <= high]
        if len(band) >= sample_count: selected = self._even(band,sample_count)
        else:
            chosen = list(band); used = {item["relative_path"] for item in chosen}
            remainder = sorted((item for item in images if item["relative_path"] not in used),
                key=lambda item:(abs(item["size_bytes"]-mean),item["relative_path"].casefold()))
            chosen.extend(remainder[:sample_count-len(chosen)]); chosen.sort(key=lambda item:item["relative_path"].casefold())
            selected = self._even(chosen,sample_count)
        evidence = []
        for selected_item in selected:
            digest = hashlib.sha256()
            with selected_item["path"].open("rb") as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b""): digest.update(chunk)
            after = selected_item["path"].stat()
            if after.st_size != selected_item["size_bytes"] or after.st_mtime_ns != selected_item["modified_time_ns"]:
                raise ServiceConflict("EVIDENCE_CONTENT_CHANGED","An evidence image changed during Manifest creation.")
            evidence.append({key:value for key,value in selected_item.items() if key != "path"} | {"sha256":digest.hexdigest()})
        return self._repo.create({"work_item_uuid":item_uuid,"album_id":item["album_id"],"sample_count":sample_count,
            "eligible_image_count":len(images),"average_size_bytes":mean,"selection_method":self.SELECTION_METHOD,
            "discovery_summary":{"eligible":len(images),**excluded},"selected_at":self._now().isoformat()}, evidence)

    def revalidate(self, item_uuid):
        manifest = self._repo.get_by_item(item_uuid)
        if not manifest: raise ServiceNotFound("Photo evidence Manifest not found.")
        album = self._albums.get_by_id(manifest["album_id"]); root = self._album_root(album)
        for item in manifest["evidence"]:
            path = (root / item["relative_path"]).resolve()
            try: path.relative_to(root)
            except ValueError as exc: raise ServiceConflict("EVIDENCE_CONTENT_CHANGED","Evidence path containment changed.") from exc
            if not path.is_file() or path.is_symlink(): raise ServiceConflict("EVIDENCE_CONTENT_CHANGED","An evidence image is missing or unsafe.")
            stat = path.stat()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if stat.st_size != item["size_bytes"] or stat.st_mtime_ns != item["modified_time_ns"] or digest != item["sha256"]:
                raise ServiceConflict("EVIDENCE_CONTENT_CHANGED","An evidence image changed after selection.",{"evidence_uuid":item["uuid"]})
        return manifest

    def _authorize_evidence(self, evidence_uuid, role, token_uuid):
        evidence = self._repo.get_evidence(evidence_uuid)
        if not evidence: raise ServiceNotFound("Photo evidence not found.")
        item = self._items.get(evidence["work_item_uuid"])
        if role != "admin":
            now = self._now().isoformat()
            if role != "writer" or item["run_state"] != "Claimed" \
                    or item["claimed_by_token_uuid"] != token_uuid or not item["lease_expires_at"] \
                    or item["lease_expires_at"] <= now:
                raise AuthorizationFailure("write", "EVIDENCE_CLAIM_REQUIRED",
                    "Photo evidence requires the Work Item's active Writer claim.")
        self.revalidate(evidence["work_item_uuid"])
        return evidence, item

    def metadata(self, evidence_uuid, role, token_uuid=None):
        evidence, item = self._authorize_evidence(evidence_uuid,role,token_uuid)
        return {key:evidence[key] for key in ("uuid","manifest_uuid","work_item_uuid","ordinal","filename",
            "size_bytes","sha256","mime_type")} | {"album_id":item["album_id"]}

    def content_descriptor(self, evidence_uuid, role, token_uuid=None):
        evidence, item = self._authorize_evidence(evidence_uuid,role,token_uuid)
        album = self._albums.get_by_id(item["album_id"]); root = self._album_root(album)
        path = (root / evidence["relative_path"]).resolve()
        extension = {"image/jpeg":".jpg","image/png":".png","image/webp":".webp"}[evidence["mime_type"]]
        return {"path":path,"size_bytes":evidence["size_bytes"],"mime_type":evidence["mime_type"],
            "sha256":evidence["sha256"],"filename":f"evidence-{evidence_uuid}{extension}"}


class AIResultSubmissionService:
    """Validate Manifest-bound Vision then Writer JSON and persist accepted stages."""

    VISION_SCHEMA = "curator://album-analysis/vision/v1"
    WRITER_SCHEMA = "curator://album-analysis/writer/v1"

    def __init__(self,result_repo,evidence_service,now_fn=None):
        self._repo,self._evidence = result_repo,evidence_service
        self._now = now_fn or (lambda:datetime.now(timezone.utc))

    @staticmethod
    def _text(value,name,limit):
        if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(char)<32 and char not in "\n\t" for char in value):
            raise ValueError(f"{name} must be a non-empty bounded string.")
        return value.strip()

    def _vision(self,payload):
        required = {"scene","people","location_environment","subjects","objects","actions","confidence","warnings"}
        if not isinstance(payload,dict) or set(payload) != required: raise ValueError("Vision result fields do not match schema v1.")
        result = {"scene":self._text(payload["scene"],"scene",500),
            "location_environment":self._text(payload["location_environment"],"location_environment",500)}
        people = payload["people"]
        if not isinstance(people,dict) or set(people) != {"minimum","maximum"} or any(isinstance(people[k],bool) or not isinstance(people[k],int) or not 0<=people[k]<=100 for k in people) or people["minimum"]>people["maximum"]:
            raise ValueError("people must contain a valid minimum/maximum range.")
        result["people"] = people
        for key,maximum in (("subjects",50),("objects",50),("actions",50),("warnings",20)):
            values = payload[key]
            if not isinstance(values,list) or len(values)>maximum: raise ValueError(f"{key} must be a bounded array.")
            result[key] = [self._text(value,key,300 if key=="warnings" else 120) for value in values]
        confidence = payload["confidence"]
        if isinstance(confidence,bool) or not isinstance(confidence,(int,float)) or not 0<=confidence<=1:
            raise ValueError("confidence must be from 0 to 1.")
        result["confidence"] = confidence; return result

    def _writer(self,payload):
        if not isinstance(payload,dict) or set(payload) != {"album_summary","description","suggested_names"}:
            raise ValueError("Writer result fields do not match schema v1.")
        names = payload["suggested_names"]
        if not isinstance(names,list) or len(names)!=6 or len(set(names))!=6: raise ValueError("suggested_names must contain exactly six unique names.")
        forbidden = {"photo","photos","collection","session","gallery"}; normalized=[]
        for name in names:
            name = self._text(name,"suggested_name",120); words=name.split()
            if not 2<=len(words)<=5 or any(not re.fullmatch(r"[A-Z][A-Za-z'’-]*",word) for word in words) \
                    or any(word.casefold() in forbidden for word in words):
                raise ValueError("Each suggested name must contain 2-5 capitalized English words and no forbidden term.")
            normalized.append(name)
        return {"album_summary":self._text(payload["album_summary"],"album_summary",500),
            "description":self._text(payload["description"],"description",2000),"suggested_names":normalized}

    @staticmethod
    def _metrics(metrics):
        if metrics is None: return {}
        if not isinstance(metrics,dict) or len(metrics)>20: raise ValueError("runtime_metrics must be a bounded object.")
        clean={}
        for key,value in metrics.items():
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,39}",str(key)) or isinstance(value,(dict,list)) or len(str(value))>200:
                raise ValueError("runtime_metrics contains an invalid field.")
            clean[str(key)]=value
        return clean

    def submit(self,item_uuid,worker_token_uuid,stage,schema_version,payload,runtime_metrics=None):
        expected = self.VISION_SCHEMA if stage=="Vision" else self.WRITER_SCHEMA if stage=="Writer" else None
        if schema_version != expected: raise ValueError("schema_version is not supported for this result stage.")
        normalized = self._vision(payload) if stage=="Vision" else self._writer(payload)
        raw = json.dumps(normalized,sort_keys=True,separators=(",",":"),ensure_ascii=True)
        if len(raw.encode()) > (65536 if stage=="Vision" else 32768): raise ValueError("AI result payload is too large.")
        self._evidence.revalidate(item_uuid)
        try:
            return self._repo.submit(item_uuid,worker_token_uuid,stage,schema_version,raw,
                hashlib.sha256(raw.encode()).hexdigest(),json.dumps(self._metrics(runtime_metrics),sort_keys=True),self._now().isoformat())
        except repo.PersistenceNotFound as exc: raise ServiceNotFound("AI Work Item not found.") from exc
        except repo.PersistenceConflict as exc:
            code=exc.details.get("code","AI_RESULT_CONFLICT")
            raise ServiceConflict(code,"AI result submission conflicts with Work Item state.",exc.details) from exc

    def get(self,item_uuid): return self._repo.get_results(item_uuid)


class AIReviewService:
    """Admin-owned stable review state machine for immutable AI output."""

    STATES={"ReadyForReview","InReview","Approved","Rejected","ReworkRequested"}

    def __init__(self,review_repo,now_fn=None):
        self._repo=review_repo; self._now=now_fn or (lambda:datetime.now(timezone.utc))

    @staticmethod
    def _name(value):
        value=str(value or "").strip(); words=value.split()
        forbidden={"photo","photos","collection","session","gallery"}
        if not 2<=len(words)<=5 or len(value)>120 or any(not re.fullmatch(r"[A-Z][A-Za-z'’-]*",word) for word in words) \
                or any(word.casefold() in forbidden for word in words):
            raise ValueError("The selected name must contain 2-5 capitalized English words and no forbidden term.")
        return value

    @staticmethod
    def allowed_actions(state):
        return ["start"] if state=="ReadyForReview" else ["approve","reject","request_rework"] if state=="InReview" else []

    def queue(self,state=None,workspace_uuid=None,limit=50,offset=0):
        if state and state not in self.STATES: raise ValueError("Review state filter is invalid.")
        if not 1<=limit<=100 or offset<0: raise ValueError("Review pagination is invalid.")
        rows,total=self._repo.queue(state,workspace_uuid,limit,offset)
        for row in rows: row["allowed_actions"]=self.allowed_actions(row["state"])
        return {"items":rows,"total":total,"limit":limit,"offset":offset}

    def detail(self,item_uuid):
        result=self._repo.detail(item_uuid)
        if not result: raise ServiceNotFound("AI review not found.")
        result["review"]["allowed_actions"]=self.allowed_actions(result["review"]["state"])
        return result

    def start(self,item_uuid,expected_version,actor):
        return self._transition(item_uuid,expected_version,"InReview",actor,{})

    def decide(self,item_uuid,expected_version,action,actor,body):
        targets={"approve":"Approved","reject":"Rejected","request_rework":"ReworkRequested"}
        if action not in targets: raise ValueError("Review action must be approve, reject, or request_rework.")
        rating=body.get("rating")
        if rating is not None and (isinstance(rating,bool) or not isinstance(rating,int) or not 1<=rating<=5):
            raise ValueError("rating must be an integer from 1 to 5.")
        notes=str(body.get("notes") or "").strip()
        if len(notes)>4000: raise ValueError("notes must not exceed 4000 characters.")
        reason=str(body.get("reason") or "").strip()
        if targets[action] in {"Rejected","ReworkRequested"} and not reason:
            raise ValueError("reason is required for rejection or rework.")
        if len(reason)>1000: raise ValueError("reason must not exceed 1000 characters.")
        evidence={"rating":rating,"notes":notes or None,"reason":reason or None}
        if action=="approve":
            source=body.get("selection_source")
            if source not in {"Recommendation","HumanRevision"}: raise ValueError("selection_source is required.")
            selected=self._name(body.get("selected_name")); detail=self.detail(item_uuid)
            writer=next((stage for stage in detail["results"] if stage["stage"]=="Writer"),None)
            if not writer: raise ServiceConflict("AI_REVIEW_RESULT_REQUIRED","Writer result is required for approval.")
            recommendations=writer["payload"]["suggested_names"]
            if source=="Recommendation" and selected not in recommendations:
                raise ValueError("The selected recommendation is not part of the accepted Writer result.")
            evidence.update({"selected_name":selected,"selection_source":source,
                "selected_recommendation":selected if source=="Recommendation" else None})
        return self._transition(item_uuid,expected_version,targets[action],actor,evidence)

    def _transition(self,item_uuid,expected_version,target,actor,evidence):
        if not isinstance(expected_version,int): raise ValueError("expected_version is required and must be an integer.")
        try:
            result=self._repo.transition(item_uuid,expected_version,target,actor,evidence,self._now().isoformat())
            result["review"]["allowed_actions"]=self.allowed_actions(result["review"]["state"])
            return result
        except repo.PersistenceNotFound as exc: raise ServiceNotFound("AI review not found.") from exc
        except repo.PersistenceConflict as exc:
            code=exc.details.get("code","AI_REVIEW_CONFLICT")
            raise ServiceConflict(code,"AI review transition conflicts with current state.",exc.details) from exc


class AIWorkspaceService:
    """Own the Dataset-independent AI Workspace container lifecycle."""

    def __init__(self, workspace_repo, operation_service=None):
        self._repo, self._operations = workspace_repo, operation_service

    def create(self, title: str, created_by_token_uuid: str | None = None) -> dict:
        title = str(title or "").strip()
        if not title or len(title) > 200: raise ValueError("Workspace title must contain 1 to 200 characters.")
        workspace = self._repo.create({"dataset_type": "album_analysis", "schema_version": 1,
            "title": title, "created_by_token_uuid": created_by_token_uuid, "created_at": _utc_now_iso()})
        if self._operations:
            op = self._operations.begin("ai_workspace_create", OP_INITIATOR_WEB_UI,
                entity_uuid=workspace["uuid"], summary=f"Created AI Workspace {title}")
            self._operations.succeed(op["uuid"], summary="AI Workspace created")
        return workspace

    def list(self, lifecycle_state=None):
        if lifecycle_state and lifecycle_state not in {"Open", "Closed", "Archived"}:
            raise ValueError("AI Workspace lifecycle filter is invalid.")
        return self._repo.list(lifecycle_state)

    def get(self, workspace_uuid):
        item = self._repo.get(workspace_uuid)
        if not item: raise ServiceNotFound("AI Workspace not found.")
        return item

    def _transition(self, workspace_uuid, expected_version, from_state, to_state, operation_type):
        current = self.get(workspace_uuid)
        if current["version"] != expected_version:
            raise ServiceConflict("AI_WORKSPACE_STALE", "The AI Workspace changed after it was read.", {"current": current})
        if current["lifecycle_state"] != from_state:
            raise ServiceConflict("AI_WORKSPACE_TRANSITION_INVALID", f"Cannot transition {current['lifecycle_state']} to {to_state}.", {"current": current})
        operation = self._operations.begin(operation_type, OP_INITIATOR_WEB_UI,
            entity_uuid=workspace_uuid, summary=f"AI Workspace {to_state}") if self._operations else None
        updated = self._repo.transition(workspace_uuid, expected_version, from_state, to_state,
                                        operation["uuid"] if operation else "", _utc_now_iso())
        if not updated or updated["version"] == expected_version:
            if operation: self._operations.fail(operation["uuid"], "concurrency", "AI_WORKSPACE_STALE")
            raise ServiceConflict("AI_WORKSPACE_STALE", "The AI Workspace changed during transition.")
        if operation: self._operations.succeed(operation["uuid"], summary=f"AI Workspace transitioned to {to_state}")
        return updated

    def close(self, workspace_uuid, expected_version):
        return self._transition(workspace_uuid, expected_version, "Open", "Closed", "ai_workspace_close")

    def archive(self, workspace_uuid, expected_version):
        return self._transition(workspace_uuid, expected_version, "Closed", "Archived", "ai_workspace_archive")


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
        preview_secret=None,
        cleanup_repo=None,
        delete_snapshot_fn=None,
        verify_snapshot_fn=None,
        operation_service=None,
        restore_preview_repo=None,
        database_state_fn=None,
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
        self._preview_secret = preview_secret
        self._cleanup_repo = cleanup_repo
        self._delete_snapshot = delete_snapshot_fn
        self._verify_snapshot = verify_snapshot_fn
        self._operations = operation_service
        self._restore_previews = restore_preview_repo
        self._database_state = database_state_fn

    @staticmethod
    def _identity(item: dict) -> str:
        value = f"{item.get('filename','')}:{item.get('size_bytes',0)}:{item.get('created_at','')}"
        return hashlib.sha256(value.encode()).hexdigest()[:24]

    def recovery_points(self, now: datetime | None = None) -> list[dict]:
        """Return safe Backend-discovered recovery-point administration models."""
        result = []
        for raw in self._catalog():
            item = dict(raw)
            protection = (SNAP_PROTECTION_PROTECTED if item.get("protected")
                          else item.get("protection_state", SNAP_PROTECTION_NONE))
            result.append({
                "identity": self._identity(item),
                "filename": item.get("filename"),
                "size_bytes": item.get("size_bytes", 0),
                "created_at": item.get("created_at"),
                "reason": item.get("reason", ""),
                "tag": item.get("tag", ""),
                "retention_class": item.get("retention_class", SNAP_RETENTION_ORDINARY),
                "protection_state": protection,
                "cleanup_eligible": is_retention_eligible({
                    "created_at": item.get("created_at"),
                    "retention_class": item.get("retention_class", SNAP_RETENTION_ORDINARY),
                    "protection_state": protection,
                }, now),
                "verification_state": item.get("verification_state", "not_verified"),
            })
        return result

    def verify(self, identity: str) -> dict:
        if not self._verify_snapshot:
            raise RuntimeError("Snapshot verification is not configured.")
        raw = next((x for x in self._catalog() if self._identity(x) == identity), None)
        if raw is None:
            raise ServiceNotFound("Recovery point not found.")
        return {"identity": identity, **self._verify_snapshot(raw)}

    def _sign_cleanup(self, payload: dict) -> str:
        if not self._preview_secret:
            raise RuntimeError("Snapshot cleanup preview signing is not configured.")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        encoded = base64.urlsafe_b64encode(raw).decode().rstrip("=")
        return f"{encoded}.{hmac.new(self._preview_secret, encoded.encode(), hashlib.sha256).hexdigest()}"

    def _read_cleanup(self, token: str) -> dict:
        try:
            encoded, signature = token.rsplit(".", 1)
            expected = hmac.new(self._preview_secret, encoded.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            if datetime.fromisoformat(payload["expires_at"]) <= datetime.now(timezone.utc):
                raise ServiceConflict("SNAPSHOT_CLEANUP_PREVIEW_EXPIRED", "The cleanup preview has expired.")
            return payload
        except ServiceConflict:
            raise
        except Exception as exc:
            raise ServiceConflict("SNAPSHOT_CLEANUP_PREVIEW_INVALID", "The cleanup preview is invalid.") from exc

    def preview_cleanup(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        items = [x for x in self.recovery_points(now) if x["cleanup_eligible"]]
        payload = {
            "preview_uuid": str(_uuid_mod.uuid4()),
            "eligible": [{"identity": x["identity"], "filename": x["filename"]} for x in items],
            "expires_at": (now + timedelta(minutes=15)).isoformat(),
        }
        return {"items": items, "summary": {"eligible": len(items)},
                "preview_token": self._sign_cleanup(payload), "expires_at": payload["expires_at"]}

    def execute_cleanup(self, token: str) -> dict:
        if not self._cleanup_repo or not self._delete_snapshot:
            raise RuntimeError("Snapshot cleanup execution is not configured.")
        payload = self._read_cleanup(token)
        if self._cleanup_repo.preview_is_claimed(payload["preview_uuid"]):
            raise ServiceConflict("SNAPSHOT_CLEANUP_PREVIEW_REPLAYED", "The cleanup preview was already used.")
        current = {self._identity(x): x for x in self._catalog()}
        reviewed = payload["eligible"]
        for expected in reviewed:
            raw = current.get(expected["identity"])
            if raw is None or not is_retention_eligible({
                "created_at": raw.get("created_at"),
                "retention_class": raw.get("retention_class", SNAP_RETENTION_ORDINARY),
                "protection_state": SNAP_PROTECTION_PROTECTED if raw.get("protected") else SNAP_PROTECTION_NONE,
            }):
                raise ServiceConflict("SNAPSHOT_CLEANUP_PREVIEW_STALE", "The recovery-point catalog changed after preview.")
        try:
            self._cleanup_repo.claim_preview(payload["preview_uuid"], _utc_now_iso())
        except repo.PersistenceConflict as exc:
            raise ServiceConflict("SNAPSHOT_CLEANUP_PREVIEW_REPLAYED", "The cleanup preview was already used.") from exc
        operation = self._operations.begin("snapshot_cleanup", OP_INITIATOR_WEB_UI,
                                           summary=f"Cleanup {len(reviewed)} reviewed recovery points") if self._operations else None
        deleted, failed = [], []
        for expected in reviewed:
            try:
                self._delete_snapshot(current[expected["identity"]])
                deleted.append(expected)
            except Exception as exc:
                failed.append({**expected, "error": str(exc)})
        if operation:
            if failed:
                self._operations.fail(operation["uuid"], "snapshot", "PARTIAL_CLEANUP",
                                      summary=f"Deleted {len(deleted)}; failed {len(failed)}")
            else:
                self._operations.succeed(operation["uuid"], summary=f"Deleted {len(deleted)} recovery points")
        return {"deleted": deleted, "failed": failed,
                "operation_uuid": operation["uuid"] if operation else None}

    def preview_restore(self, identity: str, now: datetime | None = None) -> dict:
        """Create an expiring Restore preview for one verified catalog identity."""
        raw = next((x for x in self._catalog() if self._identity(x) == identity), None)
        if raw is None:
            raise ServiceNotFound("Recovery point not found.")
        if raw.get("verification_state") != "verified":
            raise ServiceConflict("RESTORE_TARGET_NOT_VERIFIED", "Verify the recovery point before Restore.")
        now = now or datetime.now(timezone.utc)
        phrase = f"RESTORE {raw['filename']}"
        payload = {
            "preview_uuid": str(_uuid_mod.uuid4()), "identity": identity,
            "database_state": self._database_state(), "confirmation_phrase": phrase,
            "expires_at": (now + timedelta(minutes=10)).isoformat(),
        }
        return {"target": next(x for x in self.recovery_points() if x["identity"] == identity),
                "confirmation_phrase": phrase, "expires_at": payload["expires_at"],
                "preview_token": self._sign_cleanup(payload)}

    def execute_restore(self, token: str, confirmation: str) -> dict:
        """Execute one protected, preview-bound database Restore attempt."""
        if not self._restore_previews or not self._database_state or not self._verify_snapshot:
            raise RuntimeError("Protected Restore is not configured.")
        payload = self._read_cleanup(token)
        if not secrets.compare_digest(confirmation, payload.get("confirmation_phrase", "")):
            raise ServiceConflict("RESTORE_CONFIRMATION_MISMATCH", "The Restore confirmation phrase does not match.")
        if self._restore_previews.preview_is_claimed(payload["preview_uuid"]):
            raise ServiceConflict("RESTORE_PREVIEW_REPLAYED", "The Restore preview was already used.")
        if self._database_state() != payload["database_state"]:
            raise ServiceConflict("RESTORE_PREVIEW_STALE", "The database changed after Restore preview.")
        current = {self._identity(x): x for x in self._catalog()}
        target = current.get(payload["identity"])
        if target is None or target.get("verification_state") != "verified":
            raise ServiceConflict("RESTORE_PREVIEW_STALE", "The verified recovery point changed after preview.")
        try:
            self._restore_previews.claim_preview(payload["preview_uuid"], _utc_now_iso())
        except repo.PersistenceConflict as exc:
            raise ServiceConflict("RESTORE_PREVIEW_REPLAYED", "The Restore preview was already used.") from exc

        safety = self._snapshot("pre_restore_safety", f"restore-{payload['preview_uuid'][:8]}")
        self._backup_log({"timestamp": _utc_now_iso(), "reason": "pre_restore_safety", "ok": True,
                          "snapshot": str(safety), "tag": f"restore-{payload['preview_uuid'][:8]}",
                          "protected": True, "retention_class": SNAP_RETENTION_HIGH_RISK})
        safety_raw = next((x for x in self._catalog() if x.get("filename") == safety.name), None)
        if safety_raw is None or self._verify_snapshot(safety_raw).get("verification_state") != "verified":
            raise ServiceConflict("RESTORE_SAFETY_SNAPSHOT_FAILED", "The protective recovery point could not be verified.")
        try:
            self._restore(Path(target["path"]))
            # The database replacement also replaces the first claim table;
            # recreate the consumed claim in the restored database before any
            # success can be reported.
            self._restore_previews.claim_preview(payload["preview_uuid"], _utc_now_iso())
            database_verification = self._database_state(verify=True)
            if not database_verification.get("verified"):
                raise ServiceConflict("RESTORE_DATABASE_VERIFICATION_FAILED", "The restored database failed integrity verification.",
                                      {"safety_recovery_point": safety.name})
            operation = self._operations.begin(
                "database_restore", OP_INITIATOR_WEB_UI, summary=f"Restore from {target['filename']}",
                recovery_context=f"Protective recovery point: {safety.name}") if self._operations else None
            if operation:
                self._operations.succeed(operation["uuid"], summary="Database Restore verified successfully")
        except ServiceConflict:
            raise
        except Exception as exc:
            raise ServiceConflict("RESTORE_EXECUTION_FAILED", "Database Restore did not complete.",
                                  {"safety_recovery_point": safety.name}) from exc
        return {"restored_identity": payload["identity"], "safety_recovery_point": safety.name,
                "operation_uuid": operation["uuid"] if operation else None,
                "database_verified": True, "cache_reset_required": True, "reauthentication_required": True}

    def create(self, reason: str, tag: str = "") -> dict:
        """Create a named snapshot and log the outcome.

        Returns:
            A dict with ``snapshot`` (path string) and ``filename``.

        Raises:
            Exception: If the snapshot operation fails (caller maps to 500).
        """
        operation = self._operations.begin(
            "snapshot_create", OP_INITIATOR_WEB_UI, summary="Create manual recovery point"
        ) if self._operations else None
        snap = self._snapshot(reason, tag)
        entry = {
            "timestamp": _utc_now_iso(),
            "reason": reason,
            "ok": True,
            "snapshot": str(snap),
            "tag": tag,
        }
        self._backup_log(entry)
        if operation:
            self._operations.succeed(operation["uuid"], summary=f"Created recovery point {snap.name}")
        discovered = next((x for x in self._catalog()
                           if x.get("filename") == snap.name), None)
        recovery_point = None
        if discovered is not None:
            recovery_point = next((x for x in self.recovery_points()
                                   if x["identity"] == self._identity(discovered)), None)
        return {"recovery_point": recovery_point or {"filename": snap.name},
                "operation_uuid": operation["uuid"] if operation else None}

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
        if not fingerprint.strip() or not reason.strip():
            raise ValueError("Suppression fingerprint and reason are required.")
        bounded_scope = self._relative(self._under_root(scope_path))
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ValueError("Suppression expiry must be ISO-8601.") from exc
        if expiry <= datetime.now(timezone.utc): raise ValueError("Suppression expiry must be in the future.")
        operation = self._operations.begin("repair_suppression_create", creator,
                                           summary=f"Create bounded repair suppression for {bounded_scope}")
        record = self._suppressions.create({"fingerprint": fingerprint.strip(), "scope_path": bounded_scope, "reason": reason.strip(), "creator": creator, "expires_at": expiry.astimezone(timezone.utc).isoformat()})
        self._operations.succeed(operation["uuid"], "Repair suppression created.")
        record["operation_uuid"] = operation["uuid"]
        self._audit({"action": "repair_suppression_created", "suppression_uuid": record["uuid"], "creator": creator})
        return record

    def revoke_suppression(self, suppression_uuid: str, *, actor: str, actor_role: str) -> dict:
        self._require_admin(actor_role)
        record = self._suppressions.revoke(suppression_uuid, actor)
        if record is None:
            raise ServiceNotFound(f"Repair suppression not found: {suppression_uuid}")
        operation = self._operations.begin("repair_suppression_revoke", actor,
                                           summary=f"Revoke repair suppression {suppression_uuid}")
        self._operations.succeed(operation["uuid"], "Repair suppression revoked.")
        record["operation_uuid"] = operation["uuid"]
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
        self._repo.mark_restored(item_uuid, op["uuid"], destination)
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


class QuarantineContractService:
    """Signed review/execute contract for Admin repair Quarantine actions."""
    def __init__(self, quarantine_repo, repair_repo, service, archive_root, quarantine_root, preview_secret):
        self._repo, self._repairs, self._service = quarantine_repo, repair_repo, service
        self._archive, self._quarantine = Path(archive_root).resolve(), Path(quarantine_root).resolve()
        self._secret = preview_secret

    @staticmethod
    def _fingerprint(path: Path) -> dict:
        if not path.is_dir(): return {"exists": False, "digest": None}
        entries = []
        for item in sorted(path.rglob("*"), key=lambda value: str(value.relative_to(path))):
            stat = item.stat(); entries.append([str(item.relative_to(path)), item.is_dir(), stat.st_size, stat.st_mtime_ns])
        return {"exists": True, "digest": hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()}

    def _token(self, payload):
        raw = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).decode().rstrip("=")
        return f"{raw}.{hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()}"

    def _read(self, token):
        try:
            raw, signature = token.rsplit(".", 1)
            if not hmac.compare_digest(signature, hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()): raise ValueError
            payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
            if datetime.fromisoformat(payload["expires_at"]) <= datetime.now(timezone.utc):
                raise ServiceConflict("QUARANTINE_PREVIEW_EXPIRED", "The Quarantine preview expired.")
            return payload
        except ServiceConflict: raise
        except Exception as exc: raise ServiceConflict("QUARANTINE_PREVIEW_INVALID", "The Quarantine preview is invalid.") from exc

    def _base_payload(self, action):
        return {"v": 1, "preview_uuid": str(_uuid_mod.uuid4()), "action": action,
                "archive_root": str(self._archive), "quarantine_root": str(self._quarantine),
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}

    def preview_quarantine(self, repair_uuid, reason):
        repair = self._repairs.get_by_uuid(repair_uuid)
        if not repair: raise ServiceNotFound("Repair case not found.")
        if repair["state"] not in {REPAIR_STATE_NEEDS_REPAIR, REPAIR_STATE_MANUAL_CONFLICT}:
            raise ServiceConflict("INVALID_TRANSITION", "Repair is not eligible for Quarantine.")
        relative = repair.get("expected_path")
        if not relative: raise ServiceConflict("QUARANTINE_NOT_ELIGIBLE", "Repair has no Backend-approved candidate path.")
        source = self._service._within(self._archive, relative); state = self._fingerprint(source)
        if not state["exists"]: raise ServiceNotFound("The approved managed directory was not found.")
        if not isinstance(reason, str) or not reason.strip(): raise ValueError("Quarantine reason is required.")
        payload = self._base_payload("quarantine"); payload.update({"repair_uuid": repair_uuid, "repair_updated_at": repair["updated_at"],
            "relative_path": relative, "reason": reason.strip(), "source_state": state})
        return {"preview_token": self._token(payload), "preview_uuid": payload["preview_uuid"], "expires_at": payload["expires_at"],
                "action": "quarantine", "repair_uuid": repair_uuid, "managed_path": relative,
                "file_count": len([p for p in source.rglob("*") if p.is_file()]), "consequence": "Move the directory intact into repair Quarantine; this does not resolve the Issue."}

    def preview_restore(self, item_uuid):
        item = self._repo.get(item_uuid)
        if not item: raise ServiceNotFound("Quarantine item not found.")
        if item.get("restored_at"): raise ServiceConflict("QUARANTINE_ALREADY_RESTORED", "The item was already restored.")
        source = self._service._within(self._quarantine, item["quarantine_path"]); state = self._fingerprint(source)
        if not state["exists"]: raise ServiceConflict("QUARANTINE_ITEM_MISSING", "Quarantined content is missing.")
        target = self._service._within(self._archive, item["original_path"])
        if target.exists(): raise ServiceConflict("RESTORE_DESTINATION_EXISTS", "The original managed path is occupied.")
        payload = self._base_payload("restore"); payload.update({"item_uuid": item_uuid, "source_state": state,
            "original_path": item["original_path"], "created_at": item["created_at"]})
        return {"preview_token": self._token(payload), "preview_uuid": payload["preview_uuid"], "expires_at": payload["expires_at"],
                "action": "restore", "item_uuid": item_uuid, "managed_destination": item["original_path"],
                "consequence": "Restore the intact directory to its recorded original managed path after a snapshot."}

    def execute(self, token, actor_role):
        payload = self._read(token)
        if self._repo.preview_is_claimed(payload["preview_uuid"]): raise ServiceConflict("QUARANTINE_PREVIEW_REPLAYED", "The preview was already used.")
        if payload["archive_root"] != str(self._archive) or payload["quarantine_root"] != str(self._quarantine):
            raise ServiceConflict("QUARANTINE_PREVIEW_STALE", "Quarantine configuration changed.")
        if payload["action"] == "quarantine":
            repair = self._repairs.get_by_uuid(payload["repair_uuid"]); source = self._service._within(self._archive, payload["relative_path"])
            if not repair or repair["updated_at"] != payload["repair_updated_at"] or self._fingerprint(source) != payload["source_state"]:
                raise ServiceConflict("QUARANTINE_PREVIEW_STALE", "Repair or managed directory changed after preview.")
        else:
            item = self._repo.get(payload["item_uuid"]); source = self._service._within(self._quarantine, item["quarantine_path"] if item else "missing")
            target = self._service._within(self._archive, payload["original_path"])
            if not item or item.get("restored_at") or item["created_at"] != payload["created_at"] or target.exists() or self._fingerprint(source) != payload["source_state"]:
                raise ServiceConflict("QUARANTINE_PREVIEW_STALE", "Quarantine item or restore destination changed after preview.")
        try: self._repo.claim_preview(payload["preview_uuid"])
        except repo.PersistenceConflict as exc: raise ServiceConflict("QUARANTINE_PREVIEW_REPLAYED", "The preview was already used.", exc.details) from exc
        if payload["action"] == "quarantine":
            record = self._service.quarantine(payload["relative_path"], repair_uuid=payload["repair_uuid"], reason=payload["reason"], actor_role=actor_role, initiator=OP_INITIATOR_WEB_UI)
            return {"action": "quarantine", "item": record, "operation_uuid": record["operation_uuid"]}
        operation = self._service.restore(payload["item_uuid"], payload["original_path"], actor_role=actor_role, initiator=OP_INITIATOR_WEB_UI)
        return {"action": "restore", "item": self._repo.get(payload["item_uuid"]), "operation_uuid": operation["uuid"]}


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


class IssueRepairReviewService:
    """Role-safe read and optimistic decision boundary for Issue/Repair UI."""

    def __init__(self, issue_repo, repair_repo, operation_service):
        self._issue_repo = issue_repo
        self._repair_repo = repair_repo
        self._issues = IssueService(issue_repo)
        self._repairs = RepairService(repair_repo, issue_repo)
        self._operations = operation_service

    @staticmethod
    def _issue_actions(issue: dict, role: str) -> list[str]:
        actions: list[str] = []
        if issue["state"] == ISSUE_STATE_OPEN: actions.append("begin_work")
        if issue["state"] == ISSUE_STATE_IN_PROGRESS: actions.append("reopen")
        if role == ISSUE_ADMIN_ROLE:
            actions.append("assign")
            if issue["state"] == ISSUE_STATE_IN_PROGRESS: actions.append("resolve")
            if issue["state"] in {ISSUE_STATE_OPEN, ISSUE_STATE_IN_PROGRESS, ISSUE_STATE_RESOLVED}: actions.append("archive")
        return actions

    @staticmethod
    def _repair_actions(repair: dict, role: str) -> list[str]:
        if role not in {"writer", "admin"}: return []
        state = repair["state"]
        if state == REPAIR_STATE_NEEDS_REPAIR:
            actions = ["ignore", "escalate"]
            if repair["category"] == REPAIR_CATEGORY_AUTOMATIC or repair.get("confirmation"):
                actions.append("start")
            else: actions.append("confirm")
            return actions
        if state == REPAIR_STATE_MANUAL_CONFLICT:
            return ["ignore", "start"] if repair.get("confirmation") else ["ignore", "confirm"]
        if state == REPAIR_STATE_REPAIRING: return ["complete_action"]
        if state == REPAIR_STATE_PENDING_VERIFICATION: return ["verify_passed", "verify_failed"]
        return []

    def list_issues(self, role: str, *, state=None, owner=None) -> list[dict]:
        return [self._issue_view(item, role) for item in self._issue_repo.list_issues(state=state, owner=owner)]

    def get_issue(self, issue_uuid: str, role: str) -> dict:
        item = self._issue_repo.get_by_uuid(issue_uuid)
        if item is None: raise ServiceNotFound("Issue not found.")
        return self._issue_view(item, role)

    def _issue_view(self, item: dict, role: str) -> dict:
        result = {key: value for key, value in item.items() if key != "id"}
        result["links"] = self._issue_repo.list_links(item["uuid"])
        result["allowed_actions"] = self._issue_actions(item, role)
        return result

    def list_repairs(self, role: str, *, state=None, category=None) -> list[dict]:
        return [self._repair_view(item, role) for item in self._repair_repo.list_cases(state=state, category=category)]

    def get_repair(self, repair_uuid: str, role: str) -> dict:
        item = self._repair_repo.get_by_uuid(repair_uuid)
        if item is None: raise ServiceNotFound("Repair case not found.")
        return self._repair_view(item, role)

    def _repair_view(self, item: dict, role: str) -> dict:
        hidden = {"id", "confirmation", "expected_path", "failure_reason", "verification_result"}
        if role in {"writer", "admin"}: hidden = {"id"}
        result = {key: value for key, value in item.items() if key not in hidden}
        result["allowed_actions"] = self._repair_actions(item, role)
        if role == "admin" and item["state"] in {REPAIR_STATE_NEEDS_REPAIR, REPAIR_STATE_MANUAL_CONFLICT} and item.get("expected_path"):
            fingerprint_input = f"{item['uuid']}\0{item['expected_path']}\0{item.get('failure_reason') or ''}"
            result["suppression_candidate"] = {
                "fingerprint": hashlib.sha256(fingerprint_input.encode()).hexdigest(),
                "scope_path": item["expected_path"],
            }
            result["quarantine_candidate"] = {"repair_uuid": item["uuid"], "managed_path": item["expected_path"]}
        return result

    @staticmethod
    def _require_current(item: dict | None, expected: str, kind: str) -> dict:
        if item is None: raise ServiceNotFound(f"{kind} not found.")
        if not expected or item.get("updated_at") != expected:
            raise ServiceConflict("WORKFLOW_STALE", f"{kind} changed; reload before deciding.",
                                  {"current_updated_at": item.get("updated_at")})
        return item

    def decide_issue(self, issue_uuid: str, role: str, action: str, expected: str, body: dict) -> dict:
        item = self._require_current(self._issue_repo.get_by_uuid(issue_uuid), expected, "Issue")
        if action not in self._issue_actions(item, role):
            raise ServiceConflict("INVALID_TRANSITION", "The Issue action is not currently allowed.",
                                  {"allowed": self._issue_actions(item, role)})
        if action == "resolve" and (not isinstance(body.get("verification"), str) or not body["verification"].strip()):
            raise ValueError("Resolution verification is required.")
        if action == "assign" and body.get("owner") is not None and (not isinstance(body["owner"], str) or not body["owner"].strip()):
            raise ValueError("Issue owner must be a non-empty name or null.")
        operation = self._operations.begin(f"issue_{action}", OP_INITIATOR_WEB_UI,
                                           issue_uuid=issue_uuid, summary=f"Issue decision: {action}")
        if action == "begin_work": updated = self._issues.begin_work(issue_uuid)
        elif action == "reopen": updated = self._issues.reopen(issue_uuid)
        elif action == "assign": updated = self._issues.assign(issue_uuid, body.get("owner"), actor_role=role)
        elif action == "resolve": updated = self._issues.resolve(issue_uuid, body.get("verification", ""), actor_role=role)
        elif action == "archive": updated = self._issues.archive(issue_uuid, actor_role=role)
        else: raise ValueError("Unknown Issue action.")
        self._operations.succeed(operation["uuid"], f"Issue {action} completed.")
        return {"issue": self._issue_view(updated, role), "operation_uuid": operation["uuid"]}

    def decide_repair(self, repair_uuid: str, role: str, action: str, expected: str, body: dict) -> dict:
        item = self._require_current(self._repair_repo.get_by_uuid(repair_uuid), expected, "Repair")
        if action not in self._repair_actions(item, role):
            raise ServiceConflict("INVALID_TRANSITION", "The Repair action is not currently allowed.",
                                  {"allowed": self._repair_actions(item, role)})
        if action == "confirm" and (not isinstance(body.get("confirmation"), str) or not body["confirmation"].strip()):
            raise ValueError("Confirmation is required.")
        if action in {"verify_passed", "verify_failed"} and (not isinstance(body.get("verification"), str) or not body["verification"].strip()):
            raise ValueError("Verification evidence is required.")
        operation = self._operations.begin(f"repair_{action}", OP_INITIATOR_WEB_UI,
                                           repair_uuid=repair_uuid, related_operation_uuid=item.get("operation_uuid"),
                                           summary=f"Repair decision: {action}")
        if action == "confirm":
            confirmation = body.get("confirmation", "")
            updated = self._repairs.confirm(repair_uuid, confirmation.strip())
        elif action == "start": updated = self._repairs.start_repair(repair_uuid)
        elif action == "escalate": updated = self._repairs.escalate_to_manual(repair_uuid)
        elif action == "complete_action": updated = self._repairs.complete_action(repair_uuid)
        elif action in {"verify_passed", "verify_failed"}:
            result = body.get("verification", "")
            updated = self._repairs.verify(repair_uuid, action == "verify_passed", result.strip())
        elif action == "ignore": updated = self._repairs.ignore(repair_uuid)
        else: raise ValueError("Unknown Repair action.")
        self._operations.succeed(operation["uuid"], f"Repair {action} completed.")
        return {"repair": self._repair_view(updated, role), "operation_uuid": operation["uuid"]}


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


class OperationReadService:
    """Project durable Operation records into role-safe API read models."""

    _PUBLIC_FIELDS = (
        "uuid", "operation_type", "initiator", "status", "summary", "started_at", "ended_at",
        "entity_uuid", "import_uuid", "batch_uuid", "repair_uuid", "related_operation_uuid",
        "parent_operation_uuid", "issue_uuid", "error_category", "error_code", "repair_state",
    )

    def __init__(self, operation_repo):
        self._repo = operation_repo

    def list_recent(self, role: str, limit: int = 50) -> list[dict]:
        return [self._project(record, role) for record in self._repo.list_recent(limit)]

    @staticmethod
    def _filter_identity(filters: dict) -> str:
        raw = json.dumps(filters, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()[:20]

    @classmethod
    def _encode_cursor(cls, record: dict, filters: dict) -> str:
        payload = {"v": 1, "started_at": record["started_at"], "id": record["id"],
                   "query": cls._filter_identity(filters)}
        return base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).decode().rstrip("=")

    @classmethod
    def _decode_cursor(cls, cursor: str, filters: dict) -> tuple[str, int]:
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded).decode())
            if payload.get("v") != 1 or payload.get("query") != cls._filter_identity(filters):
                raise ValueError
            started_at = str(payload["started_at"])
            row_id = int(payload["id"])
            if not started_at or row_id < 1:
                raise ValueError
            return started_at, row_id
        except Exception as exc:
            raise ValueError("Invalid or query-mismatched Operation cursor.") from exc

    def query(self, role: str, *, limit: int, cursor: str | None = None,
              status: str | None = None, operation_type: str | None = None,
              started_from: str | None = None, started_to: str | None = None) -> dict:
        filters = {key: value for key, value in {
            "status": status, "operation_type": operation_type,
            "started_from": started_from, "started_to": started_to,
        }.items() if value is not None}
        after = self._decode_cursor(cursor, filters) if cursor else None
        records, total = self._repo.query_history(
            limit=limit, after=after, status=status, operation_type=operation_type,
            started_from=started_from, started_to=started_to,
        )
        has_more = len(records) > limit
        page = records[:limit]
        next_cursor = self._encode_cursor(page[-1], filters) if has_more and page else None
        return {"items": [self._project(record, role) for record in page],
                "total": total, "has_more": has_more, "next_cursor": next_cursor,
                "filters": filters}

    def get(self, operation_uuid: str, role: str) -> dict:
        record = self._repo.get_by_uuid(operation_uuid)
        if record is None:
            raise ServiceNotFound("Operation not found.")
        return self._project(record, role)

    def _project(self, record: dict, role: str) -> dict:
        result = {field: record.get(field) for field in self._PUBLIC_FIELDS}
        if role in {"writer", "admin"}:
            result["recovery_context"] = record.get("recovery_context")
        return result
