#!/usr/bin/env python3
"""Canonical path service for Curator Backend.

Implements the normalization, comparison-key derivation, path equivalence,
and album-name collision-suffix rules required by the Canonical Path Rules
Specification.

All path operations that create, compare, import, or persist managed album
paths must pass through this module. Repository persistence and service
callers must not apply their own ad hoc normalization or comparison logic.

Responsibilities
----------------
Service layer:
  - Normalizes each path component before constructing the canonical path.
  - Derives the comparison key from the canonical path for all equality
    checks and collision detection.
  - Selects deterministic collision suffixes for Album components only.
  - Validates the resulting canonical path before any persistence or
    filesystem action.

Database (enforced elsewhere):
  - Stores the canonical path in ``album.path``.
  - Enforces ``canonical_path_key`` uniqueness as the final safety net
    against concurrent writers.

This module contains no I/O, no database access, and no business rules
beyond the path-normalization contract.
"""
from __future__ import annotations

import unicodedata


# ---------------------------------------------------------------------------
# Component normalization
# ---------------------------------------------------------------------------

def canonicalize_component(component: str) -> str:
    """Return the canonical form of a single path component.

    Applies the two mandatory component-level rules from the Canonical Path
    Rules Specification in order:
    1. Strip leading and trailing whitespace.
    2. Normalize to Unicode NFC.

    Args:
        component: A raw path component (model name, studio name, album name,
            or any other segment). Must be a plain string, not a full path.

    Returns:
        The normalized component string.
    """
    return unicodedata.normalize("NFC", component.strip())


# ---------------------------------------------------------------------------
# Archive bucket
# ---------------------------------------------------------------------------

def alphabet_for_model(model_name: str) -> str:
    """Return the single-letter (``"0-9"`` / ``"_"``) archive bucket letter.

    The bucket is derived from the first character of the *already-normalized*
    model name. Callers must normalize the model name with
    :func:`canonicalize_component` before calling this function so that the
    bucket letter reflects the canonical first character.

    Args:
        model_name: A normalized model name (output of
            :func:`canonicalize_component`).

    Returns:
        An uppercase letter ``"A"``–``"Z"``, the string ``"0-9"`` for names
        beginning with a digit, or ``"_"`` when the name is empty or begins
        with a non-alphanumeric character.
    """
    if not model_name:
        return "_"
    first = model_name[0]
    if first.isalpha():
        return first.upper()
    if first.isdigit():
        return "0-9"
    return "_"


# ---------------------------------------------------------------------------
# Canonical path construction
# ---------------------------------------------------------------------------

def build_canonical_path(
    model_name: str,
    studio_name: str,
    album_name: str,
) -> str:
    """Build the normalized canonical relative archive path.

    Each component is individually canonicalized (whitespace stripped and
    NFC-normalized) before the path is assembled. The canonical path format is:

        ``<bucket>/<model>/p/<studio>/<album>``

    where ``<bucket>`` is the archive bucket letter derived from the model
    name. All components use ``/`` as the separator regardless of platform.

    Args:
        model_name: Raw model name; normalized before use.
        studio_name: Raw studio name; normalized before use.
        album_name: Raw album name (may already include a collision suffix);
            normalized before use.

    Returns:
        The normalized canonical relative path string suitable for storage
        in ``album.path`` and for deriving ``canonical_path_key``.
    """
    norm_model = canonicalize_component(model_name)
    norm_studio = canonicalize_component(studio_name)
    norm_album = canonicalize_component(album_name)
    bucket = alphabet_for_model(norm_model)
    return f"{bucket}/{norm_model}/p/{norm_studio}/{norm_album}"


# ---------------------------------------------------------------------------
# Comparison key and equivalence
# ---------------------------------------------------------------------------

def comparison_key(canonical_path: str) -> str:
    """Return the case-folded comparison key for a canonical path.

    The comparison key is the value stored in ``canonical_path_key`` and is
    used for all equality checks, collision detection, and database uniqueness
    enforcement. It is never a user-editable or user-visible path.

    Case-folding (``str.casefold()``) is used rather than ``str.lower()`` to
    produce platform-independent case-insensitive comparisons that correctly
    handle Unicode characters such as the German sharp-s (``ß`` → ``ss``).

    Args:
        canonical_path: A canonical path produced by :func:`build_canonical_path`.

    Returns:
        The case-folded comparison key string.
    """
    return canonical_path.casefold()


def paths_equivalent(path_a: str, path_b: str) -> bool:
    """Return ``True`` when two canonical paths resolve to the same comparison key.

    Uses case-insensitive comparison consistent with the Canonical Path Rules
    requirement that the entire Curator archive is compared case-insensitively
    regardless of host platform.

    Args:
        path_a: A canonical relative path string.
        path_b: A canonical relative path string.

    Returns:
        ``True`` when both paths map to the same comparison key.
    """
    return comparison_key(path_a) == comparison_key(path_b)


# ---------------------------------------------------------------------------
# Album-name collision suffix
# ---------------------------------------------------------------------------

def next_album_collision_name(
    album_name: str,
    model_name: str,
    studio_name: str,
    occupied_keys: set[str],
    max_attempts: int = 100,
) -> str | None:
    """Find the next album name that avoids a comparison-key collision.

    Tries deterministic suffixes ``"{album_name} (2)"``,
    ``"{album_name} (3)"``, etc. until it finds a candidate whose canonical
    path comparison key is not in *occupied_keys*.

    Per the Canonical Path Rules Specification **only the Album component may
    receive an automatic collision suffix**. Model and Studio name collisions
    must be rejected or escalated by the caller; this function must not be
    called for those components.

    Args:
        album_name: The base album name that collides (already canonicalized).
        model_name: The model name for the album (already canonicalized).
        studio_name: The studio name for the album (already canonicalized).
        occupied_keys: A set of comparison keys already in use (from the
            database and/or from other items in the same import batch).
        max_attempts: Maximum number of suffixes to try before giving up.

    Returns:
        The suffixed album name string (e.g. ``"Summer (2)"``), or ``None``
        when no safe suffix was found within *max_attempts*.
    """
    for n in range(2, max_attempts + 2):
        candidate = f"{album_name} ({n})"
        candidate_path = build_canonical_path(model_name, studio_name, candidate)
        if comparison_key(candidate_path) not in occupied_keys:
            return candidate
    return None
