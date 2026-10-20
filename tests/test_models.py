import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from toad_core.models import ModelConfig,OllamaAdapter,ModelError

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.requests=[];self.mode='ok';outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));outer.requests.append((self.path,body))
                if outer.mode=='redirect':self.send_response(302);self.send_header('Location','http://example.com');self.end_headers();return
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
                data={'done':True,'response':json.dumps({'files':[],'summary':'candidate only'})}
                if outer.mode=='bad':data={'done':True,'response':'not JSON'}
                if outer.mode=='incomplete':data['done']=False
                if outer.mode=='big':data['response']='x'*10000
                raw=json.dumps(data).encode()
                if outer.mode=='slow':
                    import time
                    try:
                        for byte in raw:self.wfile.write(bytes([byte]));self.wfile.flush();time.sleep(0.05)
                    except (BrokenPipeError,ConnectionResetError):pass
                else:self.wfile.write(raw)
            def do_GET(self):
                self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'models':[{'name':'test-coder'}]}).encode())
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.endpoint=f'http://127.0.0.1:{self.server.server_port}'
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join()
    def adapter(self,**kw):return OllamaAdapter(ModelConfig(endpoint=self.endpoint,model='test-coder',**kw))
    def test_real_http_adapter_uses_bounded_structured_local_requests(self):
        model=self.adapter();result=model.generate_json('Explain this code as data')
        self.assertEqual(result['summary'],'candidate only')
        path,payload=self.requests[0];self.assertEqual(path,'/api/generate')
        self.assertFalse(payload['stream']);self.assertEqual(payload['format'],'json')
        self.assertEqual(payload['options']['temperature'],0);self.assertLessEqual(payload['options']['num_predict'],4096)
        self.assertTrue(model.availability()['available'])
    def test_malformed_incomplete_large_and_redirect_responses_are_refused(self):
        for mode in ['bad','incomplete','big','redirect']:
            with self.subTest(mode=mode):
                self.mode=mode
                with self.assertRaises(ModelError):self.adapter(max_response_bytes=2000).generate_json('hello')
    def test_remote_credentials_and_oversized_prompts_are_refused(self):
        for endpoint in ['http://example.com:11434','http://user:pass@localhost:11434','file:///tmp/model','http://127.0.0.1:11434/evil']:
            with self.assertRaises(ValueError):ModelConfig(endpoint=endpoint)
        with self.assertRaises(ModelError):self.adapter(max_prompt_bytes=1000).generate_json('x'*1001)
    def test_missing_server_is_reported_without_breaking_offline_engine(self):
        model=OllamaAdapter(ModelConfig(endpoint='http://127.0.0.1:1',model='none',timeout_seconds=0.1))
        self.assertFalse(model.availability()['available'])
        with self.assertRaises(ModelError):model.generate_json('hello')

    def test_slow_trickle_response_cannot_bypass_whole_operation_deadline(self):
        import time
        self.mode='slow';start=time.monotonic()
        with self.assertRaises(ModelError):self.adapter(timeout_seconds=0.1).generate_json('hello')
        self.assertLess(time.monotonic()-start,0.6)
