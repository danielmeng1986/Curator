#!/usr/bin/env python3
"""Tests for tools/web_ui/canonical_path.py.

Covers every public function defined in the canonical_path module.
All tests are pure (no I/O, no database, no filesystem).
"""
from __future__ import annotations

import sys
import os
import unittest

# Allow tests to import sibling modules without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import canonical_path as cp


# ---------------------------------------------------------------------------
# canonicalize_component
# ---------------------------------------------------------------------------

class TestCanonicalizeComponent(unittest.TestCase):
    """Tests for cp.canonicalize_component."""

    def test_strips_leading_whitespace(self):
        self.assertEqual(cp.canonicalize_component("  Alice"), "Alice")

    def test_strips_trailing_whitespace(self):
        self.assertEqual(cp.canonicalize_component("Alice  "), "Alice")

    def test_strips_leading_and_trailing(self):
        self.assertEqual(cp.canonicalize_component("  Alice  "), "Alice")

    def test_no_op_on_clean_string(self):
        self.assertEqual(cp.canonicalize_component("Alice"), "Alice")

    def test_empty_string(self):
        self.assertEqual(cp.canonicalize_component(""), "")

    def test_whitespace_only(self):
        self.assertEqual(cp.canonicalize_component("   "), "")

    def test_internal_whitespace_preserved(self):
        # Internal spaces within a component name are preserved.
        self.assertEqual(cp.canonicalize_component("  Summer Vacation  "), "Summer Vacation")

    def test_nfc_normalization_composed(self):
        # NFC should leave already-composed characters unchanged.
        # U+00E9 LATIN SMALL LETTER E WITH ACUTE (pre-composed)
        self.assertEqual(cp.canonicalize_component("\u00e9"), "\u00e9")

    def test_nfc_normalization_decomposes_to_nfc(self):
        # NFD: e (U+0065) + combining acute accent (U+0301) → NFC: é (U+00E9)
        nfd = "e\u0301"
        nfc = "\u00e9"
        self.assertEqual(cp.canonicalize_component(nfd), nfc)

    def test_nfc_normalization_of_full_name(self):
        # Name constructed with decomposed characters is composed.
        nfd = "A\u0308lice"  # Ä (decomposed) lice
        nfc = "\u00c4lice"   # Älice (composed)
        self.assertEqual(cp.canonicalize_component(nfd), nfc)

    def test_strip_then_nfc(self):
        # Whitespace is stripped before NFC, so surrounding spaces around NFD
        # char are removed and the char is composed.
        nfd_with_spaces = "  e\u0301  "
        self.assertEqual(cp.canonicalize_component(nfd_with_spaces), "\u00e9")


# ---------------------------------------------------------------------------
# alphabet_for_model
# ---------------------------------------------------------------------------

class TestAlphabetForModel(unittest.TestCase):
    """Tests for cp.alphabet_for_model."""

    def test_uppercase_letter(self):
        self.assertEqual(cp.alphabet_for_model("Alice"), "A")

    def test_lowercase_letter_returns_upper(self):
        self.assertEqual(cp.alphabet_for_model("alice"), "A")

    def test_digit_returns_bucket(self):
        self.assertEqual(cp.alphabet_for_model("007 Bond"), "0-9")

    def test_digit_any_returns_bucket(self):
        for d in "0123456789":
            with self.subTest(digit=d):
                self.assertEqual(cp.alphabet_for_model(d + "Name"), "0-9")

    def test_non_alnum_returns_underscore(self):
        self.assertEqual(cp.alphabet_for_model("_Hidden"), "_")
        self.assertEqual(cp.alphabet_for_model("-Dash"), "_")

    def test_empty_string_returns_underscore(self):
        self.assertEqual(cp.alphabet_for_model(""), "_")


# ---------------------------------------------------------------------------
# build_canonical_path
# ---------------------------------------------------------------------------

class TestBuildCanonicalPath(unittest.TestCase):
    """Tests for cp.build_canonical_path."""

    def test_basic_structure(self):
        path = cp.build_canonical_path("Alice", "Studio X", "Summer 2024")
        self.assertEqual(path, "A/Alice/p/Studio X/Summer 2024")

    def test_bucket_derived_from_model_first_char(self):
        path = cp.build_canonical_path("Bianca", "Studio X", "Album")
        self.assertTrue(path.startswith("B/Bianca/p/"))

    def test_normalization_applied_to_model(self):
        # Leading/trailing whitespace on model name is stripped.
        path = cp.build_canonical_path("  Alice  ", "Studio", "Album")
        self.assertIn("/Alice/", path)

    def test_normalization_applied_to_studio(self):
        path = cp.build_canonical_path("Alice", "  Studio X  ", "Album")
        self.assertIn("/Studio X/", path)

    def test_normalization_applied_to_album(self):
        path = cp.build_canonical_path("Alice", "Studio", "  Summer  ")
        self.assertTrue(path.endswith("/Summer"))

    def test_separator_is_forward_slash(self):
        path = cp.build_canonical_path("Alice", "Studio", "Album")
        self.assertNotIn("\\", path)

    def test_nfc_applied_in_path(self):
        # Decomposed model name should appear NFC-composed in path.
        nfd_model = "A\u0308lice"  # Ä decomposed
        path = cp.build_canonical_path(nfd_model, "Studio", "Album")
        self.assertIn("\u00c4lice", path)

    def test_digit_model_bucket(self):
        path = cp.build_canonical_path("007 Model", "Studio", "Album")
        self.assertTrue(path.startswith("0-9/007 Model/p/"))


# ---------------------------------------------------------------------------
# comparison_key
# ---------------------------------------------------------------------------

class TestComparisonKey(unittest.TestCase):
    """Tests for cp.comparison_key."""

    def test_ascii_lowercase_unchanged(self):
        self.assertEqual(cp.comparison_key("a/b/p/c/d"), "a/b/p/c/d")

    def test_ascii_uppercase_casefolded(self):
        self.assertEqual(cp.comparison_key("A/Alice/p/Studio/Album"), "a/alice/p/studio/album")

    def test_unicode_sharp_s(self):
        # German ß casefolds to "ss", not "ß" or "SS"
        self.assertEqual(cp.comparison_key("ß"), "ss")

    def test_full_path_casefolded(self):
        path = cp.build_canonical_path("Alice", "Studio X", "Summer 2024")
        key = cp.comparison_key(path)
        self.assertEqual(key, "a/alice/p/studio x/summer 2024")


# ---------------------------------------------------------------------------
# paths_equivalent
# ---------------------------------------------------------------------------

class TestPathsEquivalent(unittest.TestCase):
    """Tests for cp.paths_equivalent."""

    def test_identical_paths_are_equivalent(self):
        path = "A/Alice/p/Studio/Summer"
        self.assertTrue(cp.paths_equivalent(path, path))

    def test_different_case_is_equivalent(self):
        self.assertTrue(
            cp.paths_equivalent(
                "A/Alice/p/Studio/Summer",
                "a/alice/p/studio/summer",
            )
        )

    def test_mixed_case_is_equivalent(self):
        self.assertTrue(
            cp.paths_equivalent(
                "A/Alice/p/Studio/Summer 2024",
                "A/ALICE/p/STUDIO/SUMMER 2024",
            )
        )

    def test_genuinely_different_paths_not_equivalent(self):
        self.assertFalse(
            cp.paths_equivalent(
                "A/Alice/p/Studio/Summer",
                "A/Alice/p/Studio/Winter",
            )
        )

    def test_different_model_not_equivalent(self):
        self.assertFalse(
            cp.paths_equivalent(
                "A/Alice/p/Studio/Album",
                "B/Bianca/p/Studio/Album",
            )
        )

    def test_unicode_casefold_equivalence(self):
        # ß and ss are equivalent after casefold
        self.assertTrue(cp.paths_equivalent("ß", "ss"))


# ---------------------------------------------------------------------------
# next_album_collision_name
# ---------------------------------------------------------------------------

class TestNextAlbumCollisionName(unittest.TestCase):
    """Tests for cp.next_album_collision_name."""

    def _make_occupied(self, model: str, studio: str, *album_names: str) -> set[str]:
        return {
            cp.comparison_key(cp.build_canonical_path(model, studio, a))
            for a in album_names
        }

    def test_returns_2_when_base_occupied(self):
        occupied = self._make_occupied("Alice", "Studio", "Summer")
        result = cp.next_album_collision_name("Summer", "Alice", "Studio", occupied)
        self.assertEqual(result, "Summer (2)")

    def test_skips_2_when_also_occupied(self):
        occupied = self._make_occupied("Alice", "Studio", "Summer", "Summer (2)")
        result = cp.next_album_collision_name("Summer", "Alice", "Studio", occupied)
        self.assertEqual(result, "Summer (3)")

    def test_increments_until_free(self):
        # Occupy (2) through (5)
        occupied = self._make_occupied(
            "Alice", "Studio",
            "Summer",
            "Summer (2)",
            "Summer (3)",
            "Summer (4)",
            "Summer (5)",
        )
        result = cp.next_album_collision_name("Summer", "Alice", "Studio", occupied)
        self.assertEqual(result, "Summer (6)")

    def test_returns_none_when_limit_exceeded(self):
        # max_attempts=1 means only tries (2), which is occupied.
        occupied = self._make_occupied("Alice", "Studio", "Summer", "Summer (2)")
        result = cp.next_album_collision_name(
            "Summer", "Alice", "Studio", occupied, max_attempts=1
        )
        self.assertIsNone(result)

    def test_empty_occupied_returns_2(self):
        result = cp.next_album_collision_name("Summer", "Alice", "Studio", set())
        self.assertEqual(result, "Summer (2)")

    def test_collision_suffix_is_normalized_in_key(self):
        # The function builds and key-checks the full canonical path.
        # Case-insensitive occupied keys should be respected.
        occupied = {
            cp.comparison_key(cp.build_canonical_path("Alice", "Studio", "SUMMER"))
        }
        result = cp.next_album_collision_name("summer", "alice", "studio", occupied)
        # "summer" and "SUMMER" have the same key, so (2) should be returned.
        self.assertEqual(result, "summer (2)")

    def test_default_max_attempts_is_100(self):
        # With default max_attempts the function tries (2)…(101).
        # Occupy (2) through (101); ensure None is returned.
        occupied = self._make_occupied("Alice", "Studio", *[
            "Summer" if i == 0 else f"Summer ({i + 1})"
            for i in range(101)
        ])
        result = cp.next_album_collision_name("Summer", "Alice", "Studio", occupied)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
