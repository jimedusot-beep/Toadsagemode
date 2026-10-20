import json
import tempfile
import unittest
from pathlib import Path
from toad_core.engine import Engine
from toad_core.schema import PackageError
from test_packages import package


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.engine=Engine(self.root/'data')
    def tearDown(self):self.engine.close();self.temp.cleanup()

    def test_ingest_duplicate_survives_restart_and_keeps_source(self):
        a=self.engine.ingest_text('print(1)',source='ChatGPT')
        b=self.engine.ingest_text('print(1)',source='Gemini')
        self.assertEqual(a['id'],b['id'])
        self.assertTrue(b['duplicate'])
        self.assertEqual(len(self.engine.list()),1)
        self.engine.close();self.engine=Engine(self.root/'data')
        self.assertEqual(self.engine.get(a['id'])['content'],'print(1)')
        self.assertIn('Gemini',self.engine.get(a['id'])['extensions']['duplicate_sources'])

    def test_backup_import_is_atomic_and_cannot_inject_test_receipts(self):
        first=self.engine.ingest_text('first idea')
        backup=self.engine.export()
        backup['abilities'][0]['status']='verified';backup['abilities'][0]['test_results']=[{'passed':True,'backend':'docker'}]
        other=Engine(self.root/'other')
        try:
            other.import_library(backup)
            record=other.list()[0]
            self.assertEqual(record['verification'],'unverified')
            self.assertEqual(record['test_results'],[])
            self.assertIsNone(other.store.latest_receipt(record['id']))
            broken=json.loads(json.dumps(backup));broken['abilities'].append({'name':'../bad','content':'x'})
            with self.assertRaises(PackageError):other.import_library(broken)
            self.assertEqual(len(other.list()),1)
        finally:other.close()
        self.assertEqual(self.engine.get(first['id'])['content'],'first idea')

    def test_search_filter_archive_delete_and_export(self):
        a=self.engine.ingest_text('Analyze infrared sensor readings',name='infrared')
        b=self.engine.ingest_text('print(2)',name='python-demo')
        self.assertEqual([r['id'] for r in self.engine.list(query='infrared')],[a['id']])
        self.assertEqual([r['id'] for r in self.engine.list(language='Python')],[b['id']])
        self.engine.archive(a['id'])
        self.assertEqual(self.engine.get(a['id'])['status'],'archived')
        self.assertEqual(len(self.engine.list(status='archived')),1)
        self.assertEqual(len(self.engine.export(ids=[a['id']])['abilities']),1)
        self.engine.delete(a['id'])
        with self.assertRaises(KeyError):self.engine.get(a['id'])

    def test_queue_inspection_claims_once_and_records_failures(self):
        a=self.engine.ingest_text('print(1)')
        j=self.engine.queue_inspection(a['id'])
        self.assertEqual(self.engine.run_queue(limit=1)[0]['state'],'completed')
        self.assertEqual(self.engine.run_queue(limit=1),[])
        self.assertEqual(self.engine.store.job(j)['attempts'],1)
        self.engine.queue_inspection('does-not-exist')
        results=self.engine.run_queue(limit=1)
        self.assertEqual(results[0]['state'],'failed')
        self.assertIn('does-not-exist',results[0]['error'])

    def test_job_expired_lease_requeues_without_unbounded_retries(self):
        a=self.engine.ingest_text('print(1)');job_id=self.engine.queue_inspection(a['id'])
        claimed=self.engine.store.claim_job(now=10,lease_seconds=1)
        self.assertEqual(claimed['id'],job_id)
        second=self.engine.store.claim_job(now=12,lease_seconds=1)
        self.assertEqual(second['attempts'],2)
        third=self.engine.store.claim_job(now=14,lease_seconds=1)
        self.assertEqual(third['attempts'],3)
        self.assertIsNone(self.engine.store.claim_job(now=16,lease_seconds=1))
        self.assertEqual(self.engine.store.job(job_id)['state'],'failed')

    def test_digest_and_status_are_recomputed_from_source(self):
        a=self.engine.ingest_package(package())
        self.assertEqual(a['status'],'ready_for_testing')
        self.assertFalse(a['installed'])
        self.assertEqual(a['verification'],'unverified')
        self.assertTrue(a['validation_results']['syntax_checked'])

    def test_unknown_backup_metadata_roundtrips(self):
        backup={'schema':'toad-library-v1','owner':'Jimmy','abilities':[{'name':'old-demo','version':'0.1.0','content':'print(1)','custom':7,'status':'unverified','installed':False}]}
        self.engine.import_library(backup)
        out=self.engine.export()
        self.assertEqual(out['abilities'][0]['extensions']['original']['custom'],7)
        self.assertEqual(out['extensions']['imports'][0]['original']['owner'],'Jimmy')
