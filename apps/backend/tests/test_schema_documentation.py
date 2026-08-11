"""DBDOC-006 schema-documentation drift acceptance."""

from __future__ import annotations

import copy
import json
import unittest

from tools.check_schema_docs import (
    CATALOG_PATH,
    INVENTORY_PATH,
    build_canonical_inventory,
    catalog_gaps,
    differences,
)


class SchemaDocumentationGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))

    def test_canonical_schema_matches_inventory_and_catalog(self):
        actual = build_canonical_inventory()
        self.assertEqual([], differences(self.expected, actual))
        self.assertEqual([], catalog_gaps(actual, CATALOG_PATH.read_text(encoding="utf-8")))

    def test_added_table_is_reported(self):
        actual = copy.deepcopy(self.expected)
        actual["tables"]["unexpected_table"] = {"columns": [], "foreign_keys": [], "indexes": []}
        self.assertIn("undocumented table: unexpected_table", differences(self.expected, actual))

    def test_changed_column_is_reported(self):
        actual = copy.deepcopy(self.expected)
        actual["tables"]["album"]["columns"][0]["type"] = "TEXT"
        self.assertIn("changed columns: album", differences(self.expected, actual))

    def test_changed_foreign_key_is_reported(self):
        actual = copy.deepcopy(self.expected)
        actual["tables"]["photo"]["foreign_keys"] = []
        self.assertIn("changed foreign_keys: photo", differences(self.expected, actual))

    def test_changed_index_is_reported(self):
        actual = copy.deepcopy(self.expected)
        actual["tables"]["album_relation"]["indexes"] = []
        self.assertIn("changed indexes: album_relation", differences(self.expected, actual))

