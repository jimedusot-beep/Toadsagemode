import json
import tempfile
import unittest
from pathlib import Path
from toad_core.import_feed import import_browser_library

class BrowserLibraryImportTests(unittest.TestCase):
    def test_import_does_not_execute(self):
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            marker=directory/"SHOULD_NOT_EXIST"
            content='__import__("pathlib").Path('+repr(str(marker))+').write_text("BAD")'
            data={"schema":"toad-library-v1","abilities":[{"name":"sample-module","version":"0.1.0","description":"demo","content":content,"kind":"Python","source":"ChatGPT","status":"unverified","installed":False}]}
            source=directory/"export.json"
            target=directory/"catalog.json"
            source.write_text(json.dumps(data))
            self.assertEqual(import_browser_library(source,target),1)
            result=json.loads(target.read_text())
            self.assertEqual(result["abilities"][0]["content"],content)
            self.assertFalse(marker.exists())
            self.assertEqual(result["abilities"][0]["status"],"unverified")
            self.assertFalse(result["abilities"][0]["installed"])

    def test_reject_installed_and_existing_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder); source=base/"import.json"; target=base/"catalog.json"
            data={"schema":"toad-library-v1","abilities":[{"name":"x-ok","version":"0.1.0","content":"hello","status":"unverified","installed":True}]}
            source.write_text(json.dumps(data))
            with self.assertRaises(ValueError): import_browser_library(source,target)
            self.assertFalse(target.exists())
            data["abilities"][0]["installed"]=False
            source.write_text(json.dumps(data))
            target.write_text("keep this")
            with self.assertRaises(ValueError): import_browser_library(source,target)
            self.assertEqual(target.read_text(),"keep this")

    def test_reject_pathlike_name_and_oversize(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder); source=base/"import.json"
            data={"schema":"toad-library-v1","abilities":[{"name":"../escape","content":"hello","status":"unverified","installed":False}]}
            source.write_text(json.dumps(data))
            with self.assertRaises(ValueError): import_browser_library(source,base/"out.json")
            source.write_text("x"*2000001)
            with self.assertRaises(ValueError): import_browser_library(source,base/"out.json")

if __name__=="__main__": unittest.main()

class LegacyMetadataTests(unittest.TestCase):
    def test_legacy_converter_preserves_source_version_and_unknown_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'old.json';target=root/'new.json'
            source.write_text(json.dumps({'schema':'toad-library-v1','custom_top':9,'abilities':[{'name':'legacy-demo','version':'2.0.0','source':'Gemini','content':'print(1)','custom':7,'status':'unverified','installed':False}]}))
            import_browser_library(source,target)
            out=json.loads(target.read_text())
            self.assertEqual(out['custom_top'],9)
            self.assertEqual(out['abilities'][0]['version'],'2.0.0')
            self.assertEqual(out['abilities'][0]['source'],'Gemini')
            self.assertEqual(out['abilities'][0]['custom'],7)
