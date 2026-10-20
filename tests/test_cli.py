import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class CLITests(unittest.TestCase):
    def test_offline_cli_lifecycle_and_error_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);workspace=base/'private';source=base/'demo.py';source.write_text('print("hello")\n')
            def run(*args,input=None):
                return subprocess.run([sys.executable,'-m','toad_core','--workspace',str(workspace),*args],input=input,capture_output=True,text=True,timeout=10)
            r=run('ingest',str(source));self.assertEqual(r.returncode,0,r.stderr);record=json.loads(r.stdout)
            self.assertFalse(record['installed'])
            r=run('library','list','--search','hello');self.assertEqual(len(json.loads(r.stdout)),1)
            r=run('inspect',record['id']);self.assertEqual(r.returncode,0,r.stderr)
            r=run('status');self.assertEqual(json.loads(r.stdout)['candidates'],1)
            out=base/'backup.json';r=run('export','--output',str(out));self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(out.read_text())['schema'],'toad-library-v2')
            r=run('ingest','-',input='Some notes');self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(len(json.loads(run('library','list').stdout)),2)
            r=run('inspect','unknown');self.assertNotEqual(r.returncode,0);self.assertEqual(json.loads(r.stderr)['ok'],False)
