import json
import tempfile
import unittest
from pathlib import Path
from toad_core.library import add_record
from toad_core.missions import create_mission, save_mission

class CoreTests(unittest.TestCase):
    def test_catalog_upsert(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "library.json"
            pkg = {"name": "demo", "version": "0.1.0", "description": "test"}
            add_record(path, pkg)
            add_record(path, pkg)
            data = json.loads(path.read_text())
            self.assertEqual(len(data["abilities"]), 1)
            self.assertFalse(data["abilities"][0]["installed"])
    def test_mission(self):
        mission = create_mission("Demo", ["Plan", "Test"])
        self.assertEqual(len(mission["steps"]), 2)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mission.json"
            save_mission(path, mission)
            self.assertEqual(json.loads(path.read_text())["status"], "planned")
    def test_empathy_schema(self):
        data = json.loads((Path(__file__).resolve().parents[1] / "empathy" / "examples.json").read_text())
        self.assertEqual(data["schema"], "toad-empathy-v1")
        self.assertGreaterEqual(len(data["examples"]), 5)
        for x in data["examples"]:
            self.assertTrue(all(x.get(k) for k in ("emotion", "context", "response", "principle", "avoid")))

if __name__ == "__main__":
    unittest.main()

class CatalogDataRetentionTests(unittest.TestCase):
    def test_metadata_update_does_not_erase_content_and_custom_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'library.json'
            path.write_text(json.dumps({'schema':'toad-library-v1','owner':'Jimmy','abilities':[{'name':'demo','version':'0.1.0','content':'print(1)','custom':7,'status':'unverified','installed':False}]}))
            add_record(path,{'name':'demo','version':'0.1.0','description':'updated'})
            result=json.loads(path.read_text())
            self.assertEqual(result['abilities'][0]['content'],'print(1)')
            self.assertEqual(result['abilities'][0]['custom'],7)
            self.assertEqual(result['owner'],'Jimmy')
