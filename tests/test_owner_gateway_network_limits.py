"""Bounded private AI gateway network handling. Real loopback TCP; NO model calls.

Tests exercise production OwnerStudioHTTP and intentionally incomplete
requests. No browser model or Docker is used.
"""
import http.client
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest import mock

from toad_core import owner_gateway


TOKEN = "test-only-private-token-at-least-32-characters"


class NoModel:
    def __init__(self):
        self.calls = 0

    def generate_json(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("Unfinished HTTP requests must never contact the model")


class OwnerGatewayNetworkLimitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model = NoModel()
        self.server = owner_gateway.OwnerStudioHTTP(
            ("127.0.0.1", 0), workspace=Path(self.temp.name),
            owner_token=TOKEN, model=self.model, max_calls=1,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        self.address = ("127.0.0.1", self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def _socket(self):
        connection = socket.create_connection(self.address, timeout=3)
        connection.settimeout(3)
        return connection

    @staticmethod
    def _request_head(length):
        return (
            "POST /api/drafts HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\n"
            "Origin: http://127.0.0.1\r\n"
            "X-Toad-Owner-Token: " + TOKEN + "\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: " + str(length) + "\r\n"
            "Connection: close\r\n\r\n"
        ).encode()

    def test_truncated_body_returns_400_and_never_consumes_model_quota(self):
        with self._socket() as connection:
            connection.sendall(self._request_head(40) + b'{"goal":"incomplete"')
            connection.shutdown(socket.SHUT_WR)
            response = connection.recv(4096)
        self.assertIn(b"HTTP/1.0 400", response)
        self.assertEqual(self.server.used_calls, 0)
        self.assertEqual(self.model.calls, 0)

    def test_body_deadline_returns_408_without_model_request(self):
        with mock.patch.object(owner_gateway, "BODY_READ_DEADLINE_SECONDS", 0.2):
            with self._socket() as connection:
                connection.sendall(self._request_head(40) + b'{"goal":"slow"')
                response = connection.recv(4096)
        self.assertIn(b"HTTP/1.0 408", response)
        self.assertEqual(self.server.used_calls, 0)
        self.assertEqual(self.model.calls, 0)

    def test_header_idle_deadline_drops_incomplete_headers(self):
        with mock.patch.object(owner_gateway, "HEADER_IDLE_TIMEOUT_SECONDS", 0.2):
            with self._socket() as connection:
                connection.sendall(b"GET /api/status HTTP/1.1\r\nHost:")
                result = connection.recv(1)
        self.assertEqual(result, b"")
        self.assertEqual(self.server.used_calls, 0)
        self.assertEqual(self.model.calls, 0)

    def test_over_capacity_connection_is_dropped_before_thread_creation(self):
        blocked = threading.BoundedSemaphore(1)
        self.assertTrue(blocked.acquire(blocking=False))
        with mock.patch.object(self.server, "request_slots", blocked):
            with self._socket() as connection:
                connection.sendall(b"GET / HTTP/1.0\r\n\r\n")
                self.assertEqual(connection.recv(1), b"")
        self.assertEqual(self.model.calls, 0)

        # After releasing the synthetic limit, an ordinary request still works.
        client = http.client.HTTPConnection(*self.address, timeout=3)
        try:
            client.request("GET", "/api/status")
            response = client.getresponse()
            response.read()
            self.assertEqual(response.status, 401)
        finally:
            client.close()

    def test_connection_limit_is_fixed_and_request_threads_release_slots(self):
        self.assertEqual(owner_gateway.MAX_CONCURRENT_REQUESTS, 8)
        for _ in range(3):
            client = http.client.HTTPConnection(*self.address, timeout=3)
            try:
                client.request("GET", "/api/status")
                result = client.getresponse()
                result.read()
                self.assertEqual(result.status, 401)
            finally:
                client.close()
        self.assertEqual(self.model.calls, 0)


if __name__ == "__main__":
    unittest.main()
