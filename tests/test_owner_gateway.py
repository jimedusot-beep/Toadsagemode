"""Private iPad AI Draft Lab: real loopback HTTP tests, model doubles ONLY."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from toad_core.owner_gateway import OwnerStudioHTTP, serve


TOKEN = "this-is-a-test-only-owner-token-long-enough-123"


class ModelDouble:
    def __init__(self, *, fail=False):
        self.calls = []
        self.fail = fail

    def generate_json(self, prompt, **kwargs):
        self.calls.append((json.loads(prompt), kwargs))
        if self.fail:
            raise RuntimeError("simulated unavailable model; do-not-leak-secret")
        return {
            "schema": "toad-web-source-draft-v1",
            "name": "ipad-study-draft",
            "title": "iPad Study Draft",
            "files": [
                {"path": "index.html",
                 "content": "<!doctype html><html><body><h1>Study</h1><script src='app.js'></script></body></html>"},
                {"path": "styles.css", "content": "body { color: green; }"},
                {"path": "app.js", "content": "document.querySelector('h1').textContent = 'Studying';"},
            ],
            "declared_features": ["editable learning tasks"],
        }


class OwnerGatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.model = ModelDouble()
        self.server = OwnerStudioHTTP(
            ("127.0.0.1", 0), workspace=Path(self.tmp.name),
            owner_token=TOKEN, model=self.model, max_calls=1
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = "127.0.0.1:" + str(self.server.server_port)
        self.origin = "http://" + self.host

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def request(self, method, path, payload=None, headers=None):
        client = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            client.request(method, path, body=payload, headers=headers or {})
            response = client.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            client.close()

    def auth(self, *, origin=None):
        return {
            "X-Toad-Owner-Token": TOKEN,
            "Origin": origin or self.origin,
            "Content-Type": "application/json",
        }

    def test_static_ui_is_source_only_and_not_authenticated_by_cookie(self):
        for route, needle in [
            ("/", b"AI Code Draft Lab"),
            ("/app.js", b"textContent"),
            ("/styles.css", b"max-width"),
        ]:
            status, headers, body = self.request("GET", route)
            self.assertEqual(status, 200)
            self.assertIn(needle, body)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
            self.assertNotIn("Set-Cookie", headers)
        status, _, _ = self.request("GET", "/api/status")
        self.assertEqual(status, 401)
        self.assertEqual(self.model.calls, [])

    def test_auth_origin_and_shape_refused_before_model_call(self):
        body = json.dumps({"goal": "Build a small study app"})
        cases = [
            ({}, 401, body),
            ({"X-Toad-Owner-Token": "wrong", "Origin": self.origin,
              "Content-Type": "application/json"}, 401, body),
            (self.auth(origin="https://evil.example"), 403, body),
            (self.auth() | {"Content-Type": "text/plain"}, 415, body),
            (self.auth(), 400, json.dumps({"goal": 1})),
            (self.auth(), 400, json.dumps({"goal": "Study", "shell": "please"})),
            (self.auth(), 400, '{"goal":"study","goal":"duplicate"}'),
            (self.auth(), 400, json.dumps({"goal": ""})),
            (self.auth(), 400, json.dumps({"goal": "x" * 2501})),
        ]
        for headers, expected, payload in cases:
            with self.subTest(expected=expected, payload=payload[:50]):
                status, _, _ = self.request("POST", "/api/drafts", payload, headers)
                self.assertEqual(status, expected)
        self.assertEqual(self.model.calls, [])
        self.assertEqual(self.server.used_calls, 0)

    def test_real_socket_quarantine_is_inert_json_and_cap_is_enforced(self):
        status, _, body = self.request("GET", "/api/status", headers=self.auth())
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["calls_remaining"], 1)
        self.assertFalse(json.loads(body)["source_execution"])

        payload = json.dumps({"goal": "Build an original interactive study app"})
        status, _, body = self.request("POST", "/api/drafts", payload, self.auth())
        self.assertEqual(status, 201, body)
        result = json.loads(body)
        self.assertEqual(result["status"], "quarantined_unverified")
        self.assertFalse(result["executed"])
        self.assertFalse(result["tested"])
        self.assertFalse(result["deployed"])
        self.assertFalse(result["release_allowed"])
        self.assertEqual(len(self.model.calls), 1)
        self.assertEqual(self.model.calls[0][0]["request"], "Build an original interactive study app")
        saved = list((Path(self.tmp.name) / "ai-web-drafts").iterdir())
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].suffix, ".json")
        self.assertFalse(any(p.suffix in (".html", ".js", ".css", ".zip")
                             for p in Path(self.tmp.name).rglob("*") if p.is_file()))

        status, _, content = self.request("GET", "/api/drafts/" + result["id"],
                                          headers=self.auth())
        self.assertEqual(status, 200)
        response = json.loads(content)
        self.assertEqual(response["draft"]["files"][2]["path"], "app.js")
        self.assertIn("textContent", response["draft"]["files"][2]["content"])
        self.assertFalse(response["release_allowed"])
        status, _, _ = self.request("GET", "/api/drafts/" + result["id"])
        self.assertEqual(status, 401)
        status, _, _ = self.request("POST", "/api/drafts", payload, self.auth())
        self.assertEqual(status, 429)
        self.assertEqual(len(self.model.calls), 1)
        status, _, body = self.request("GET", "/api/status", headers=self.auth())
        self.assertEqual(json.loads(body)["calls_remaining"], 0)

    def test_failed_provider_does_not_leak_internal_error_and_uses_call_quota(self):
        self.server.model = ModelDouble(fail=True)
        payload = json.dumps({"goal": "Build a study app"})
        status, _, raw = self.request("POST", "/api/drafts", payload, self.auth())
        self.assertEqual(status, 503)
        self.assertNotIn(b"do-not-leak-secret", raw)
        self.assertEqual(len(self.server.model.calls), 1)
        status, _, _ = self.request("POST", "/api/drafts", payload, self.auth())
        self.assertEqual(status, 429)

    def test_reject_unknown_routes_query_tokens_and_bad_bindings(self):
        self.assertEqual(self.request("GET", "/?token=secrets")[0], 400)
        self.assertEqual(self.request("POST", "/api/feed", "{}", self.auth())[0], 404)
        self.assertEqual(self.request("GET", "/api/drafts/../../bad", headers=self.auth())[0], 404)
        with self.assertRaisesRegex(ValueError, "loopback"):
            OwnerStudioHTTP(("0.0.0.0", 0), owner_token=TOKEN)
        with self.assertRaisesRegex(ValueError, "token"):
            OwnerStudioHTTP(("127.0.0.1", 0), owner_token="weak")
        with self.assertRaisesRegex(ValueError, "limit"):
            OwnerStudioHTTP(("127.0.0.1", 0), owner_token=TOKEN, max_calls=50)

    def test_start_requires_explicit_host_opt_in(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "disabled"):
                serve(workspace=Path(self.tmp.name), port=8766)


if __name__ == "__main__":
    unittest.main()
