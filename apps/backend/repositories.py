#!/usr/bin/env python3
"""Repository layer for Curator Backend.

Repositories are the exclusive persistence boundary. They execute SQL,
translate rows to plain dicts, and hide SQLite-specific details from the
application layer. No sqlite3 objects, raw rows, or SQL strings leave this
module.

Services depend on repository contracts, not on SQLite mechanics. Handlers
that have no corresponding service call repository methods directly.
"""
from __future__ import annotations

import uuid
import json
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Persistence exceptions
# ---------------------------------------------------------------------------

class PersistenceConflict(Exception):
    """Raised when a write or delete cannot proceed due to a constraint.

    Attributes:
        details: Dict of counts or conflict context supplied to the caller.
    """

    def __init__(self, details: dict):
        super().__init__(str(details))
        self.details = details


class PersistenceNotFound(Exception):
    """Raised when a required record cannot be located."""


# ---------------------------------------------------------------------------
# Device authentication persistence
# ---------------------------------------------------------------------------

class AuthRepository:
    """Persistence contract for device registration and bearer-token state.

    Token plaintext is intentionally not accepted by this repository.  The
    service supplies a one-way token hash and is the only layer that ever sees
    a newly generated credential.
    """

    def __init__(self, db_factory):
        self._db = db_factory

    @staticmethod
    def _ensure_schema(conn) -> None:
        """Install the independent authentication tables when first used.

        Authentication is additive to the existing Curator schema, so this
        also makes the repository usable with an older database file.
        """
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS device_registration (
                uuid TEXT PRIMARY KEY,
                device_name TEXT NOT NULL,
                device_identity TEXT NOT NULL UNIQUE,
                requested_role TEXT NOT NULL,
                requested_scopes TEXT NOT NULL,
                approved_role TEXT,
                approved_scopes TEXT,
                status TEXT NOT NULL,
                trusted INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                approved_at TEXT,
                rejected_at TEXT
            );
            CREATE TABLE IF NOT EXISTS auth_token (
                uuid TEXT PRIMARY KEY,
                token_hash TEXT NOT NULL UNIQUE,
                registration_uuid TEXT NOT NULL,
                device_name TEXT NOT NULL,
                scopes TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_used_at TEXT,
                revoked_at TEXT,
                replaced_by_uuid TEXT,
                FOREIGN KEY(registration_uuid) REFERENCES device_registration(uuid)
            );
            CREATE TABLE IF NOT EXISTS token_renewal_request (
                uuid TEXT PRIMARY KEY,
                registration_uuid TEXT NOT NULL,
                previous_token_uuid TEXT NOT NULL,
                requested_role TEXT NOT NULL,
                requested_scopes TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                approved_at TEXT,
                rejected_at TEXT,
                FOREIGN KEY(registration_uuid) REFERENCES device_registration(uuid),
                FOREIGN KEY(previous_token_uuid) REFERENCES auth_token(uuid)
            );
            CREATE TABLE IF NOT EXISTS admin_bootstrap_code (
                uuid TEXT PRIMARY KEY,
                code_hash TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_at TEXT
            );
            """
        )
        conn.commit()

    @staticmethod
    def _registration(row: dict) -> dict:
        result = dict(row)
        for key in ("requested_scopes", "approved_scopes"):
            result[key] = json.loads(result[key]) if result[key] else []
        result["trusted"] = bool(result["trusted"])
        return result

    @staticmethod
    def _token(row: dict) -> dict:
        result = dict(row)
        result["scopes"] = json.loads(result["scopes"])
        return result

    @staticmethod
    def _renewal(row: dict) -> dict:
        result = dict(row)
        result["requested_scopes"] = json.loads(result["requested_scopes"])
        return result

    def create_registration(self, fields: dict) -> dict:
        now = _utc_now_iso()
        registration_uuid = fields.get("uuid") or str(uuid.uuid4())
        with self._db() as conn:
            self._ensure_schema(conn)
            try:
                conn.execute(
                    """INSERT INTO device_registration
                    (uuid, device_name, device_identity, requested_role,
                     requested_scopes, status, trusted, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'PendingApproval', 0, ?, ?)""",
                    (registration_uuid, fields["device_name"], fields["device_identity"],
                     fields["requested_role"], json.dumps(fields["requested_scopes"]), now, now),
                )
                conn.commit()
            except Exception as exc:
                # The service turns this deliberately small persistence signal
                # into a stable business outcome.
                raise PersistenceConflict({"device_identity": fields["device_identity"]}) from exc
            row = conn.execute("SELECT * FROM device_registration WHERE uuid = ?", (registration_uuid,)).fetchone()
        return self._registration(dict(row))

    def get_registration(self, registration_uuid: str) -> dict | None:
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute("SELECT * FROM device_registration WHERE uuid = ?", (registration_uuid,)).fetchone()
        return self._registration(dict(row)) if row else None

    def get_registration_by_identity(self, device_identity: str) -> dict | None:
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute("SELECT * FROM device_registration WHERE device_identity = ?", (device_identity,)).fetchone()
        return self._registration(dict(row)) if row else None

    def list_registrations(self) -> list[dict]:
        with self._db() as conn:
            self._ensure_schema(conn)
            rows = conn.execute("SELECT * FROM device_registration ORDER BY created_at DESC").fetchall()
        return [self._registration(dict(row)) for row in rows]

    def list_tokens(self) -> list[dict]:
        with self._db() as conn:
            self._ensure_schema(conn)
            rows = conn.execute("SELECT * FROM auth_token ORDER BY created_at DESC").fetchall()
        result = [self._token(dict(row)) for row in rows]
        for item in result: item.pop("token_hash", None)
        return result

    def list_renewals(self) -> list[dict]:
        with self._db() as conn:
            self._ensure_schema(conn)
            rows = conn.execute("SELECT * FROM token_renewal_request ORDER BY created_at DESC").fetchall()
        return [self._renewal(dict(row)) for row in rows]

    def approve_registration(self, registration_uuid: str, role: str, scopes: list[str], trusted: bool) -> dict | None:
        now = _utc_now_iso()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                """UPDATE device_registration SET status = 'Approved', approved_role = ?,
                approved_scopes = ?, trusted = ?, approved_at = ?, updated_at = ?
                WHERE uuid = ? AND status = 'PendingApproval'""",
                (role, json.dumps(scopes), int(trusted), now, now, registration_uuid),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM device_registration WHERE uuid = ?", (registration_uuid,)).fetchone()
        return self._registration(dict(row)) if row else None

    def reject_registration(self, registration_uuid: str) -> dict | None:
        now = _utc_now_iso()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                """UPDATE device_registration SET status = 'Rejected', rejected_at = ?, updated_at = ?
                WHERE uuid = ? AND status = 'PendingApproval'""",
                (now, now, registration_uuid),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM device_registration WHERE uuid = ?", (registration_uuid,)).fetchone()
        return self._registration(dict(row)) if row else None

    def create_token(self, fields: dict) -> dict:
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                """INSERT INTO auth_token
                (uuid, token_hash, registration_uuid, device_name, scopes, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (fields["uuid"], fields["token_hash"], fields["registration_uuid"],
                 fields["device_name"], json.dumps(fields["scopes"]),
                 fields["created_at"], fields["expires_at"]),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM auth_token WHERE uuid = ?", (fields["uuid"],)).fetchone()
        return self._token(dict(row))

    def get_token_by_hash(self, token_hash: str) -> dict | None:
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute("SELECT * FROM auth_token WHERE token_hash = ?", (token_hash,)).fetchone()
        return self._token(dict(row)) if row else None

    def has_usable_admin(self, now_iso: str) -> bool:
        """Return whether an approved trusted registration has a usable Admin Token."""
        with self._db() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """SELECT t.scopes FROM auth_token t
                   JOIN device_registration r ON r.uuid = t.registration_uuid
                   WHERE r.status = 'Approved' AND r.trusted = 1
                     AND r.approved_role = 'admin'
                     AND t.revoked_at IS NULL AND t.expires_at > ?""",
                (now_iso,),
            ).fetchall()
        return any("admin" in json.loads(row["scopes"]) for row in rows)

    def has_bootstrapped_admin(self) -> bool:
        """Return whether first-administrator bootstrap has already completed."""
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                """SELECT 1 FROM device_registration
                   WHERE status = 'Approved' AND trusted = 1
                     AND approved_role = 'admin' LIMIT 1"""
            ).fetchone()
        return row is not None

    def bootstrap_first_admin(self, registration: dict, token: dict, now_iso: str) -> tuple[dict, dict]:
        """Atomically create the first trusted Admin registration and Token."""
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            existing_admin = conn.execute(
                """SELECT 1 FROM device_registration
                   WHERE status = 'Approved' AND trusted = 1
                     AND approved_role = 'admin' LIMIT 1"""
            ).fetchone()
            if existing_admin is not None:
                conn.rollback()
                raise PersistenceConflict({"reason": "usable_admin_exists"})
            try:
                conn.execute(
                    """INSERT INTO device_registration
                       (uuid, device_name, device_identity, requested_role,
                        requested_scopes, approved_role, approved_scopes,
                        status, trusted, created_at, updated_at, approved_at)
                       VALUES (?, ?, ?, 'admin', ?, 'admin', ?, 'Approved', 1, ?, ?, ?)""",
                    (
                        registration["uuid"], registration["device_name"],
                        registration["device_identity"], json.dumps(registration["scopes"]),
                        json.dumps(registration["scopes"]), now_iso, now_iso, now_iso,
                    ),
                )
                conn.execute(
                    """INSERT INTO auth_token
                       (uuid, token_hash, registration_uuid, device_name, scopes,
                        created_at, expires_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        token["uuid"], token["token_hash"], registration["uuid"],
                        registration["device_name"], json.dumps(registration["scopes"]),
                        token["created_at"], token["expires_at"],
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            registration_row = conn.execute(
                "SELECT * FROM device_registration WHERE uuid = ?", (registration["uuid"],)
            ).fetchone()
            token_row = conn.execute(
                "SELECT * FROM auth_token WHERE uuid = ?", (token["uuid"],)
            ).fetchone()
        return self._registration(dict(registration_row)), self._token(dict(token_row))

    def rollback_bootstrap(self, registration_uuid: str, token_uuid: str) -> None:
        """Compensate a just-created bootstrap credential when audit persistence fails."""
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "DELETE FROM auth_token WHERE uuid = ? AND registration_uuid = ?",
                (token_uuid, registration_uuid),
            )
            conn.execute("DELETE FROM device_registration WHERE uuid = ?", (registration_uuid,))
            conn.commit()

    def create_bootstrap_code(self, fields: dict) -> dict:
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE admin_bootstrap_code SET used_at = ? WHERE used_at IS NULL",
                (fields["created_at"],),
            )
            conn.execute(
                """INSERT INTO admin_bootstrap_code
                   (uuid, code_hash, created_at, expires_at)
                   VALUES (?, ?, ?, ?)""",
                (fields["uuid"], fields["code_hash"], fields["created_at"], fields["expires_at"]),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM admin_bootstrap_code WHERE uuid = ?", (fields["uuid"],)
            ).fetchone()
        result = dict(row)
        result.pop("code_hash", None)
        return result

    def get_current_bootstrap_code(self) -> dict | None:
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                """SELECT * FROM admin_bootstrap_code
                   WHERE used_at IS NULL ORDER BY created_at DESC LIMIT 1"""
            ).fetchone()
        return dict(row) if row else None

    def fail_bootstrap_code(self, code_uuid: str, now_iso: str, maximum_attempts: int) -> dict | None:
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                """UPDATE admin_bootstrap_code
                   SET failed_attempts = failed_attempts + 1,
                       locked_at = CASE WHEN failed_attempts + 1 >= ? THEN ? ELSE locked_at END
                   WHERE uuid = ? AND used_at IS NULL""",
                (maximum_attempts, now_iso, code_uuid),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM admin_bootstrap_code WHERE uuid = ?", (code_uuid,)
            ).fetchone()
        return dict(row) if row else None

    def consume_bootstrap_code(self, code_uuid: str, now_iso: str) -> bool:
        with self._db() as conn:
            self._ensure_schema(conn)
            cursor = conn.execute(
                """UPDATE admin_bootstrap_code SET used_at = ?
                   WHERE uuid = ? AND used_at IS NULL AND locked_at IS NULL""",
                (now_iso, code_uuid),
            )
            conn.commit()
        return cursor.rowcount == 1

    def touch_token(self, token_uuid: str, used_at: str) -> None:
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute("UPDATE auth_token SET last_used_at = ? WHERE uuid = ?", (used_at, token_uuid))
            conn.commit()

    def revoke_token(self, token_uuid: str, *, replaced_by_uuid: str | None = None) -> bool:
        now = _utc_now_iso()
        with self._db() as conn:
            self._ensure_schema(conn)
            cur = conn.execute(
                "UPDATE auth_token SET revoked_at = ?, replaced_by_uuid = ? WHERE uuid = ? AND revoked_at IS NULL",
                (now, replaced_by_uuid, token_uuid),
            )
            conn.commit()
        return cur.rowcount == 1

    def revoke_token_preserving_admin(self, token_uuid: str, now_iso: str) -> bool:
        """Atomically revoke a Token unless it is the final usable Admin."""
        with self._db() as conn:
            self._ensure_schema(conn); conn.execute("BEGIN IMMEDIATE")
            target = conn.execute(
                """SELECT t.uuid,t.revoked_at,t.expires_at,t.scopes,r.approved_role,r.status,r.trusted
                   FROM auth_token t JOIN device_registration r ON r.uuid=t.registration_uuid
                   WHERE t.uuid=?""", (token_uuid,),
            ).fetchone()
            if target is None or target["revoked_at"] is not None:
                conn.rollback(); return False
            target_usable_admin = (
                target["approved_role"] == "admin" and target["status"] == "Approved"
                and bool(target["trusted"]) and target["expires_at"] > now_iso
                and "admin" in json.loads(target["scopes"])
            )
            if target_usable_admin:
                count = conn.execute(
                    """SELECT COUNT(*) FROM auth_token t JOIN device_registration r ON r.uuid=t.registration_uuid
                       WHERE r.approved_role='admin' AND r.status='Approved' AND r.trusted=1
                         AND t.revoked_at IS NULL AND t.expires_at>? AND t.scopes LIKE '%admin%'""", (now_iso,),
                ).fetchone()[0]
                if count <= 1:
                    conn.rollback(); raise PersistenceConflict({"reason": "last_usable_admin", "token_uuid": token_uuid})
            conn.execute("UPDATE auth_token SET revoked_at=? WHERE uuid=? AND revoked_at IS NULL", (now_iso, token_uuid))
            conn.commit(); return True

    def create_renewal_request(self, fields: dict) -> dict:
        now = _utc_now_iso()
        request_uuid = fields.get("uuid") or str(uuid.uuid4())
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                """INSERT INTO token_renewal_request
                (uuid, registration_uuid, previous_token_uuid, requested_role, requested_scopes,
                 status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'PendingApproval', ?, ?)""",
                (request_uuid, fields["registration_uuid"], fields["previous_token_uuid"],
                 fields["requested_role"], json.dumps(fields["requested_scopes"]), now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM token_renewal_request WHERE uuid = ?", (request_uuid,)).fetchone()
        return self._renewal(dict(row))

    def get_renewal_request(self, request_uuid: str) -> dict | None:
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute("SELECT * FROM token_renewal_request WHERE uuid = ?", (request_uuid,)).fetchone()
        return self._renewal(dict(row)) if row else None

    def get_pending_renewal_for_token(self, token_uuid: str) -> dict | None:
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                """SELECT * FROM token_renewal_request
                   WHERE previous_token_uuid = ? AND status = 'PendingApproval'
                   ORDER BY created_at DESC LIMIT 1""",
                (token_uuid,),
            ).fetchone()
        return self._renewal(dict(row)) if row else None

    def approve_renewal(self, request_uuid: str) -> dict | None:
        now = _utc_now_iso()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                """UPDATE token_renewal_request SET status = 'Approved', approved_at = ?, updated_at = ?
                WHERE uuid = ? AND status = 'PendingApproval'""", (now, now, request_uuid)
            )
            conn.commit()
            row = conn.execute("SELECT * FROM token_renewal_request WHERE uuid = ?", (request_uuid,)).fetchone()
        return self._renewal(dict(row)) if row else None

    def reject_renewal(self, request_uuid: str) -> dict | None:
        now = _utc_now_iso()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute("""UPDATE token_renewal_request SET status='Rejected',rejected_at=?,updated_at=?
                            WHERE uuid=? AND status='PendingApproval'""", (now, now, request_uuid))
            conn.commit(); row = conn.execute("SELECT * FROM token_renewal_request WHERE uuid=?", (request_uuid,)).fetchone()
        return self._renewal(dict(row)) if row else None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Read-model normalization
#
# Each function accepts a plain dict (converted from a sqlite3.Row) and
# returns a canonical read-model dict with a stable, explicit field set.
# Services and controllers consume these normalized dicts; they never see
# raw database row objects or database-specific field conventions.
# ---------------------------------------------------------------------------

def _norm_status(row: dict) -> dict:
    """Canonical read model for a single status record."""
    return {
        "id": row["id"],
        "name": row.get("name"),
        "description": row.get("description"),
    }


def _norm_status_with_counts(row: dict) -> dict:
    """Status read model enriched with album reference counts."""
    return {
        "id": row["id"],
        "name": row.get("name"),
        "description": row.get("description"),
        "album_count": row.get("album_count", 0),
        "workspace_album_count": row.get("workspace_album_count", 0),
    }


def _norm_model(row: dict) -> dict:
    """Canonical read model for a model entity.

    Adds a computed ``name`` field (COALESCE of display_name and
    primary_name) so consumers have a single stable display value.
    """
    return {
        "id": row["id"],
        "uuid": row.get("uuid") or "",
        "name": row.get("display_name") or row.get("primary_name"),
        "display_name": row.get("display_name"),
        "primary_name": row.get("primary_name"),
        "description": row.get("description"),
        "country": row.get("country"),
        "ethnicity": row.get("ethnicity"),
        "eye_color": row.get("eye_color"),
        "natural_hair_color": row.get("natural_hair_color"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _norm_model_album_assoc(row: dict) -> dict:
    """Albums associated with a model (used in model detail view)."""
    return {
        "id": row["id"],
        "title": row.get("title"),
        "capture_date": row.get("capture_date"),
        "age_when_shot": row.get("age_when_shot"),
        "role": row.get("role"),
        "remarks": row.get("remarks"),
        "studio_name": row.get("studio_name"),
    }


def _norm_studio(row: dict) -> dict:
    """Canonical read model for a studio entity."""
    return {
        "id": row["id"],
        "uuid": row.get("uuid") or "",
        "name": row.get("name"),
        "website": row.get("website"),
        "description": row.get("description"),
        "media_scope": row.get("media_scope"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _norm_studio_album_assoc(row: dict) -> dict:
    """Albums associated with a studio (used in studio detail view)."""
    return {
        "id": row["id"],
        "title": row.get("title"),
        "capture_date": row.get("capture_date"),
        "publish_date": row.get("publish_date"),
        "rating": row.get("rating"),
        "status_name": row.get("status_name"),
    }


def _norm_album_list(row: dict) -> dict:
    """Album read model for list/search results.

    Normalizes ``model_names`` from a SQL GROUP_CONCAT string to a
    Python list so consumers never need to split database-specific
    aggregate output.
    """
    raw_names = row.get("model_names") or ""
    model_names = [n for n in raw_names.split(",") if n]
    return {
        "id": row["id"],
        "uuid": row.get("uuid") or "",
        "title": row.get("title"),
        "description": row.get("description"),
        "scene": row.get("scene"),
        "location": row.get("location"),
        "capture_date": row.get("capture_date"),
        "publish_date": row.get("publish_date"),
        "rating": row.get("rating"),
        "path": row.get("path"),
        "remark": row.get("remark"),
        "studio_id": row.get("studio_id"),
        "status_id": row.get("status_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "studio_name": row.get("studio_name"),
        "status_name": row.get("status_name"),
        "model_names": model_names,
    }


def _norm_album_detail(row: dict) -> dict:
    """Album read model for single-record detail views."""
    return {
        "id": row["id"],
        "uuid": row.get("uuid") or "",
        "title": row.get("title"),
        "description": row.get("description"),
        "scene": row.get("scene"),
        "location": row.get("location"),
        "capture_date": row.get("capture_date"),
        "publish_date": row.get("publish_date"),
        "rating": row.get("rating"),
        "path": row.get("path"),
        "remark": row.get("remark"),
        "studio_id": row.get("studio_id"),
        "status_id": row.get("status_id"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "studio_name": row.get("studio_name"),
        "status_name": row.get("status_name"),
    }


def _norm_album_model_assoc(row: dict) -> dict:
    """Model associations on an album (used in album detail view)."""
    return {
        "id": row["id"],
        "model_id": row.get("model_id"),
        "age_when_shot": row.get("age_when_shot"),
        "role": row.get("role"),
        "remarks": row.get("remarks"),
        "model_name": row.get("model_name"),
    }


def _norm_album_relation_assoc(row: dict) -> dict:
    """Relation associations on an album (used in album detail view)."""
    return {
        "id": row["id"],
        "related_album_id": row.get("related_album_id"),
        "relation_type": row.get("relation_type"),
        "remarks": row.get("remarks"),
        "related_title": row.get("related_title"),
        "related_studio": row.get("related_studio"),
    }


def _norm_photo(row: dict) -> dict:
    """Canonical read model for a photo.

    The ``hash`` column is an internal file fingerprint and is excluded
    from all read models.
    """
    return {
        "id": row["id"],
        "uuid": row.get("uuid") or "",
        "album_id": row.get("album_id"),
        "filename": row.get("filename"),
        "relative_path": row.get("relative_path"),
        "width": row.get("width"),
        "height": row.get("height"),
        "capture_time": row.get("capture_time"),
        "created_at": row.get("created_at"),
    }


def _norm_workspace_album(row: dict) -> dict:
    """Canonical read model for a workspace album."""
    return {
        "id": row["id"],
        "uuid": row.get("uuid"),
        "studio_name": row.get("studio_name"),
        "album_name": row.get("album_name"),
        "primary_model": row.get("primary_model"),
        "additional_models": row.get("additional_models"),
        "remark": row.get("remark"),
        "current_path": row.get("current_path"),
        "expected_path": row.get("expected_path"),
        "ai_result": row.get("ai_result"),
        "belongs_to_album_id": row.get("belongs_to_album_id"),
        "album_id": row.get("album_id"),
        "status_id": row.get("status_id"),
        "status_name": row.get("status_name"),
        "lifecycle_state": row.get("lifecycle_state", "active"),
    }


def _norm_workspace_album_belongs_to(row: dict) -> dict:
    """Parent workspace album reference in a detail read model."""
    return {
        "id": row["id"],
        "album_name": row.get("album_name"),
        "primary_model": row.get("primary_model"),
    }


def _norm_workspace_album_linked_album(row: dict) -> dict:
    """Linked permanent album reference in a workspace album detail read model."""
    return {
        "id": row["id"],
        "title": row.get("title"),
    }


# ---------------------------------------------------------------------------
# StatusRepository
# ---------------------------------------------------------------------------

class StatusRepository:
    """Persistence operations for the status lookup table."""

    def __init__(self, db_factory):
        self._db = db_factory

    def list_with_counts(self) -> list[dict]:
        """Return all statuses with album and workspace_album reference counts."""
        with self._db() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.name, s.description,
                    (SELECT COUNT(*) FROM album a WHERE a.status_id = s.id)
                        AS album_count,
                    (SELECT COUNT(*) FROM workspace_album wa WHERE wa.status_id = s.id)
                        AS workspace_album_count
                FROM status s ORDER BY s.id
                """
            ).fetchall()
        return [_norm_status_with_counts(dict(r)) for r in rows]

    def create(self, name: str, description: str) -> dict:
        """Insert a new status and return the persisted record."""
        with self._db() as conn:
            cur = conn.execute(
                "INSERT INTO status (name, description) VALUES (?, ?)",
                (name, description),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM status WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return {"id": cur.lastrowid, "status": _norm_status(dict(row))}

    def update(self, status_id: int, name: str, description: str) -> dict | None:
        """Update a status and return the refreshed record, or None if not found."""
        with self._db() as conn:
            conn.execute(
                "UPDATE status SET name = ?, description = ? WHERE id = ?",
                (name, description, status_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM status WHERE id = ?", (status_id,)
            ).fetchone()
        return _norm_status(dict(row)) if row is not None else None

    def delete(self, status_id: int) -> None:
        """Atomically verify no references exist, then delete the status.

        Raises:
            PersistenceConflict: if any album or workspace_album references
                this status.
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
                raise PersistenceConflict(
                    {"album_refs": album_refs, "workspace_album_refs": wa_refs}
                )
            conn.execute("DELETE FROM status WHERE id = ?", (status_id,))
            conn.commit()


# ---------------------------------------------------------------------------
# ModelRepository
# ---------------------------------------------------------------------------

class ModelRepository:
    """Persistence operations for the model entity."""

    def __init__(self, db_factory):
        self._db = db_factory

    def search(self, q: str, limit: int, offset: int) -> tuple[list[dict], int]:
        """Return a page of models matching q, plus the total unfiltered count."""
        pattern = f"%{q}%" if q else "%%"
        with self._db() as conn:
            rows = conn.execute(
                """
                SELECT id, uuid, display_name, primary_name, description,
                    country, ethnicity, eye_color, natural_hair_color,
                    created_at, updated_at
                FROM model
                WHERE (display_name LIKE ? OR primary_name LIKE ?)
                ORDER BY COALESCE(display_name, primary_name)
                LIMIT ? OFFSET ?
                """,
                (pattern, pattern, limit, offset),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM model"
                " WHERE (display_name LIKE ? OR primary_name LIKE ?)",
                (pattern, pattern),
            ).fetchone()[0]
        return [_norm_model(dict(r)) for r in rows], total

    def get_by_id(self, model_id: int) -> dict | None:
        """Return model record and its album list, or None if not found."""
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM model WHERE id = ?", (model_id,)
            ).fetchone()
            if row is None:
                return None
            albums = conn.execute(
                """
                SELECT a.id, a.title, a.capture_date,
                    am.age_when_shot, am.role, am.remarks,
                    s.name AS studio_name
                FROM album_model am
                JOIN album a ON a.id = am.album_id
                LEFT JOIN studio s ON s.id = a.studio_id
                WHERE am.model_id = ?
                ORDER BY a.capture_date DESC
                """,
                (model_id,),
            ).fetchall()
        return {
            "model": _norm_model(dict(row)),
            "albums": [_norm_model_album_assoc(dict(a)) for a in albums],
        }

    def create(self, data: dict) -> dict:
        """Insert a new model and return a dict with the new id and record."""
        now = _utc_now_iso()
        new_uuid = str(uuid.uuid4())
        with self._db() as conn:
            cur = conn.execute(
                """
                INSERT INTO model
                    (uuid, display_name, primary_name, description, country,
                     ethnicity, eye_color, natural_hair_color,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_uuid,
                    data.get("display_name"),
                    data.get("primary_name"),
                    data.get("description"),
                    data.get("country"),
                    data.get("ethnicity"),
                    data.get("eye_color"),
                    data.get("natural_hair_color"),
                    now,
                    now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM model WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return {"id": cur.lastrowid, "model": _norm_model(dict(row))}

    def update_fields(
        self, model_id: int, data: dict, now: str
    ) -> dict | None:
        """Update model fields and return the refreshed record, or None if not found."""
        with self._db() as conn:
            conn.execute(
                """
                UPDATE model SET
                    display_name = ?, primary_name = ?, description = ?,
                    country = ?, ethnicity = ?, eye_color = ?,
                    natural_hair_color = ?, updated_at = ?
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
        return _norm_model(dict(row)) if row is not None else None

    def find_by_name(self, name: str) -> dict | None:
        """Return a model matching the given name (case-insensitive), or None."""
        with self._db() as conn:
            row = conn.execute(
                "SELECT id FROM model"
                " WHERE LOWER(display_name) = LOWER(?)"
                "    OR LOWER(primary_name) = LOWER(?)",
                (name, name),
            ).fetchone()
        return dict(row) if row is not None else None

    def find_or_create(self, name: str, now: str) -> int:
        """Return the id of the model with this name, creating it if absent."""
        with self._db() as conn:
            row = conn.execute(
                "SELECT id FROM model"
                " WHERE LOWER(display_name) = LOWER(?)"
                "    OR LOWER(primary_name) = LOWER(?)",
                (name, name),
            ).fetchone()
            if row is not None:
                return row["id"]
            new_uuid = str(uuid.uuid4())
            cur = conn.execute(
                "INSERT INTO model (uuid, display_name, created_at, updated_at)"
                " VALUES (?, ?, ?, ?)",
                (new_uuid, name, now, now),
            )
            conn.commit()
            return cur.lastrowid

    def delete(self, model_id: int) -> None:
        """Atomically verify no album references exist, then delete the model.

        Raises:
            PersistenceConflict: if the model is referenced by any album.
        """
        with self._db() as conn:
            refs = conn.execute(
                "SELECT COUNT(*) FROM album_model WHERE model_id = ?",
                (model_id,),
            ).fetchone()[0]
            if refs > 0:
                raise PersistenceConflict({"album_refs": refs})
            conn.execute("DELETE FROM model WHERE id = ?", (model_id,))
            conn.commit()


# ---------------------------------------------------------------------------
# StudioRepository
# ---------------------------------------------------------------------------

class StudioRepository:
    """Persistence operations for the studio entity."""

    def __init__(self, db_factory):
        self._db = db_factory

    def search(self, q: str, limit: int, offset: int) -> tuple[list[dict], int]:
        """Return a page of studios matching q, plus the total unfiltered count."""
        pattern = f"%{q}%" if q else "%%"
        with self._db() as conn:
            rows = conn.execute(
                """
                SELECT id, uuid, name, website, description, media_scope,
                    created_at, updated_at
                FROM studio WHERE name LIKE ? ORDER BY name
                LIMIT ? OFFSET ?
                """,
                (pattern, limit, offset),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM studio WHERE name LIKE ?", (pattern,)
            ).fetchone()[0]
        return [_norm_studio(dict(r)) for r in rows], total

    def get_by_id(self, studio_id: int) -> dict | None:
        """Return studio record and its album list, or None if not found."""
        with self._db() as conn:
            row = conn.execute(
                "SELECT * FROM studio WHERE id = ?", (studio_id,)
            ).fetchone()
            if row is None:
                return None
            albums = conn.execute(
                """
                SELECT a.id, a.title, a.capture_date, a.publish_date, a.rating,
                    st.name AS status_name
                FROM album a
                LEFT JOIN status st ON st.id = a.status_id
                WHERE a.studio_id = ?
                ORDER BY a.publish_date DESC
                """,
                (studio_id,),
            ).fetchall()
        return {
            "studio": _norm_studio(dict(row)),
            "albums": [_norm_studio_album_assoc(dict(a)) for a in albums],
        }

    def create(self, data: dict) -> dict:
        """Insert a new studio and return a dict with the new id and record."""
        now = _utc_now_iso()
        new_uuid = str(uuid.uuid4())
        with self._db() as conn:
            cur = conn.execute(
                """
                INSERT INTO studio
                    (uuid, name, website, description, media_scope,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_uuid,
                    data.get("name"),
                    data.get("website"),
                    data.get("description"),
                    data.get("media_scope"),
                    now,
                    now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM studio WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return {"id": cur.lastrowid, "studio": _norm_studio(dict(row))}

    def update(self, studio_id: int, data: dict, now: str) -> dict | None:
        """Update a studio and return the refreshed record, or None if not found."""
        with self._db() as conn:
            conn.execute(
                """
                UPDATE studio SET
                    name = ?, website = ?, description = ?,
                    media_scope = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    data.get("name"),
                    data.get("website"),
                    data.get("description"),
                    data.get("media_scope"),
                    now,
                    studio_id,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM studio WHERE id = ?", (studio_id,)
            ).fetchone()
        return _norm_studio(dict(row)) if row is not None else None

    def find_by_name(self, name: str) -> dict | None:
        """Return a studio matching the given name (case-insensitive), or None."""
        with self._db() as conn:
            row = conn.execute(
                "SELECT id, name FROM studio WHERE LOWER(name) = LOWER(?)",
                (name,),
            ).fetchone()
        return dict(row) if row is not None else None

    def find_or_create(self, name: str, now: str) -> int:
        """Return the id of the studio with this name, creating it if absent."""
        with self._db() as conn:
            row = conn.execute(
                "SELECT id FROM studio WHERE LOWER(name) = LOWER(?)", (name,)
            ).fetchone()
            if row is not None:
                return row["id"]
            new_uuid = str(uuid.uuid4())
            cur = conn.execute(
                "INSERT INTO studio (uuid, name, created_at, updated_at)"
                " VALUES (?, ?, ?, ?)",
                (new_uuid, name, now, now),
            )
            conn.commit()
            return cur.lastrowid

    def delete(self, studio_id: int) -> None:
        """Atomically verify no album references exist, then delete the studio.

        Raises:
            PersistenceConflict: if the studio is referenced by any album.
        """
        with self._db() as conn:
            refs = conn.execute(
                "SELECT COUNT(*) FROM album WHERE studio_id = ?", (studio_id,)
            ).fetchone()[0]
            if refs > 0:
                raise PersistenceConflict({"album_refs": refs})
            conn.execute("DELETE FROM studio WHERE id = ?", (studio_id,))
            conn.commit()


# ---------------------------------------------------------------------------
# AlbumRepository
# ---------------------------------------------------------------------------

class AlbumRepository:
    """Persistence operations for the album entity and its associations."""

    _SORT_MAP = {
        "title": "a.title",
        "studio_name": "s.name",
        "publish_date": "a.publish_date",
        "rating": "a.rating",
        "updated_at": "a.updated_at",
        "capture_date": "a.capture_date",
    }

    def __init__(self, db_factory):
        self._db = db_factory

    def search(
        self,
        q: str = "",
        studio_id: str = "",
        status_id: str = "",
        model_id: str = "",
        rating_min: str = "",
        rating_max: str = "",
        capture_date_from: str = "",
        capture_date_to: str = "",
        publish_date_from: str = "",
        publish_date_to: str = "",
        sort: str = "updated_at",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Return a filtered, sorted page of albums plus the total count."""
        order_col = self._SORT_MAP.get(sort, "a.updated_at")
        conditions: list[str] = []
        params: list = []

        if q:
            pattern = f"%{q}%"
            conditions.append(
                "(a.title LIKE ? OR a.description LIKE ? OR a.location LIKE ?"
                " OR a.scene LIKE ? OR s.name LIKE ? OR EXISTS ("
                "SELECT 1 FROM album_model amq JOIN model mq ON mq.id = amq.model_id"
                " WHERE amq.album_id = a.id"
                " AND (mq.display_name LIKE ? OR mq.primary_name LIKE ?)))"
            )
            params += [pattern] * 7
        if studio_id:
            conditions.append("a.studio_id = ?")
            params.append(int(studio_id))
        if status_id:
            conditions.append("a.status_id = ?")
            params.append(int(status_id))
        if model_id:
            conditions.append(
                "EXISTS (SELECT 1 FROM album_model am2"
                " WHERE am2.album_id = a.id AND am2.model_id = ?)"
            )
            params.append(int(model_id))
        if rating_min:
            conditions.append("a.rating >= ?")
            params.append(float(rating_min))
        if rating_max:
            conditions.append("a.rating <= ?")
            params.append(float(rating_max))
        for value, column, operator in (
            (capture_date_from, "a.capture_date", ">="),
            (capture_date_to, "a.capture_date", "<="),
            (publish_date_from, "a.publish_date", ">="),
            (publish_date_to, "a.publish_date", "<="),
        ):
            if value:
                conditions.append(f"{column} {operator} ?")
                params.append(value)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        query = f"""
            SELECT a.id, a.uuid, a.title, a.description, a.scene, a.location,
                a.capture_date, a.publish_date, a.rating, a.path, a.remark,
                a.studio_id, a.status_id, a.created_at, a.updated_at,
                s.name AS studio_name,
                st.name AS status_name,
                GROUP_CONCAT(DISTINCT COALESCE(m.display_name, m.primary_name))
                    AS model_names
            FROM album a
            LEFT JOIN studio s ON s.id = a.studio_id
            LEFT JOIN status st ON st.id = a.status_id
            LEFT JOIN album_model am ON am.album_id = a.id
            LEFT JOIN model m ON m.id = am.model_id
            {where}
            GROUP BY a.id
            ORDER BY {order_col} DESC
            LIMIT ? OFFSET ?
        """
        count_query = f"""
            SELECT COUNT(DISTINCT a.id)
            FROM album a
            LEFT JOIN studio s ON s.id = a.studio_id
            LEFT JOIN status st ON st.id = a.status_id
            {where}
        """
        with self._db() as conn:
            rows = conn.execute(query, params + [limit, offset]).fetchall()
            total = conn.execute(count_query, params).fetchone()[0]
        return [_norm_album_list(dict(r)) for r in rows], total

    def get_batch_state(self, album_ids: list[int]) -> list[dict]:
        """Return stable fields used by Album batch preview and stale checks."""
        if not album_ids:
            return []
        placeholders = ",".join("?" for _ in album_ids)
        with self._db() as conn:
            rows = conn.execute(
                f"SELECT id, uuid, title, studio_id, status_id, rating, description,"
                f" scene, location, capture_date, publish_date, remark, updated_at"
                f" FROM album WHERE id IN ({placeholders}) ORDER BY id",
                album_ids,
            ).fetchall()
        return [dict(row) for row in rows]

    def relationship_targets_exist(
        self, model_ids: set[int], related_album_ids: set[int]
    ) -> tuple[set[int], set[int]]:
        """Return the subsets of requested Model and Album ids that exist."""
        with self._db() as conn:
            found_models: set[int] = set()
            found_albums: set[int] = set()
            if model_ids:
                marks = ",".join("?" for _ in model_ids)
                found_models = {
                    int(row[0]) for row in conn.execute(
                        f"SELECT id FROM model WHERE id IN ({marks})", sorted(model_ids)
                    )
                }
            if related_album_ids:
                marks = ",".join("?" for _ in related_album_ids)
                found_albums = {
                    int(row[0]) for row in conn.execute(
                        f"SELECT id FROM album WHERE id IN ({marks})", sorted(related_album_ids)
                    )
                }
        return found_models, found_albums

    def batch_update(
        self, album_ids: list[int], changes: dict, expected_versions: dict[int, str], now: str
    ) -> list[dict]:
        """Atomically apply a reviewed batch when every Album version still matches."""
        columns = list(changes)
        assignments = ", ".join(f"{column} = ?" for column in columns)
        with self._db() as conn:
            try:
                conn.execute("BEGIN")
                for album_id in album_ids:
                    current = conn.execute(
                        "SELECT updated_at FROM album WHERE id = ?", (album_id,)
                    ).fetchone()
                    if current is None or current[0] != expected_versions[album_id]:
                        raise PersistenceConflict({"album_id": album_id, "reason": "stale"})
                for album_id in album_ids:
                    conn.execute(
                        f"UPDATE album SET {assignments}, updated_at = ? WHERE id = ?",
                        [changes[column] for column in columns] + [now, album_id],
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return self.get_batch_state(album_ids)

    def get_by_id(self, album_id: int) -> dict | None:
        """Return album with studio, status, models, relations and photos, or None."""
        with self._db() as conn:
            row = conn.execute(
                """
                SELECT a.*, s.name AS studio_name, st.name AS status_name
                FROM album a
                LEFT JOIN studio s ON s.id = a.studio_id
                LEFT JOIN status st ON st.id = a.status_id
                WHERE a.id = ?
                """,
                (album_id,),
            ).fetchone()
            if row is None:
                return None
            models = conn.execute(
                """
                SELECT am.id, am.model_id, am.age_when_shot, am.role, am.remarks,
                    COALESCE(m.display_name, m.primary_name) AS model_name
                FROM album_model am
                JOIN model m ON m.id = am.model_id
                WHERE am.album_id = ?
                """,
                (album_id,),
            ).fetchall()
            relations = conn.execute(
                """
                SELECT ar.id, ar.related_album_id, ar.relation_type, ar.remarks,
                    a2.title AS related_title, s2.name AS related_studio
                FROM album_relation ar
                JOIN album a2 ON a2.id = ar.related_album_id
                LEFT JOIN studio s2 ON s2.id = a2.studio_id
                WHERE ar.album_id = ?
                """,
                (album_id,),
            ).fetchall()
            photos = conn.execute(
                """
                SELECT id, uuid, album_id, filename, relative_path, width, height,
                    capture_time, created_at
                FROM photo WHERE album_id = ? ORDER BY filename
                """,
                (album_id,),
            ).fetchall()
        return {
            "album": _norm_album_detail(dict(row)),
            "models": [_norm_album_model_assoc(dict(m)) for m in models],
            "relations": [_norm_album_relation_assoc(dict(r)) for r in relations],
            "photos": [_norm_photo(dict(p)) for p in photos],
        }

    def create(
        self, data: dict, models: list, relations: list, now: str
    ) -> int:
        """Atomically insert album, album_model rows, and album_relation rows.

        Returns:
            The new album's integer id.
        """
        new_uuid = str(uuid.uuid4())
        with self._db() as conn:
            try:
                conn.execute("BEGIN")
                cur = conn.execute(
                    """
                    INSERT INTO album
                        (uuid, studio_id, status_id, title, description,
                         scene, location, capture_date, publish_date,
                         rating, path, remark, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        data.get("remark"),
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
        return album_id

    def update(
        self, album_id: int, data: dict, models: list, relations: list, now: str
    ) -> None:
        """Atomically replace album fields, model list, and relation list."""
        with self._db() as conn:
            try:
                conn.execute("BEGIN")
                conn.execute(
                    """
                    UPDATE album SET
                        studio_id = ?, status_id = ?, title = ?,
                        description = ?, scene = ?, location = ?,
                        capture_date = ?, publish_date = ?,
                        rating = ?, path = ?, remark = ?, updated_at = ?
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
                        data.get("remark"),
                        now,
                        album_id,
                    ),
                )
                conn.execute(
                    "DELETE FROM album_model WHERE album_id = ?", (album_id,)
                )
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

    def delete(self, album_id: int) -> None:
        """Atomically delete an album and all its associated records."""
        with self._db() as conn:
            try:
                conn.execute("BEGIN")
                conn.execute(
                    "DELETE FROM album_model WHERE album_id = ?", (album_id,)
                )
                conn.execute(
                    "DELETE FROM album_relation"
                    " WHERE album_id = ? OR related_album_id = ?",
                    (album_id, album_id),
                )
                conn.execute(
                    "DELETE FROM photo WHERE album_id = ?", (album_id,)
                )
                conn.execute("DELETE FROM album WHERE id = ?", (album_id,))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def find_by_studio_and_title(
        self, studio_id: int, title: str
    ) -> dict | None:
        """Return an album matching the given studio and title (case-insensitive)."""
        with self._db() as conn:
            row = conn.execute(
                "SELECT id FROM album"
                " WHERE studio_id = ? AND LOWER(title) = LOWER(?)",
                (studio_id, title),
            ).fetchone()
        return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# AlbumModelRepository
# ---------------------------------------------------------------------------

class AlbumModelRepository:
    """Persistence operations for the album_model join table."""

    def __init__(self, db_factory):
        self._db = db_factory

    def add(self, album_id: int, data: dict) -> int:
        """Insert a model association and return the new row id."""
        with self._db() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_model
                    (album_id, model_id, age_when_shot, role, remarks)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    album_id,
                    data.get("model_id"),
                    data.get("age_when_shot"),
                    data.get("role"),
                    data.get("remarks"),
                ),
            )
            conn.commit()
        return cur.lastrowid

    def update(self, album_id: int, am_id: int, data: dict) -> None:
        """Update a model association row."""
        with self._db() as conn:
            conn.execute(
                """
                UPDATE album_model SET
                    age_when_shot = ?, role = ?, remarks = ?
                WHERE id = ? AND album_id = ?
                """,
                (
                    data.get("age_when_shot"),
                    data.get("role"),
                    data.get("remarks"),
                    am_id,
                    album_id,
                ),
            )
            conn.commit()

    def delete(self, album_id: int, am_id: int) -> None:
        """Remove a model association row."""
        with self._db() as conn:
            conn.execute(
                "DELETE FROM album_model WHERE id = ? AND album_id = ?",
                (am_id, album_id),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# AlbumRelationRepository
# ---------------------------------------------------------------------------

class AlbumRelationRepository:
    """Persistence operations for the album_relation join table."""

    def __init__(self, db_factory):
        self._db = db_factory

    def add(self, album_id: int, data: dict) -> int:
        """Insert a relation and return the new row id."""
        with self._db() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_relation
                    (album_id, related_album_id, relation_type, remarks)
                VALUES (?, ?, ?, ?)
                """,
                (
                    album_id,
                    data.get("related_album_id"),
                    data.get("relation_type"),
                    data.get("remarks"),
                ),
            )
            conn.commit()
        return cur.lastrowid

    def update(self, album_id: int, relation_id: int, data: dict) -> None:
        """Update a relation row."""
        with self._db() as conn:
            conn.execute(
                """
                UPDATE album_relation SET
                    relation_type = ?, remarks = ?
                WHERE id = ? AND album_id = ?
                """,
                (
                    data.get("relation_type"),
                    data.get("remarks"),
                    relation_id,
                    album_id,
                ),
            )
            conn.commit()

    def delete(self, album_id: int, relation_id: int) -> None:
        """Remove a relation row."""
        with self._db() as conn:
            conn.execute(
                "DELETE FROM album_relation WHERE id = ? AND album_id = ?",
                (relation_id, album_id),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# PhotoRepository
# ---------------------------------------------------------------------------

class PhotoRepository:
    """Persistence operations for the photo entity."""

    def __init__(self, db_factory):
        self._db = db_factory

    def add(self, album_id: int, data: dict) -> int:
        """Insert a photo record and return the new row id."""
        now = _utc_now_iso()
        new_uuid = str(uuid.uuid4())
        with self._db() as conn:
            cur = conn.execute(
                """
                INSERT INTO photo
                    (uuid, album_id, filename, relative_path, hash,
                     width, height, capture_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_uuid,
                    album_id,
                    data.get("filename"),
                    data.get("relative_path"),
                    data.get("hash"),
                    data.get("width"),
                    data.get("height"),
                    data.get("capture_time"),
                    now,
                ),
            )
            conn.commit()
        return cur.lastrowid

    def update(self, photo_id: int, data: dict) -> None:
        """Update editable photo fields."""
        with self._db() as conn:
            conn.execute(
                """
                UPDATE photo SET
                    filename = ?, relative_path = ?,
                    width = ?, height = ?, capture_time = ?
                WHERE id = ?
                """,
                (
                    data.get("filename"),
                    data.get("relative_path"),
                    data.get("width"),
                    data.get("height"),
                    data.get("capture_time"),
                    photo_id,
                ),
            )
            conn.commit()

    def delete(self, photo_id: int) -> None:
        """Remove a photo record."""
        with self._db() as conn:
            conn.execute("DELETE FROM photo WHERE id = ?", (photo_id,))
            conn.commit()


# ---------------------------------------------------------------------------
# WorkspaceAlbumRepository
# ---------------------------------------------------------------------------

class WorkspaceAlbumRepository:
    """Persistence operations for workspace_album records."""

    def __init__(self, db_factory):
        self._db = db_factory

    def search(
        self,
        status_id: str = "",
        studio_name: str = "",
        primary_model: str = "",
        linked: str = "",
        q: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Return a filtered page of workspace albums plus the total count."""
        conditions: list[str] = []
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
                "(wa.album_name LIKE ? OR wa.primary_model LIKE ?"
                " OR wa.studio_name LIKE ?)"
            )
            params += [f"%{q}%", f"%{q}%", f"%{q}%"]

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        query = f"""
            SELECT wa.*, s.name AS status_name
            FROM workspace_album wa
            LEFT JOIN status s ON s.id = wa.status_id
            {where}
            ORDER BY wa.id DESC
            LIMIT ? OFFSET ?
        """
        count_query = f"""
            SELECT COUNT(*) FROM workspace_album wa
            LEFT JOIN status s ON s.id = wa.status_id
            {where}
        """
        with self._db() as conn:
            rows = conn.execute(query, params + [limit, offset]).fetchall()
            total = conn.execute(count_query, params).fetchone()[0]
        return [_norm_workspace_album(dict(r)) for r in rows], total

    def get_by_id(self, wa_id: int) -> dict | None:
        """Return workspace album with belongs_to and linked_album context, or None."""
        with self._db() as conn:
            row = conn.execute(
                """
                SELECT wa.*, s.name AS status_name
                FROM workspace_album wa
                LEFT JOIN status s ON s.id = wa.status_id
                WHERE wa.id = ?
                """,
                (wa_id,),
            ).fetchone()
            if row is None:
                return None
            raw = dict(row)
            normalized = _norm_workspace_album(raw)
            if raw.get("belongs_to_album_id"):
                parent = conn.execute(
                    "SELECT id, album_name, primary_model"
                    " FROM workspace_album WHERE id = ?",
                    (raw["belongs_to_album_id"],),
                ).fetchone()
                normalized["belongs_to"] = (
                    _norm_workspace_album_belongs_to(dict(parent)) if parent else None
                )
            else:
                normalized["belongs_to"] = None
            if raw.get("album_id"):
                linked = conn.execute(
                    "SELECT id, title FROM album WHERE id = ?", (raw["album_id"],)
                ).fetchone()
                normalized["linked_album"] = (
                    _norm_workspace_album_linked_album(dict(linked)) if linked else None
                )
            else:
                normalized["linked_album"] = None
        return normalized

    @staticmethod
    def _historical_item(row: dict) -> dict:
        """Return an Admin audit model without filesystem or raw AI fields."""
        allowed = (
            "id", "uuid", "status_id", "status_name", "studio_name", "album_name",
            "primary_model", "additional_models", "remark", "belongs_to_album_id",
            "album_id", "lifecycle_state", "archive_classification", "archive_reason",
            "archived_at", "archive_operation_uuid",
        )
        return {key: row.get(key) for key in allowed}

    def search_historical(self, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
        """List only closed/archived historical rows for Admin audit."""
        with self._db() as conn:
            rows = conn.execute(
                """SELECT wa.*, s.name AS status_name FROM workspace_album wa
                   LEFT JOIN status s ON s.id = wa.status_id
                   WHERE wa.lifecycle_state IN ('closed', 'archived_retired')
                   ORDER BY wa.id DESC LIMIT ? OFFSET ?""", (limit, offset),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM workspace_album WHERE lifecycle_state IN ('closed','archived_retired')"
            ).fetchone()[0]
        return [self._historical_item(dict(row)) for row in rows], total

    def get_historical(self, wa_id: int) -> dict | None:
        """Return one terminal historical row, never an active/review row."""
        with self._db() as conn:
            row = conn.execute(
                """SELECT wa.*, s.name AS status_name FROM workspace_album wa
                   LEFT JOIN status s ON s.id = wa.status_id
                   WHERE wa.id=? AND wa.lifecycle_state IN ('closed','archived_retired')""",
                (wa_id,),
            ).fetchone()
        return self._historical_item(dict(row)) if row else None

    def update(self, wa_id: int, allowed_fields: frozenset, changes: dict) -> None:
        """Apply an allow-listed subset of changes to a single workspace album."""
        filtered = {k: v for k, v in changes.items() if k in allowed_fields}
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

    def batch_update(
        self, ids: list, allowed_fields: frozenset, changes: dict
    ) -> int:
        """Apply an allow-listed subset of changes to multiple workspace albums.

        Returns:
            The number of rows updated.
        """
        filtered = {k: v for k, v in changes.items() if k in allowed_fields}
        if not filtered:
            raise ValueError("No valid fields to update were supplied.")
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
    def create(self, fields: dict) -> dict:
        """Create a new workspace album with lifecycle_state='active'.

        All supplied fields are filtered to the allow-list; ``lifecycle_state``
        is always set to ``'active'``; ``uuid`` is auto-generated when absent.

        Returns:
            The normalized workspace album read model for the new record.
        """
        _creatable = frozenset({
            "uuid", "status_id", "studio_name", "album_name", "primary_model",
            "additional_models", "remark", "current_path", "expected_path",
            "ai_result", "belongs_to_album_id", "album_id",
        })
        filtered = {k: v for k, v in fields.items() if k in _creatable}
        filtered["lifecycle_state"] = "active"
        if "uuid" not in filtered:
            filtered["uuid"] = str(uuid.uuid4())
        columns = ", ".join(filtered.keys())
        placeholders = ", ".join("?" * len(filtered))
        with self._db() as conn:
            cur = conn.execute(
                f"INSERT INTO workspace_album ({columns}) VALUES ({placeholders})",
                list(filtered.values()),
            )
            new_id = cur.lastrowid
            conn.commit()
            row = conn.execute(
                """
                SELECT wa.*, s.name AS status_name
                FROM workspace_album wa
                LEFT JOIN status s ON s.id = wa.status_id
                WHERE wa.id = ?
                """,
                (new_id,),
            ).fetchone()
        return _norm_workspace_album(dict(row))

    def get_lifecycle_state(self, wa_id: int) -> str | None:
        """Return the current lifecycle state for a workspace album.

        Returns:
            The lifecycle state string, or ``None`` when the record does not
            exist.
        """
        with self._db() as conn:
            row = conn.execute(
                "SELECT lifecycle_state FROM workspace_album WHERE id = ?",
                (wa_id,),
            ).fetchone()
        return row["lifecycle_state"] if row else None

    def set_lifecycle_state(self, wa_id: int, state: str) -> None:
        """Persist a lifecycle state transition for a workspace album.

        Args:
            wa_id: Integer primary key of the workspace album to update.
            state: The target lifecycle state string to write.
        """
        with self._db() as conn:
            conn.execute(
                "UPDATE workspace_album SET lifecycle_state = ? WHERE id = ?",
                (state, wa_id),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# ImportRepository
# ---------------------------------------------------------------------------

class AIWorkspaceRepository:
    """Persistence for versioned AI Workspace containers, never legacy rows."""

    DATASET_TYPE = "album_analysis"
    SCHEMA_VERSION = 1

    def __init__(self, db_factory): self._db = db_factory

    @classmethod
    def _ensure_schema(cls, conn) -> None:
        conn.execute("""CREATE TABLE IF NOT EXISTS ai_dataset_schema (
            dataset_type TEXT NOT NULL, schema_version INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Active','Retired')),
            definition_json TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(dataset_type,schema_version))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS ai_workspace (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL UNIQUE,
            dataset_type TEXT NOT NULL, schema_version INTEGER NOT NULL,
            title TEXT NOT NULL, lifecycle_state TEXT NOT NULL DEFAULT 'Open'
                CHECK(lifecycle_state IN ('Open','Closed','Archived')),
            created_by_token_uuid TEXT, created_at TEXT NOT NULL, closed_at TEXT,
            archived_at TEXT, version INTEGER NOT NULL DEFAULT 1,
            close_operation_uuid TEXT, archive_operation_uuid TEXT,
            FOREIGN KEY(dataset_type,schema_version)
                REFERENCES ai_dataset_schema(dataset_type,schema_version))""")
        now = datetime.now(timezone.utc).isoformat()
        definition = json.dumps({"dataset_type": cls.DATASET_TYPE, "schema_version": cls.SCHEMA_VERSION,
                                 "item_type": "workspace_album_ai_worker"}, sort_keys=True)
        conn.execute("INSERT OR IGNORE INTO ai_dataset_schema VALUES (?,?,?,?,?)",
                     (cls.DATASET_TYPE, cls.SCHEMA_VERSION, "Active", definition, now))
        conn.commit()

    @staticmethod
    def _norm(row) -> dict:
        return {key: row[key] for key in (
            "id", "uuid", "dataset_type", "schema_version", "title", "lifecycle_state",
            "created_by_token_uuid", "created_at", "closed_at", "archived_at", "version",
            "close_operation_uuid", "archive_operation_uuid")}

    def create(self, fields: dict) -> dict:
        with self._db() as conn:
            self._ensure_schema(conn)
            cur = conn.execute("""INSERT INTO ai_workspace
                (uuid,dataset_type,schema_version,title,lifecycle_state,created_by_token_uuid,created_at)
                VALUES (?,?,?,?, 'Open', ?,?)""", (
                fields.get("uuid") or str(uuid.uuid4()), fields["dataset_type"],
                fields["schema_version"], fields["title"], fields.get("created_by_token_uuid"),
                fields["created_at"],
            )); conn.commit()
            row = conn.execute("SELECT * FROM ai_workspace WHERE id=?", (cur.lastrowid,)).fetchone()
        return self._norm(row)

    def get(self, workspace_uuid: str) -> dict | None:
        with self._db() as conn:
            self._ensure_schema(conn); row = conn.execute("SELECT * FROM ai_workspace WHERE uuid=?", (workspace_uuid,)).fetchone()
        return self._norm(row) if row else None

    def list(self, lifecycle_state: str | None = None) -> list[dict]:
        with self._db() as conn:
            self._ensure_schema(conn)
            if lifecycle_state:
                rows = conn.execute("SELECT * FROM ai_workspace WHERE lifecycle_state=? ORDER BY created_at DESC,id DESC", (lifecycle_state,)).fetchall()
            else: rows = conn.execute("SELECT * FROM ai_workspace ORDER BY created_at DESC,id DESC").fetchall()
        return [self._norm(row) for row in rows]

    def transition(self, workspace_uuid: str, expected_version: int, from_state: str,
                   to_state: str, operation_uuid: str, at: str) -> dict | None:
        time_field = "closed_at" if to_state == "Closed" else "archived_at"
        op_field = "close_operation_uuid" if to_state == "Closed" else "archive_operation_uuid"
        with self._db() as conn:
            self._ensure_schema(conn)
            cur = conn.execute(f"""UPDATE ai_workspace SET lifecycle_state=?, {time_field}=?,
                {op_field}=?, version=version+1 WHERE uuid=? AND version=? AND lifecycle_state=?""",
                (to_state, at, operation_uuid, workspace_uuid, expected_version, from_state))
            conn.commit(); row = conn.execute("SELECT * FROM ai_workspace WHERE uuid=?", (workspace_uuid,)).fetchone()
        return self._norm(row) if cur.rowcount == 1 else (self._norm(row) if row else None)


class ImportRepository:
    """Persistence operations for the album import workflow."""

    def __init__(self, db_factory):
        self._db = db_factory

    def lookup_preview_item(
        self, studio_name: str, model_name: str, album_name: str
    ) -> dict:
        """Return existence flags and ids for the given import candidate.

        Used by the import preview operation (read-only lookups).
        """
        with self._db() as conn:
            studio_row = conn.execute(
                "SELECT id, name FROM studio WHERE LOWER(name) = LOWER(?)",
                (studio_name,),
            ).fetchone()
            studio_exists = studio_row is not None
            studio_id = studio_row["id"] if studio_row else None

            model_row = conn.execute(
                "SELECT id FROM model"
                " WHERE LOWER(display_name) = LOWER(?)"
                "    OR LOWER(primary_name) = LOWER(?)",
                (model_name, model_name),
            ).fetchone()
            model_exists = model_row is not None
            model_id = model_row["id"] if model_row else None

            album_exists = False
            album_id = None
            if studio_id:
                album_row = conn.execute(
                    "SELECT id FROM album"
                    " WHERE studio_id = ? AND LOWER(title) = LOWER(?)",
                    (studio_id, album_name),
                ).fetchone()
                if album_row:
                    album_exists = True
                    album_id = album_row["id"]

        return {
            "studio_exists": studio_exists,
            "studio_id": studio_id,
            "model_exists": model_exists,
            "model_id": model_id,
            "album_exists": album_exists,
            "album_id": album_id,
        }

    def lookup_path_collision(self, comparison_key: str) -> bool:
        """Return ``True`` when any album's stored path matches the comparison key.

        Uses ``LOWER(path) = ?`` for SQL-level filtering (covers ASCII paths),
        where *comparison_key* is the casefolded canonical path key produced by
        :func:`canonical_path.comparison_key`. This detects occupied canonical
        paths that would cause a uniqueness conflict even when the title-based
        duplicate check (``lookup_preview_item``) does not fire.

        Args:
            comparison_key: The casefolded canonical path key to check against
                existing ``album.path`` values.

        Returns:
            ``True`` when at least one album occupies the same canonical path.
        """
        with self._db() as conn:
            row = conn.execute(
                "SELECT id FROM album WHERE LOWER(path) = ?",
                (comparison_key,),
            ).fetchone()
        return row is not None

    def claim_preview(self, preview_uuid: str, claimed_at: str) -> None:
        """Atomically claim a reviewed Import preview for one execution attempt."""
        with self._db() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS import_preview_claim (
                    preview_uuid TEXT PRIMARY KEY,
                    claimed_at TEXT NOT NULL
                )"""
            )
            try:
                conn.execute(
                    "INSERT INTO import_preview_claim (preview_uuid, claimed_at) VALUES (?, ?)",
                    (preview_uuid, claimed_at),
                )
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflict(
                    {"preview_uuid": preview_uuid, "reason": "already_claimed"}
                ) from exc

    def preview_is_claimed(self, preview_uuid: str) -> bool:
        """Return whether an Import preview has already begun execution."""
        with self._db() as conn:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='import_preview_claim'"
            ).fetchone()
            if not exists:
                return False
            return conn.execute(
                "SELECT 1 FROM import_preview_claim WHERE preview_uuid = ?", (preview_uuid,)
            ).fetchone() is not None


    def create_item(
        self,
        studio_name: str,
        model_name: str,
        album_name: str,
        expected_path: str,
        now: str,
    ) -> dict:
        """Atomically find-or-create studio and model, then create the album.

        Returns:
            ``{'status': 'created', 'album_id': int}`` on creation, or
            ``{'status': 'skipped', 'album_id': int}`` when the album already
            exists.
        """
        with self._db() as conn:
            try:
                conn.execute("BEGIN")

                studio_row = conn.execute(
                    "SELECT id FROM studio WHERE LOWER(name) = LOWER(?)",
                    (studio_name,),
                ).fetchone()
                if studio_row:
                    studio_id = studio_row["id"]
                else:
                    new_uuid = str(uuid.uuid4())
                    cur = conn.execute(
                        "INSERT INTO studio (uuid, name, created_at, updated_at)"
                        " VALUES (?, ?, ?, ?)",
                        (new_uuid, studio_name, now, now),
                    )
                    studio_id = cur.lastrowid

                model_row = conn.execute(
                    "SELECT id FROM model"
                    " WHERE LOWER(display_name) = LOWER(?)"
                    "    OR LOWER(primary_name) = LOWER(?)",
                    (model_name, model_name),
                ).fetchone()
                if model_row:
                    model_id = model_row["id"]
                else:
                    new_uuid = str(uuid.uuid4())
                    cur = conn.execute(
                        "INSERT INTO model"
                        " (uuid, display_name, created_at, updated_at)"
                        " VALUES (?, ?, ?, ?)",
                        (new_uuid, model_name, now, now),
                    )
                    model_id = cur.lastrowid

                album_row = conn.execute(
                    "SELECT id FROM album"
                    " WHERE studio_id = ? AND LOWER(title) = LOWER(?)",
                    (studio_id, album_name),
                ).fetchone()
                if album_row:
                    conn.rollback()
                    return {"status": "skipped", "album_id": album_row["id"]}

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
                conn.execute(
                    "INSERT INTO album_model (album_id, model_id) VALUES (?, ?)",
                    (album_id, model_id),
                )
                conn.commit()
                return {"status": "created", "album_id": album_id}
            except Exception:
                conn.rollback()
                raise


# ---------------------------------------------------------------------------
# Normalizers — repair_case and issue
# ---------------------------------------------------------------------------

def _norm_repair_case(row: dict) -> dict:
    """Canonical read model for a repair case."""
    return {
        "id": row["id"],
        "uuid": row.get("uuid"),
        "operation_uuid": row.get("operation_uuid"),
        "album_uuid": row.get("album_uuid"),
        "expected_path": row.get("expected_path"),
        "state": row.get("state", "NeedsRepair"),
        "category": row.get("category", "Assisted"),
        "confirmation": row.get("confirmation"),
        "failure_reason": row.get("failure_reason"),
        "verification_result": row.get("verification_result"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _norm_issue(row: dict) -> dict:
    """Canonical read model for an issue."""
    return {
        "id": row["id"],
        "uuid": row.get("uuid"),
        "category": row.get("category"),
        "description": row.get("description"),
        "affected_operation": row.get("affected_operation"),
        "suggested_resolution": row.get("suggested_resolution"),
        "state": row.get("state", "Open"),
        "source_workflow": row.get("source_workflow"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "priority": row.get("priority", "Normal"),
        "owner": row.get("owner"),
        "due_date": row.get("due_date"),
        "resolution_verification": row.get("resolution_verification"),
        "resolved_by": row.get("resolved_by"),
        "resolved_at": row.get("resolved_at"),
    }


# ---------------------------------------------------------------------------
# RepairRepository
# ---------------------------------------------------------------------------

class RepairRepository:
    """Persistence operations for the repair workflow state machine."""

    def __init__(self, db_factory):
        self._db = db_factory

    @staticmethod
    def _ensure_schema(conn) -> None:
        conn.execute("""CREATE TABLE IF NOT EXISTS repair_case (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL UNIQUE,
            operation_uuid TEXT, album_uuid TEXT, expected_path TEXT,
            state TEXT NOT NULL DEFAULT 'NeedsRepair', category TEXT NOT NULL DEFAULT 'Assisted',
            confirmation TEXT, failure_reason TEXT, verification_result TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        conn.commit()

    def create(self, fields: dict) -> dict:
        """Create a new repair case and return the normalised record.

        The caller supplies all required fields.  ``uuid`` defaults to a new
        UUID4 if not provided.  ``state`` defaults to ``'NeedsRepair'``.

        Args:
            fields: Any subset of repair_case columns (excluding ``id``).

        Returns:
            Normalised repair case dict.
        """
        now = datetime.now(timezone.utc).isoformat()
        repair_uuid = fields.get("uuid") or str(uuid.uuid4())
        category = fields.get("category", "Assisted")
        state = fields.get("state", "NeedsRepair")
        with self._db() as conn:
            self._ensure_schema(conn)
            cur = conn.execute(
                """
                INSERT INTO repair_case
                    (uuid, operation_uuid, album_uuid, expected_path,
                     state, category, confirmation, failure_reason,
                     verification_result, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repair_uuid,
                    fields.get("operation_uuid"),
                    fields.get("album_uuid"),
                    fields.get("expected_path"),
                    state,
                    category,
                    fields.get("confirmation"),
                    fields.get("failure_reason"),
                    fields.get("verification_result"),
                    fields.get("created_at") or now,
                    fields.get("updated_at") or now,
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM repair_case WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return _norm_repair_case(dict(row))

    def get_by_uuid(self, repair_uuid: str) -> dict | None:
        """Return the normalised repair case for *repair_uuid*, or ``None``."""
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                "SELECT * FROM repair_case WHERE uuid = ?", (repair_uuid,)
            ).fetchone()
        return _norm_repair_case(dict(row)) if row else None

    def list_cases(self, *, state: str | None = None, category: str | None = None) -> list[dict]:
        clauses, params = [], []
        if state: clauses.append("state = ?"); params.append(state)
        if category: clauses.append("category = ?"); params.append(category)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._db() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                f"SELECT * FROM repair_case{where} ORDER BY created_at DESC, id DESC", params,
            ).fetchall()
        return [_norm_repair_case(dict(row)) for row in rows]

    def get_state(self, repair_uuid: str) -> str | None:
        """Return the current state string for *repair_uuid*, or ``None``."""
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                "SELECT state FROM repair_case WHERE uuid = ?", (repair_uuid,)
            ).fetchone()
        return row["state"] if row else None

    def set_state(self, repair_uuid: str, state: str) -> None:
        """Persist a state transition for *repair_uuid*."""
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                "UPDATE repair_case SET state = ?, updated_at = ? WHERE uuid = ?",
                (state, now, repair_uuid),
            )
            conn.commit()

    def set_confirmation(self, repair_uuid: str, confirmation: str) -> None:
        """Persist a confirmation text for an Assisted or ManualConflict repair."""
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                "UPDATE repair_case SET confirmation = ?, updated_at = ? WHERE uuid = ?",
                (confirmation, now, repair_uuid),
            )
            conn.commit()

    def set_verification_result(self, repair_uuid: str, result: str) -> None:
        """Persist the post-action verification result."""
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                "UPDATE repair_case"
                " SET verification_result = ?, updated_at = ? WHERE uuid = ?",
                (result, now, repair_uuid),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Repair suppression persistence
# ---------------------------------------------------------------------------

class RepairSuppressionRepository:
    """Durable, bounded suppression records for repair rediscovery."""

    def __init__(self, db_factory):
        self._db = db_factory

    @staticmethod
    def _ensure_schema(conn) -> None:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS repair_suppression (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT NOT NULL UNIQUE,
                fingerprint TEXT NOT NULL,
                scope_path TEXT NOT NULL,
                reason TEXT NOT NULL,
                creator TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                revoked_by TEXT
            )"""
        )
        conn.commit()

    @staticmethod
    def _normalise(row: dict) -> dict:
        return {
            "id": row["id"], "uuid": row["uuid"],
            "fingerprint": row["fingerprint"], "scope_path": row["scope_path"],
            "reason": row["reason"], "creator": row["creator"],
            "created_at": row["created_at"], "expires_at": row["expires_at"],
            "revoked_at": row.get("revoked_at"), "revoked_by": row.get("revoked_by"),
        }

    def create(self, fields: dict) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        record_uuid = fields.get("uuid") or str(uuid.uuid4())
        with self._db() as conn:
            self._ensure_schema(conn)
            cur = conn.execute(
                """INSERT INTO repair_suppression
                   (uuid, fingerprint, scope_path, reason, creator, created_at, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (record_uuid, fields["fingerprint"], fields["scope_path"],
                fields["reason"], fields["creator"], fields.get("created_at") or now,
                 fields["expires_at"]),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM repair_suppression WHERE id = ?", (cur.lastrowid,)).fetchone()
        return self._normalise(dict(row))

    def find_active(self, fingerprint: str, scope_path: str, now: str) -> dict | None:
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                """SELECT * FROM repair_suppression
                   WHERE fingerprint = ? AND scope_path = ?
                     AND revoked_at IS NULL AND expires_at > ?
                   ORDER BY created_at DESC LIMIT 1""",
                (fingerprint, scope_path, now),
            ).fetchone()
        return self._normalise(dict(row)) if row else None

    def revoke(self, record_uuid: str, revoked_by: str) -> dict | None:
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                "UPDATE repair_suppression SET revoked_at = ?, revoked_by = ? WHERE uuid = ?",
                (now, revoked_by, record_uuid),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM repair_suppression WHERE uuid = ?", (record_uuid,)).fetchone()
        return self._normalise(dict(row)) if row else None

    def list_records(self) -> list[dict]:
        with self._db() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                "SELECT * FROM repair_suppression ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._normalise(dict(row)) for row in rows]


class SnapshotCleanupRepository:
    """Durable single-use claims for reviewed snapshot cleanup previews."""

    def __init__(self, db_factory):
        self._db = db_factory

    def claim_preview(self, preview_uuid: str, claimed_at: str) -> None:
        with self._db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS snapshot_cleanup_preview_claim (
                preview_uuid TEXT PRIMARY KEY, claimed_at TEXT NOT NULL)""")
            try:
                conn.execute("INSERT INTO snapshot_cleanup_preview_claim VALUES (?, ?)",
                             (preview_uuid, claimed_at))
                conn.commit()
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflict({"preview_uuid": preview_uuid, "reason": "already_claimed"}) from exc

    def preview_is_claimed(self, preview_uuid: str) -> bool:
        with self._db() as conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='snapshot_cleanup_preview_claim'").fetchone()
            return bool(exists and conn.execute(
                "SELECT 1 FROM snapshot_cleanup_preview_claim WHERE preview_uuid=?", (preview_uuid,)
            ).fetchone())


class RestorePreviewRepository:
    """Durable single-use claims for protected database Restore previews."""

    def __init__(self, db_factory): self._db = db_factory

    def claim_preview(self, preview_uuid: str, claimed_at: str) -> None:
        with self._db() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS restore_preview_claim (
                preview_uuid TEXT PRIMARY KEY, claimed_at TEXT NOT NULL)""")
            try:
                conn.execute("INSERT INTO restore_preview_claim VALUES (?,?)", (preview_uuid, claimed_at)); conn.commit()
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflict({"preview_uuid": preview_uuid, "reason": "already_claimed"}) from exc

    def preview_is_claimed(self, preview_uuid: str) -> bool:
        with self._db() as conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='restore_preview_claim'").fetchone()
            return bool(exists and conn.execute("SELECT 1 FROM restore_preview_claim WHERE preview_uuid=?", (preview_uuid,)).fetchone())


class QuarantineRepository:
    """Durable metadata for intact quarantined directories."""
    def __init__(self, db_factory): self._db = db_factory
    def _schema(self, conn):
        conn.execute("""CREATE TABLE IF NOT EXISTS quarantine_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL UNIQUE,
            original_path TEXT NOT NULL, quarantine_path TEXT NOT NULL,
            repair_uuid TEXT, operation_uuid TEXT NOT NULL, reason TEXT NOT NULL,
            inventory TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            hold INTEGER NOT NULL DEFAULT 0, restored_at TEXT,
            restore_operation_uuid TEXT, restore_destination TEXT)""")
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(quarantine_item)")}
        for column in ("restored_at", "restore_operation_uuid", "restore_destination"):
            if column not in existing: conn.execute(f"ALTER TABLE quarantine_item ADD COLUMN {column} TEXT")
        conn.execute("""CREATE TABLE IF NOT EXISTS quarantine_preview_claim (
            preview_uuid TEXT PRIMARY KEY, claimed_at TEXT NOT NULL)""")
        conn.commit()
    def create(self, fields):
        now = datetime.now(timezone.utc).isoformat(); item_uuid = fields.get("uuid") or str(uuid.uuid4())
        with self._db() as conn:
            self._schema(conn)
            conn.execute("INSERT INTO quarantine_item (uuid,original_path,quarantine_path,repair_uuid,operation_uuid,reason,inventory,created_at,expires_at,hold) VALUES (?,?,?,?,?,?,?,?,?,?)", (item_uuid, fields["original_path"], fields["quarantine_path"], fields.get("repair_uuid"), fields["operation_uuid"], fields["reason"], fields["inventory"], now, fields["expires_at"], 0))
            conn.commit(); row = conn.execute("SELECT * FROM quarantine_item WHERE uuid=?", (item_uuid,)).fetchone()
        return dict(row)
    def get(self, item_uuid):
        with self._db() as conn:
            self._schema(conn); row = conn.execute("SELECT * FROM quarantine_item WHERE uuid=?", (item_uuid,)).fetchone()
        return dict(row) if row else None
    def list(self):
        with self._db() as conn:
            self._schema(conn); rows = conn.execute("SELECT * FROM quarantine_item ORDER BY created_at").fetchall()
        return [dict(row) for row in rows]
    def mark_restored(self, item_uuid, operation_uuid, destination):
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as conn:
            self._schema(conn); conn.execute(
                "UPDATE quarantine_item SET restored_at=?,restore_operation_uuid=?,restore_destination=? WHERE uuid=?",
                (now, operation_uuid, destination, item_uuid)); conn.commit()
        return self.get(item_uuid)
    def preview_is_claimed(self, preview_uuid):
        with self._db() as conn:
            self._schema(conn); row = conn.execute("SELECT 1 FROM quarantine_preview_claim WHERE preview_uuid=?", (preview_uuid,)).fetchone()
        return bool(row)
    def claim_preview(self, preview_uuid):
        with self._db() as conn:
            self._schema(conn)
            try:
                conn.execute("INSERT INTO quarantine_preview_claim VALUES (?,?)", (preview_uuid, datetime.now(timezone.utc).isoformat())); conn.commit()
            except Exception as exc:
                raise PersistenceConflict({"preview_uuid": preview_uuid}) from exc


# ---------------------------------------------------------------------------
# IssueRepository
# ---------------------------------------------------------------------------

class IssueRepository:
    """Persistence operations for the issue management lifecycle."""

    def __init__(self, db_factory):
        self._db = db_factory

    @staticmethod
    def _ensure_schema(conn) -> None:
        """Provide additive Issue persistence for existing Curator databases."""
        conn.execute(
            """CREATE TABLE IF NOT EXISTS issue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                affected_operation TEXT,
                suggested_resolution TEXT,
                state TEXT NOT NULL DEFAULT 'Open',
                source_workflow TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                priority TEXT DEFAULT 'Normal',
                owner TEXT,
                due_date TEXT,
                resolution_verification TEXT,
                resolved_by TEXT,
                resolved_at TEXT
            )"""
        )
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(issue)")}
        for column, declaration in (
            ("resolution_verification", "TEXT"),
            ("resolved_by", "TEXT"),
            ("resolved_at", "TEXT"),
        ):
            if column not in existing:
                conn.execute(f"ALTER TABLE issue ADD COLUMN {column} {declaration}")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS issue_link (
                issue_uuid TEXT NOT NULL,
                relationship TEXT NOT NULL,
                target_uuid TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(issue_uuid, relationship, target_uuid)
            )"""
        )
        conn.commit()

    def create(self, fields: dict) -> dict:
        """Create a new issue and return the normalised record.

        Args:
            fields: Must include ``category``, ``description``, and
                ``source_workflow``; all other columns are optional.

        Returns:
            Normalised issue dict.
        """
        now = datetime.now(timezone.utc).isoformat()
        issue_uuid = fields.get("uuid") or str(uuid.uuid4())
        with self._db() as conn:
            self._ensure_schema(conn)
            cur = conn.execute(
                """
                INSERT INTO issue
                    (uuid, category, description, affected_operation,
                     suggested_resolution, state, source_workflow,
                     created_at, updated_at, priority, owner, due_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    issue_uuid,
                    fields["category"],
                    fields["description"],
                    fields.get("affected_operation"),
                    fields.get("suggested_resolution"),
                    fields.get("state", "Open"),
                    fields["source_workflow"],
                    fields.get("created_at") or now,
                    fields.get("updated_at") or now,
                    fields.get("priority", "Normal"),
                    fields.get("owner"),
                    fields.get("due_date"),
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM issue WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return _norm_issue(dict(row))

    def get_by_uuid(self, issue_uuid: str) -> dict | None:
        """Return the normalised issue for *issue_uuid*, or ``None``."""
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                "SELECT * FROM issue WHERE uuid = ?", (issue_uuid,)
            ).fetchone()
        return _norm_issue(dict(row)) if row else None

    def list_issues(self, *, state: str | None = None, owner: str | None = None) -> list[dict]:
        clauses, params = [], []
        if state: clauses.append("state = ?"); params.append(state)
        if owner: clauses.append("owner = ?"); params.append(owner)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._db() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                f"SELECT * FROM issue{where} ORDER BY created_at DESC, id DESC", params,
            ).fetchall()
        return [_norm_issue(dict(row)) for row in rows]

    def get_state(self, issue_uuid: str) -> str | None:
        """Return the current state string for *issue_uuid*, or ``None``."""
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                "SELECT state FROM issue WHERE uuid = ?", (issue_uuid,)
            ).fetchone()
        return row["state"] if row else None

    def set_state(
        self,
        issue_uuid: str,
        state: str,
        *,
        resolution_verification: str | None = None,
        resolved_by: str | None = None,
    ) -> None:
        """Persist a state transition for *issue_uuid*."""
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                """UPDATE issue SET state = ?, updated_at = ?,
                resolution_verification = COALESCE(?, resolution_verification),
                resolved_by = COALESCE(?, resolved_by),
                resolved_at = CASE WHEN ? = 'Resolved' THEN ? ELSE resolved_at END
                WHERE uuid = ?""",
                (state, now, resolution_verification, resolved_by, state, now, issue_uuid),
            )
            conn.commit()

    def set_owner(self, issue_uuid: str, owner: str | None) -> None:
        """Persist an administrator-selected Issue owner."""
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                "UPDATE issue SET owner = ?, updated_at = ? WHERE uuid = ?",
                (owner, now, issue_uuid),
            )
            conn.commit()

    def set_category(self, issue_uuid: str, category: str) -> None:
        """Persist a service-validated category change."""
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                "UPDATE issue SET category = ?, updated_at = ? WHERE uuid = ?",
                (category, now, issue_uuid),
            )
            conn.commit()

    def add_link(self, issue_uuid: str, relationship: str, target_uuid: str) -> None:
        """Record one durable Issue-to-operation or Issue-to-entity link."""
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                """INSERT OR IGNORE INTO issue_link
                (issue_uuid, relationship, target_uuid, created_at) VALUES (?, ?, ?, ?)""",
                (issue_uuid, relationship, target_uuid, now),
            )
            conn.commit()

    def list_links(self, issue_uuid: str) -> list[dict]:
        """Return the stable links associated with an Issue."""
        with self._db() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                """SELECT relationship, target_uuid, created_at FROM issue_link
                WHERE issue_uuid = ? ORDER BY created_at, relationship, target_uuid""",
                (issue_uuid,),
            ).fetchall()
        return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Normalizer — operation
# ---------------------------------------------------------------------------

def _norm_operation(row: dict) -> dict:
    """Canonical read model for an Operation record."""
    return {
        "id": row["id"],
        "uuid": row.get("uuid"),
        "operation_type": row.get("operation_type"),
        "initiator": row.get("initiator"),
        "status": row.get("status", "Pending"),
        "summary": row.get("summary"),
        "started_at": row.get("started_at"),
        "ended_at": row.get("ended_at"),
        "entity_uuid": row.get("entity_uuid"),
        "import_uuid": row.get("import_uuid"),
        "batch_uuid": row.get("batch_uuid"),
        "repair_uuid": row.get("repair_uuid"),
        "related_operation_uuid": row.get("related_operation_uuid"),
        "parent_operation_uuid": row.get("parent_operation_uuid"),
        "issue_uuid": row.get("issue_uuid"),
        "error_category": row.get("error_category"),
        "error_code": row.get("error_code"),
        "error_details": row.get("error_details"),
        "repair_state": row.get("repair_state"),
        "recovery_context": row.get("recovery_context"),
    }


# ---------------------------------------------------------------------------
# OperationRepository
# ---------------------------------------------------------------------------

class OperationRepository:
    """Persistence operations for the Operation history record.

    All material backend writes that require a durable Operation record use
    this repository to create and update their records.  Supporting log output
    (JSONL) is the caller's responsibility; this repository owns only the
    database-backed record.
    """

    def __init__(self, db_factory):
        self._db = db_factory

    @staticmethod
    def _ensure_schema(conn) -> None:
        """Provide additive Operation persistence for existing databases."""
        conn.execute("""CREATE TABLE IF NOT EXISTS operation (
            id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL,
            operation_type TEXT NOT NULL, initiator TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending', summary TEXT, started_at TEXT NOT NULL,
            ended_at TEXT, entity_uuid TEXT, import_uuid TEXT, batch_uuid TEXT,
            repair_uuid TEXT, related_operation_uuid TEXT, parent_operation_uuid TEXT,
            issue_uuid TEXT, error_category TEXT, error_code TEXT, error_details TEXT,
            repair_state TEXT, recovery_context TEXT)""")
        conn.commit()

    def create(self, fields: dict) -> dict:
        """Create a new Operation record and return the normalised result.

        Required fields: ``operation_type``, ``initiator``.
        ``uuid`` defaults to a new UUID4 when not supplied.
        ``status`` defaults to ``'Pending'``.
        ``started_at`` defaults to the current UTC time.

        Args:
            fields: Subset of operation columns (excluding ``id``).

        Returns:
            Normalised operation dict.
        """
        now = datetime.now(timezone.utc).isoformat()
        op_uuid = fields.get("uuid") or str(uuid.uuid4())
        status = fields.get("status", "Pending")
        with self._db() as conn:
            self._ensure_schema(conn)
            cur = conn.execute(
                """
                INSERT INTO operation (
                    uuid, operation_type, initiator, status, summary,
                    started_at, ended_at,
                    entity_uuid, import_uuid, batch_uuid, repair_uuid,
                    related_operation_uuid, parent_operation_uuid, issue_uuid,
                    error_category, error_code, error_details,
                    repair_state, recovery_context
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?
                )
                """,
                (
                    op_uuid,
                    fields["operation_type"],
                    fields["initiator"],
                    status,
                    fields.get("summary"),
                    fields.get("started_at") or now,
                    fields.get("ended_at"),
                    fields.get("entity_uuid"),
                    fields.get("import_uuid"),
                    fields.get("batch_uuid"),
                    fields.get("repair_uuid"),
                    fields.get("related_operation_uuid"),
                    fields.get("parent_operation_uuid"),
                    fields.get("issue_uuid"),
                    fields.get("error_category"),
                    fields.get("error_code"),
                    fields.get("error_details"),
                    fields.get("repair_state"),
                    fields.get("recovery_context"),
                ),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM operation WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
        return _norm_operation(dict(row))

    def get_by_uuid(self, op_uuid: str) -> dict | None:
        """Return the normalised Operation for *op_uuid*, or ``None``."""
        with self._db() as conn:
            self._ensure_schema(conn)
            row = conn.execute(
                "SELECT * FROM operation WHERE uuid = ?", (op_uuid,)
            ).fetchone()
        return _norm_operation(dict(row)) if row else None

    def list_recent(self, limit: int = 50) -> list[dict]:
        """Return durable Operation records newest first, bounded by *limit*."""
        with self._db() as conn:
            self._ensure_schema(conn)
            rows = conn.execute(
                "SELECT * FROM operation ORDER BY started_at DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_norm_operation(dict(row)) for row in rows]

    def query_history(
        self, *, limit: int, status: str | None = None,
        operation_type: str | None = None, started_from: str | None = None,
        started_to: str | None = None, after: tuple[str, int] | None = None,
    ) -> tuple[list[dict], int]:
        """Return one stable keyset page and the filtered total count."""
        clauses: list[str] = []
        params: list[object] = []
        for column, value, operator in (
            ("status", status, "="), ("operation_type", operation_type, "="),
            ("started_at", started_from, ">="), ("started_at", started_to, "<="),
        ):
            if value is not None:
                clauses.append(f"{column} {operator} ?")
                params.append(value)
        filter_where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        page_clauses = list(clauses)
        page_params = list(params)
        if after is not None:
            page_clauses.append("(started_at < ? OR (started_at = ? AND id < ?))")
            page_params.extend((after[0], after[0], after[1]))
        page_where = f" WHERE {' AND '.join(page_clauses)}" if page_clauses else ""
        with self._db() as conn:
            self._ensure_schema(conn)
            total = conn.execute(
                f"SELECT COUNT(*) FROM operation{filter_where}", params,
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM operation{page_where} "
                "ORDER BY started_at DESC, id DESC LIMIT ?",
                (*page_params, limit + 1),
            ).fetchall()
        return [_norm_operation(dict(row)) for row in rows], int(total)

    def set_status(
        self,
        op_uuid: str,
        status: str,
        *,
        summary: str | None = None,
        ended_at: str | None = None,
        error_category: str | None = None,
        error_code: str | None = None,
        error_details: str | None = None,
        repair_state: str | None = None,
        recovery_context: str | None = None,
    ) -> None:
        """Update the status and optional terminal fields for *op_uuid*.

        Args:
            op_uuid: UUID of the operation to update.
            status: New status string (one of the ``OP_STATUS_*`` constants).
            summary: Optional human-readable outcome summary to persist.
            ended_at: ISO 8601 end timestamp; defaults to current UTC time
                when ``None`` and the operation has reached a terminal state.
            error_category: Coarse error category (e.g. ``'filesystem'``).
            error_code: Stable error code (e.g. ``'filesystem.write-failed'``).
            error_details: Free-text error detail for diagnostic use.
            repair_state: Repair-state string when a filesystem repair is
                relevant.
            recovery_context: Recovery instructions or context.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as conn:
            self._ensure_schema(conn)
            conn.execute(
                """
                UPDATE operation SET
                    status = ?,
                    summary = COALESCE(?, summary),
                    ended_at = COALESCE(?, ended_at, ?),
                    error_category = COALESCE(?, error_category),
                    error_code = COALESCE(?, error_code),
                    error_details = COALESCE(?, error_details),
                    repair_state = COALESCE(?, repair_state),
                    recovery_context = COALESCE(?, recovery_context)
                WHERE uuid = ?
                """,
                (
                    status,
                    summary,
                    ended_at, now,
                    error_category,
                    error_code,
                    error_details,
                    repair_state,
                    recovery_context,
                    op_uuid,
                ),
            )
            conn.commit()
