import sqlite3
import tempfile
import unittest
from pathlib import Path

from apps.ai_instruction_profile import DEFAULT_VERSION_UUID, compose, content_hash, default_content, snapshot
from apps.backend import repositories as repo
from apps.backend import services as svc


class AIInstructionProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.database=Path(self.tmp.name)/"profile.db"
        self.db=lambda:sqlite3.connect(self.database)
        # Repository rows need named access just like the application connection.
        def factory():
            connection=sqlite3.connect(self.database);connection.row_factory=sqlite3.Row;return connection
        self.db=factory;self.repo=repo.AIInstructionProfileRepository(self.db);self.service=svc.AIInstructionProfileService(self.repo)
    def tearDown(self):self.tmp.cleanup()

    def test_default_snapshot_hash_and_composition_are_deterministic(self):
        version=self.repo.get_version();frozen=snapshot(version)
        first=compose(frozen,"writer",vision={"scene":"indoor"});second=compose(frozen,"writer",vision={"scene":"indoor"})
        self.assertEqual(first,second);self.assertIn("<VISION_DATA>",first);self.assertEqual(content_hash(frozen),frozen["content_hash"])
        self.assertEqual(DEFAULT_VERSION_UUID,version["version_uuid"]);self.assertEqual(4,version["version"])
        self.assertIn("sensual, provocative, imaginative editorial style",first)
        self.assertIn("Do not simply combine clothing, anatomy, pose, room",first)
        self.assertIn("three or four English words according to what sounds most natural",first)
        self.assertIn("Never append Roman numerals",first)
        frozen["global_instruction"]="tampered"
        with self.assertRaisesRegex(ValueError,"hash"):compose(frozen,"vision")

    def test_create_version_publish_and_disable_lifecycle(self):
        created=self.service.create({"name":"Editorial Album Control","content":default_content()})
        profile=next(item for item in self.service.list() if item["uuid"]==created["profile_uuid"])
        published=self.service.publish(profile["uuid"],profile["version"],False)
        version=self.service.create_version(profile["uuid"],published["version"],{"content":default_content()})
        draft=next(item for item in self.service.list() if item["uuid"]==profile["uuid"])
        self.assertEqual(2,version["version"]);self.assertEqual("Draft",draft["lifecycle_state"])
        published=self.service.publish(profile["uuid"],draft["version"],False)
        self.assertEqual("Disabled",self.service.disable(profile["uuid"],published["version"])["lifecycle_state"])


if __name__=="__main__":unittest.main()
