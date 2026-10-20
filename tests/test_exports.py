"""Backup privacy and overwrite boundaries use actual filesystem operations."""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from toad_core.cli import write_output


class ExportTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='posix','POSIX permission bits')
    def test_new_backup_is_private_even_with_permissive_umask(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'private-feed.json'
            old=os.umask(0)
            try:write_output(target,{'content':'private source'})
            finally:os.umask(old)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o600)
            self.assertEqual(json.loads(target.read_text())['content'],'private source')

    def test_existing_backup_requires_explicit_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'backup.json';target.write_text('original')
            with self.assertRaises(FileExistsError):write_output(target,{'replacement':True})
            self.assertEqual(target.read_text(),'original')
            write_output(target,{'replacement':True},force=True)
            self.assertEqual(json.loads(target.read_text()),{'replacement':True})
            if os.name=='posix':self.assertEqual(stat.S_IMODE(target.stat().st_mode),0o600)

    @unittest.skipUnless(os.name=='posix','Symlink creation')
    def test_force_replaces_symlink_without_writing_through_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            original=Path(tmp)/'untouched';original.write_text('original')
            target=Path(tmp)/'backup.json';target.symlink_to(original)
            with self.assertRaises(FileExistsError):write_output(target,{'data':1})
            write_output(target,{'data':1},force=True)
            self.assertFalse(target.is_symlink())
            self.assertEqual(original.read_text(),'original')
