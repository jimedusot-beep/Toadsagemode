import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from toad_core.engine import Engine
from toad_core.installation import Registry
from toad_core.schema import PackageError
from test_packages import package
from test_lab import DockerBoundary

class InstallationTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.engine=Engine(Path(self.tmp.name)/'data');self.registry=Registry(self.engine)
    def tearDown(self):self.engine.close();self.tmp.cleanup()
    def verified(self,code='print("hello")\n',version='0.1.0'):
        r=self.engine.ingest_package(package(code=code,version=version))
        with patch('toad_core.lab.shutil.which',return_value='/usr/bin/docker'),patch('toad_core.lab.run_limited',side_effect=DockerBoundary()):
            self.assertTrue(self.engine.test(r['id'])['passed'])
        return self.engine.get(r['id'])
    def test_unverified_and_imported_claims_cannot_activate(self):
        a=self.engine.ingest_package(package())
        with self.assertRaises(PackageError):self.registry.activate(a['id'])
        backup=self.engine.export();backup['abilities'][0].update(status='installed',installed=True,verification='verified')
        other=Engine(Path(self.tmp.name)/'other')
        try:
            other.import_library(backup)
            with self.assertRaises(PackageError):Registry(other).activate(other.list()[0]['id'])
        finally:other.close()
    def test_versioned_activation_and_rollback_remain_sandbox_only(self):
        a=self.verified();first=self.registry.activate(a['id'])
        self.assertEqual(first['activation_mode'],'sandbox_only')
        self.assertTrue(self.engine.get(a['id'])['installed'])
        b=self.verified(code='print("hello")\n# second version\n',version='0.2.0')
        second=self.registry.activate(b['id'])
        self.assertFalse(self.engine.get(a['id'])['installed'])
        self.assertTrue((Path(first['path'])/'main.py').exists())
        self.assertTrue((Path(second['path'])/'main.py').exists())
        rolled=self.registry.rollback(a['name'])
        self.assertEqual(rolled['candidate_id'],a['id'])
        self.assertFalse(self.engine.get(b['id'])['installed'])
        self.assertEqual(self.registry.activate(a['id'])['candidate_id'],a['id'])
    def test_tampering_or_privilege_expansion_refuses_activation(self):
        a=self.verified()
        with self.assertRaises(PackageError):self.registry.activate(a['id'],allowed_capabilities=['network'])
        active=self.registry.activate(a['id']);self.registry.deactivate(a['name'])
        source=Path(active['path'])/'main.py';source.chmod(0o600);source.write_text('print("changed")')
        with self.assertRaises(PackageError):self.registry.activate(a['id'])
    def test_changed_manifest_cannot_reuse_receipt(self):
        a=self.verified()
        self.engine.store.mutate(a['id'],lambda r:r['manifest']['files'][0].update(content='print("not hello")'))
        with self.assertRaises(PackageError):self.registry.activate(a['id'])
    def test_active_and_rollback_candidates_cannot_be_deleted(self):
        a=self.verified();self.registry.activate(a['id'])
        with self.assertRaises(PackageError):self.engine.delete(a['id'])
        b=self.verified(code='print("hello")\n# next\n',version='0.2.0');self.registry.activate(b['id'])
        with self.assertRaises(PackageError):self.engine.delete(a['id'])

    def test_successful_retest_of_inactive_snapshot_can_reactivate(self):
        a=self.verified();self.registry.activate(a['id']);self.registry.deactivate(a['name'])
        with patch('toad_core.lab.shutil.which',return_value='/usr/bin/docker'),patch('toad_core.lab.run_limited',side_effect=DockerBoundary()):self.engine.test(a['id'])
        self.assertEqual(self.registry.activate(a['id'])['candidate_id'],a['id'])
