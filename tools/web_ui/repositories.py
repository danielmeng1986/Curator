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
        sort: str = "updated_at",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Return a filtered, sorted page of albums plus the total count."""
        order_col = self._SORT_MAP.get(sort, "a.updated_at")
        conditions: list[str] = []
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

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        query = f"""
            SELECT a.id, a.uuid, a.title, a.description, a.scene, a.location,
                a.capture_date, a.publish_date, a.rating, a.path,
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
                         rating, path, created_at, updated_at)
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
