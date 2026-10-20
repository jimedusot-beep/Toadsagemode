"""End-to-end private bridge tests over actual loopback sockets; never executes feeds."""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from toad_core.bridge import BridgeHTTP, _same_origin


class PrivateBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = BridgeHTTP(("127.0.0.1", 0), workspace=Path(self.tmp.name), pairing_code="this-is-a-long-enough-unique-test-secret")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = "127.0.0.1:" + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        con = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            con.request(method, path, body=body, headers=headers or {})
            response = con.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            con.close()

    def test_reject_external_origin_and_unauthenticated(self):
        status, _, _ = self.request("GET", "/api/candidates")
        self.assertEqual(status, 401)
        for origin in ["https://evil.example", "https://" + self.host + ".evil.com", "null"]:
            status, _, _ = self.request("POST", "/login", "code=anything", {"Origin": origin, "Content-Type": "application/x-www-form-urlencoded"})
            self.assertEqual(status, 403)
        self.assertFalse(_same_origin("https://evil.example", self.host))

    def test_feed_round_trip_and_no_execution(self):
        headers = {"Origin": "http://" + self.host, "Content-Type": "application/x-www-form-urlencoded"}
        status, response, _ = self.request("POST", "/login", "code=this-is-a-long-enough-unique-test-secret", headers)
        self.assertEqual(status, 303)
        cookie = response["Set-Cookie"].split(";", 1)[0]
        self.assertIn("HttpOnly", response["Set-Cookie"])
        self.assertIn("SameSite=Strict", response["Set-Cookie"])
        status, _, raw = self.request("GET", "/api/status", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        csrf = json.loads(raw)["bridge"]["csrf"]
        # Even with a valid cookie, a cross-origin or missing-CSRF write is denied.
        payload = json.dumps({"content": "print('hello')", "name": "greeting"}).encode()
        status, _, _ = self.request("POST", "/api/feed", payload, {"Cookie": cookie, "Origin": "http://" + self.host, "Content-Type": "application/json"})
        self.assertEqual(status, 403)
        malicious = "__import__('pathlib').Path('BAD_MARKER').write_text('bad')"
        payload = json.dumps({"content": malicious, "name": "harmless-data"}).encode()
        status, _, result = self.request("POST", "/api/feed", payload, {"Cookie": cookie, "Origin": "http://" + self.host, "Content-Type": "application/json", "X-Toad-CSRF": csrf})
        self.assertEqual(status, 201, result.decode())
        record = json.loads(result)
        self.assertTrue(record["received"])
        self.assertFalse(record["executed"])
        self.assertTrue(record["id"])
        self.assertFalse((Path(self.tmp.name) / "BAD_MARKER").exists())
        status, _, listing = self.request("GET", "/api/candidates", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(listing)[0]["name"], "harmless-data")
        status, _, html = self.request("GET", "/private", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertIn(b"Private Console", html)
        status, _, js = self.request("GET", "/private/ui.js", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertIn(b"X-Toad-CSRF", js)

    def test_empty_and_non_json_inputs_rejected(self):
        headers = {"Origin": "http://" + self.host, "Content-Type": "application/x-www-form-urlencoded"}
        status, _, _ = self.request("POST", "/login", "code=wrong", headers)
        self.assertEqual(status, 401)
        status, _, _ = self.request("GET", "/api/missions")
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
