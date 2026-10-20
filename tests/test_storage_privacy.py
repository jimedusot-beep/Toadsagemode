"""POSIX workspace boundaries must precede SQLite writes."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from toad_core.storage import Store
from toad_core.schema import PackageError


@unittest.skipUnless(os.name == 'posix', 'POSIX permissions')
class StoragePrivacyTests(unittest.TestCase):
    def test_existing_workspace_and_sqlite_files_are_private_under_normal_umask(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace=Path(tmp)/'existing';workspace.mkdir(mode=0o755)
            previous=os.umask(0o022)
            store=None
            try:
                store=Store(workspace)
                self.assertEqual(stat.S_IMODE(workspace.stat().st_mode),0o700)
                for name in ('catalog.sqlite3','catalog.sqlite3-wal','catalog.sqlite3-shm'):
                    self.assertEqual(stat.S_IMODE((workspace/name).stat().st_mode),0o600,name)
            finally:
                if store:store.close()
                os.umask(previous)

    def test_permission_failure_refuses_before_sqlite_opens(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('toad_core.storage.Path.chmod',side_effect=PermissionError('denied')),patch('toad_core.storage.sqlite3.connect') as connect:
                with self.assertRaises(PackageError):Store(Path(tmp)/'private')
                connect.assert_not_called()

    def test_existing_sidecar_symlink_is_rejected_before_sqlite_opens(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace=Path(tmp)/'private';workspace.mkdir()
            target=Path(tmp)/'unrelated';target.write_text('keep')
            (workspace/'catalog.sqlite3-wal').symlink_to(target)
            with patch('toad_core.storage.sqlite3.connect') as connect:
                with self.assertRaises(PackageError):Store(workspace)
                connect.assert_not_called()
            self.assertEqual(target.read_text(),'keep')
