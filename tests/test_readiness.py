"""Readiness is capability-specific and never generates or executes candidate code."""
import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from toad_core.cli import main
from toad_core.engine import Engine
from test_lab import DockerBoundary


def invoke(workspace,*args):
    stdout=io.StringIO();stderr=io.StringIO()
    with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
        try:code=main(['--workspace',str(workspace),'doctor',*args])
        except SystemExit as exc:code=exc.code
    return code,stdout.getvalue(),stderr.getvalue()


class ReadinessTests(unittest.TestCase):
    def test_default_is_offline_and_does_not_claim_mission_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('toad_core.lab.DockerWorker._call',side_effect=AssertionError('unexpected Docker call')),patch('toad_core.models.OllamaAdapter._request',side_effect=AssertionError('unexpected HTTP request')):
                code,out,err=invoke(Path(tmp)/'catalog')
            self.assertEqual(code,0,err)
            report=json.loads(out)
            self.assertEqual(report['schema'],'toad-readiness-v1')
            self.assertEqual(report['capabilities']['library'],'ready')
            self.assertEqual(report['capabilities']['testing'],'not_checked')
            self.assertEqual(report['capabilities']['missions'],'not_checked')
            self.assertFalse(report['execution_performed'])
            self.assertFalse(report['containment_verified'])
            self.assertTrue(any('doctor --probe' in x for x in report['next_steps']))

    def test_probes_report_missing_dependencies_without_disabling_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('toad_core.lab.shutil.which',return_value=None),patch.dict(os.environ,{'TOAD_OLLAMA_URL':'https://user:private-password@example.com'}):
                code,out,err=invoke(Path(tmp)/'catalog','--probe')
            self.assertEqual(code,2,err)
            report=json.loads(out)
            self.assertEqual(report['capabilities'],{'library':'ready','testing':'blocked','missions':'blocked'})
            self.assertEqual(report['checks']['lab']['status'],'blocked')
            self.assertEqual(report['checks']['model']['status'],'blocked')
            self.assertNotIn('private-password',out)
            self.assertFalse(report['execution_performed'])

    def test_workspace_failure_is_structured_and_blocks_all_capabilities(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'file';path.write_text('not a directory')
            code,out,err=invoke(path)
            self.assertEqual(code,1,err)
            report=json.loads(out)
            self.assertEqual(set(report['capabilities'].values()),{'blocked'})
            self.assertEqual(report['checks']['workspace']['status'],'blocked')
            self.assertTrue(report['next_steps'])

    def test_report_does_not_export_candidate_content_or_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace=Path(tmp)/'catalog';engine=Engine(workspace)
            candidate=engine.ingest_text('PRIVATE-CONTENT-SENTINEL',name='private-name-sentinel');engine.close()
            code,out,err=invoke(workspace)
            self.assertEqual(code,0,err)
            self.assertNotIn(candidate['content'],out)
            self.assertNotIn(candidate['name'],out)
            self.assertEqual(json.loads(out)['checks']['workspace']['candidates'],1)

    def test_available_probes_use_metadata_only_without_claiming_containment(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                requests.append(('GET',self.path))
                self.send_response(200);self.end_headers();self.wfile.write(b'{"models":[{"name":"test-coder"}]}')
            def do_POST(self):
                requests.append(('POST',self.path));self.send_error(500)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        boundary=DockerBoundary()
        try:
            with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'TOAD_OLLAMA_URL':f'http://127.0.0.1:{server.server_port}','TOAD_OLLAMA_MODEL':'test-coder'}),patch('toad_core.lab.shutil.which',return_value='/usr/bin/docker'),patch('toad_core.lab.run_limited',side_effect=boundary):
                code,out,err=invoke(Path(tmp)/'catalog','--probe')
            self.assertEqual(code,0,err)
            report=json.loads(out)
            self.assertEqual(set(report['capabilities'].values()),{'ready'})
            self.assertFalse(report['containment_verified'])
            self.assertFalse(report['execution_performed'])
            self.assertEqual(requests,[('GET','/api/tags')])
            self.assertEqual(len(boundary.calls),2)
            self.assertTrue(all('info' in cmd or 'image' in cmd for cmd,kw in boundary.calls))
            self.assertTrue(any('smoke' in x.lower() for x in report['next_steps']))
        finally:server.shutdown();server.server_close();thread.join()

    def test_corrupt_catalog_is_reported_without_resetting_private_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace=Path(tmp)/'catalog';workspace.mkdir()
            database=workspace/'catalog.sqlite3';original=b'not sqlite; preserve this data'
            database.write_bytes(original)
            code,out,err=invoke(workspace)
            self.assertEqual(code,1,err)
            self.assertEqual(json.loads(out)['checks']['workspace']['status'],'blocked')
            self.assertEqual(database.read_bytes(),original)

    def test_requested_probes_are_marked_skipped_when_workspace_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'file';path.write_text('not a directory')
            code,out,err=invoke(path,'--probe')
            self.assertEqual(code,1,err)
            report=json.loads(out)
            self.assertTrue(report['probes_requested'])
            for name in ('lab','model'):
                self.assertEqual(report['checks'][name]['status'],'not_checked')
                self.assertIn('blocked',report['checks'][name]['reason'])
