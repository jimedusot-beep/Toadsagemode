import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class SiteBuildTests(unittest.TestCase):
    def test_static_allowlist_excludes_source_archives_and_private_runtime(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'site'
            r=subprocess.run([sys.executable,str(root/'tools/build_site.py'),'--output',str(out)],cwd=root,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(sorted(p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()),['index.html','web/ability-library.js','web/catalog.js','web/styles.css'])
            self.assertFalse((out/'toad_core').exists());self.assertFalse((out/'sage-toad-github-pages.zip').exists())
