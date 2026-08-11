"""DOC-008 application user-manual release-gate acceptance."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from tools.check_user_manuals import MANUAL_ROOT, check


class UserManualDocumentationGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="curator-manual-test-")
        self.root = Path(self.temporary.name) / "User-Manual"
        shutil.copytree(MANUAL_ROOT, self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def test_current_manuals_pass(self):
        self.assertEqual([], check())

    def test_missing_locale_file_is_reported(self):
        (self.root / "zh-CN" / "client" / "apps-web" / "reader.md").unlink()
        failures = check(self.root)
        self.assertTrue(any("missing zh-CN manual: client/apps-web/reader.md" in item for item in failures))

    def test_missing_safety_section_is_reported(self):
        path = self.root / "en" / "server" / "apps-backend.md"
        path.write_text(path.read_text(encoding="utf-8").replace("<!-- manual-section: warnings -->", ""), encoding="utf-8")
        failures = check(self.root)
        self.assertTrue(any("missing safety/structure section" in item and "warnings" in item for item in failures))

    def test_broken_link_is_reported(self):
        path = self.root / "en" / "client" / "apps-web" / "reader.md"
        path.write_text(path.read_text(encoding="utf-8") + "\n[Broken](missing.md)\n", encoding="utf-8")
        failures = check(self.root)
        self.assertTrue(any("broken link" in item for item in failures))

    def test_command_drift_is_reported(self):
        path = self.root / "zh-CN" / "server" / "apps-backend.md"
        path.write_text(path.read_text(encoding="utf-8").replace("python3 -m apps.backend\n", "python3 -m apps.backend.unsupported\n", 1), encoding="utf-8")
        failures = check(self.root)
        self.assertTrue(any("shell commands differ" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
