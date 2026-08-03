#!/usr/bin/env python3
"""Shared API contract serialization layer for /api/v1 endpoints.

Provides envelope helpers for success, error, and collection responses as
defined in the API Contract specification. Route handlers MUST use these
helpers and MUST NOT construct contract response payloads directly.

Envelope shapes
---------------
Success:
    {"data": <any>, "meta": {"request_id": "...", ...}}

Error:
    {"error": {"code": "...", "message": "...", ["details": ...], ["fields": ...]},
     "meta": {"request_id": "...", ...}}

Collection (success with pagination meta):
    {"data": [...], "meta": {"request_id": "...", "pagination": {...},
                              "filters": [...], "sort": [...]}}

Stable error code families
--------------------------
  REQUEST_*          400  Transport/syntax validation failures.
  VALIDATION_*       422  Domain or business validation failures.
  AUTHENTICATION_*   401  Missing, invalid, expired, or revoked token.
  AUTHORIZATION_*    403  Valid token lacks required scope.
  NOT_FOUND          404  Resource does not exist or is not visible.
  DATA_CONFLICT      409  Concurrent uniqueness or integrity conflict.
  BUSINESS_CONFLICT  409  Request blocked by current workflow or lifecycle state.
  NEEDS_REPAIR       409  Incomplete operation requiring repair.
  CONFIRMATION_REQUIRED 428 Action requires explicit confirmation.
  INTERNAL_ERROR     500  Unexpected backend failure (no implementation details).
"""

from __future__ import annotations

import base64
import json
import uuid


# ---------------------------------------------------------------------------
# Request ID generation
# ---------------------------------------------------------------------------

def generate_request_id() -> str:
    """Generate a unique per-request correlation identifier."""
    return f"req-{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Success envelope
# ---------------------------------------------------------------------------

def success_response(
    data,
    *,
    request_id: str,
    meta_extras: dict | None = None,
) -> dict:
    """Build a contract-conformant success envelope.

    Args:
        data: The route result. MAY be an object, list, scalar, or None.
        request_id: The per-request correlation identifier.
        meta_extras: Optional additional members to merge into ``meta``
            (e.g. pagination, filters, sort, operation, snapshot).

    Returns:
        ``{"data": data, "meta": {"request_id": ..., ...}}``
    """
    meta: dict = {"request_id": request_id}
    if meta_extras:
        meta.update(meta_extras)
    return {"data": data, "meta": meta}


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------

def error_response(
    code: str,
    message: str,
    *,
    request_id: str,
    details: dict | None = None,
    fields: dict | None = None,
    meta_extras: dict | None = None,
) -> dict:
    """Build a contract-conformant error envelope.

    Optional fields are omitted entirely when not supplied, per the contract
    rule that a route MUST omit optional fields rather than supply a
    meaning-changing alternative shape.

    Args:
        code: Stable machine-readable error code (e.g. ``"NOT_FOUND"``).
        message: Safe, user-presentable error description. MUST NOT expose SQL,
            stack traces, framework names, token material, or other
            implementation-sensitive data.
        request_id: The per-request correlation identifier.
        details: Optional structured context (expected state, supported values,
            retry-safe action). MUST NOT contain sensitive implementation data.
        fields: Optional field-level error map (validation errors only). Keys
            MUST match client-submitted or client-received field names.
        meta_extras: Optional additional meta members (e.g. operation, repair,
            confirmation).

    Returns:
        ``{"error": {"code": ..., "message": ..., ...}, "meta": {...}}``
    """
    err: dict = {"code": code, "message": message}
    if details is not None:
        err["details"] = details
    if fields is not None:
        err["fields"] = fields
    meta: dict = {"request_id": request_id}
    if meta_extras:
        meta.update(meta_extras)
    return {"error": err, "meta": meta}


# ---------------------------------------------------------------------------
# Collection pagination metadata
# ---------------------------------------------------------------------------

def build_collection_meta(
    *,
    cursor: str | None,
    limit: int,
    next_cursor: str | None,
    has_more: bool,
    total: int | None,
    filters: list | None = None,
    sort: list | None = None,
) -> dict:
    """Build the standard collection metadata block for use as ``meta_extras``.

    The returned dict is suitable for passing directly to
    :func:`success_response` as ``meta_extras``.

    Args:
        cursor: Opaque continuation token for the current page, or ``None``
            for the first page.
        limit: The page size applied to the query.
        next_cursor: Opaque continuation token for the next page, or ``None``
            when no further page is available.
        has_more: ``True`` when a subsequent page exists.
        total: Integer item count when the route can provide it without
            changing query semantics; otherwise ``None``.
        filters: Normalized filter objects applied to the query. Always
            present; use an empty list when no filters were applied.
        sort: Normalized sort key objects applied to the query. Always
            present; use an empty list when no sort was specified.

    Returns:
        ``{"pagination": {...}, "filters": [...], "sort": [...]}``
    """
    return {
        "pagination": {
            "cursor": cursor,
            "limit": limit,
            "next_cursor": next_cursor,
            "has_more": bool(has_more),
            "total": total,
        },
        "filters": filters if filters is not None else [],
        "sort": sort if sort is not None else [],
    }


# ---------------------------------------------------------------------------
# Opaque cursor encoding (offset-based)
# ---------------------------------------------------------------------------

def encode_cursor(offset: int) -> str:
    """Encode a page offset as an opaque, URL-safe cursor string.

    Clients MUST treat the returned value as opaque and MUST NOT inspect,
    construct, or reuse it with a materially different query.
    """
    payload = json.dumps({"offset": offset}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> int | None:
    """Decode an opaque cursor back to its offset value.

    Returns:
        The integer offset, or ``None`` if the cursor is invalid or cannot
        be decoded.
    """
    try:
        payload = base64.urlsafe_b64decode(cursor.encode()).decode()
        data = json.loads(payload)
        return int(data["offset"])
    except Exception:
        return None
