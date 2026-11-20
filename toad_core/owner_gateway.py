"""Owner-only iPad AI code *draft* gateway. No candidate execution or public hosting.

Run only on an authorized cloud Python host behind a PRIVATE HTTPS port
forward. A model response is JSON data stored by QuarantinedWebGenerator.
This service never executes JavaScript, Docker, shell, Git, or deployment.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
from pathlib import Path
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .bridge import _same_origin
from .engine import default_workspace
from .schema import PackageError, strict_json
from .web_codegen import MAX_REQUEST_BYTES, QuarantinedWebGenerator

ROOT = Path(__file__).resolve().parents[1] / "owner-ai-studio"
MAX_BODY = MAX_REQUEST_BYTES + 512
TOKEN_MIN_LENGTH = 32
# Bound private-HTTPS forwarded clients, including incomplete HTTP requests.
MAX_CONCURRENT_REQUESTS = 8
HEADER_IDLE_TIMEOUT_SECONDS = 8.0
BODY_READ_DEADLINE_SECONDS = 8.0
BODY_READ_CHUNK_BYTES = 2048
ASSETS = {
    "/": ("text/html; charset=utf-8", "index.html"),
    "/index.html": ("text/html; charset=utf-8", "index.html"),
    "/app.js": ("application/javascript; charset=utf-8", "app.js"),
    "/styles.css": ("text/css; charset=utf-8", "styles.css"),
}


class OwnerStudioHTTP(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = MAX_CONCURRENT_REQUESTS

    def __init__(self, address, *, workspace=None, model=None,
                 owner_token=None, max_calls=1):
        if address[0] != "127.0.0.1":
            raise ValueError("AI Studio must bind exactly to IPv4 loopback")
        if not isinstance(max_calls, int) or isinstance(max_calls, bool) or not 1 <= max_calls <= 3:
            raise ValueError("AI Studio draft limit must be 1-3 per server lifetime")
        if owner_token is None:
            owner_token = secrets.token_urlsafe(32)
        if not isinstance(owner_token, str) or len(owner_token) < TOKEN_MIN_LENGTH or \
                any(ord(char) < 33 or ord(char) > 126 for char in owner_token):
            raise ValueError("Owner token must be a private printable 32+ character secret")
        self.owner_token = owner_token
        self.workspace = Path(workspace).expanduser() if workspace is not None else default_workspace()
        self.model = model
        self.max_calls = max_calls
        self.used_calls = 0
        self.call_lock = threading.Lock()
        self.request_slots = threading.BoundedSemaphore(MAX_CONCURRENT_REQUESTS)
        super().__init__(address, OwnerStudioHandler)

    def process_request(self, request, client_address):
        """Refuse excess clients before allocating another request thread."""
        if not self.request_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()


class OwnerStudioHandler(BaseHTTPRequestHandler):
    def setup(self):
        # BaseHTTPRequestHandler has no request timeout by default.
        self.request.settimeout(HEADER_IDLE_TIMEOUT_SECONDS)
        super().setup()

    def _read_body(self, size):
        """Enforce an overall body deadline, including slow trickle attacks."""
        body = bytearray()
        deadline = time.monotonic() + BODY_READ_DEADLINE_SECONDS
        try:
            while len(body) < size:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Request body deadline exceeded")
                self.connection.settimeout(min(remaining, HEADER_IDLE_TIMEOUT_SECONDS))
                chunk = self.rfile.read1(min(BODY_READ_CHUNK_BYTES, size - len(body)))
                if not chunk:
                    raise ValueError("Incomplete request body")
                body.extend(chunk)
            return bytes(body)
        finally:
            self.connection.settimeout(HEADER_IDLE_TIMEOUT_SECONDS)

    # No default access logs: goals, tokens, URLs and source must never leak.
    def log_message(self, *_):
        pass

    def _reply(self, status, value, content_type="application/json; charset=utf-8"):
        if isinstance(value, bytes):
            payload = value
        elif isinstance(value, str):
            payload = value.encode("utf-8")
        else:
            payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        for key, data in {
            "Content-Type": content_type,
            "Content-Length": str(len(payload)),
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": (
                "default-src 'none'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; img-src 'none'; font-src 'none'; "
                "form-action 'none'; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'none'"
            ),
        }.items():
            self.send_header(key, data)
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _authorized(self):
        candidate = self.headers.get("X-Toad-Owner-Token", "")
        if not candidate or not hmac.compare_digest(candidate, self.server.owner_token):
            self._reply(401, {"error": "Private owner token required"})
            return False
        return True

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment:
            return self._reply(400, {"error": "Query parameters are not supported"})
        if parsed.path in ASSETS:
            media_type, filename = ASSETS[parsed.path]
            return self._reply(200, (ROOT / filename).read_bytes(), media_type)
        if parsed.path == "/api/status":
            if not self._authorized():
                return
            return self._reply(200, {
                "service": "toad-owner-ai-draft-gateway",
                "provider_selection": os.environ.get("TOAD_MODEL_PROVIDER", "ollama"),
                "provider_connection_verified": False,
                "calls_remaining": max(0, self.server.max_calls - self.server.used_calls),
                "source_execution": False, "deploy_enabled": False,
                "quarantine_only": True,
            })
        if parsed.path.startswith("/api/drafts/"):
            if not self._authorized():
                return
            identifier = parsed.path.removeprefix("/api/drafts/")
            try:
                record = QuarantinedWebGenerator(self.server.workspace).show(identifier)
            except (PackageError, OSError, ValueError):
                return self._reply(404, {"error": "Draft not found or failed integrity checks"})
            return self._reply(200, record)
        return self._reply(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlsplit(self.path)
        if parsed.path != "/api/drafts" or parsed.query or parsed.fragment:
            return self._reply(404, {"error": "Not found"})
        if not self._authorized():
            return
        if not _same_origin(self.headers.get("Origin", ""), self.headers.get("Host", "")):
            return self._reply(403, {"error": "Matching browser origin required"})
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self._reply(415, {"error": "JSON request required"})
        size = self.headers.get("Content-Length", "")
        if (not size or len(size) > len(str(MAX_BODY)) or
                not size.isascii() or not size.isdecimal() or
                not 1 <= int(size) <= MAX_BODY):
            return self._reply(413, {"error": "Missing or oversized request"})
        try:
            body = self._read_body(int(size))
        except TimeoutError:
            self.close_connection = True
            return self._reply(408, {"error": "Request body deadline exceeded"})
        except (OSError, ValueError):
            self.close_connection = True
            return self._reply(400, {"error": "Incomplete request"})
        try:
            request = strict_json(body.decode("utf-8"))
            if not isinstance(request, dict) or set(request) != {"goal"} or \
                    not isinstance(request["goal"], str):
                raise ValueError("Only a single goal is accepted")
            goal = request["goal"]
            if not goal.strip() or "\x00" in goal or \
                    len(goal.encode("utf-8")) > MAX_REQUEST_BYTES:
                raise ValueError("Goal must be 1-2500 UTF-8 bytes")
        except (UnicodeError, PackageError, ValueError):
            return self._reply(400, {"error": "Invalid bounded goal JSON"})
        # Reserve the call before contacting a model; no concurrency/retry
        # loophole can permit additional potentially billable invocations.
        with self.server.call_lock:
            if self.server.used_calls >= self.server.max_calls:
                return self._reply(429, {"error": "Draft quota exhausted; owner restart required"})
            self.server.used_calls += 1
        try:
            result = QuarantinedWebGenerator(
                self.server.workspace, model=self.server.model
            ).propose(goal)
        except (PackageError, OSError, RuntimeError, ValueError):
            # Do not print raw model failures, prompts, stack traces, or keys.
            return self._reply(503, {"error": "Model unavailable or draft rejected; inspect the trusted host"})
        return self._reply(201, result)


def serve(workspace=None, port=8766, *, owner_token=None, max_calls=1):
    if os.environ.get("TOAD_ENABLE_PRIVATE_AI_STUDIO") != "YES":
        raise ValueError("AI Studio disabled; explicit private-host opt-in is required")
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        raise ValueError("Choose an unprivileged port")
    host = OwnerStudioHTTP(
        ("127.0.0.1", port), workspace=workspace,
        owner_token=owner_token, max_calls=max_calls
    )
    try:
        print("Toad owner AI drafts listening on 127.0.0.1:" + str(host.server_port), flush=True)
        print("Use PRIVATE HTTPS forwarded port only; never expose this directly.", flush=True)
        if owner_token is None:
            print("Generated owner token (keep private): " + host.owner_token, flush=True)
        else:
            print("Owner token loaded from trusted server configuration (not displayed).", flush=True)
        print("Model calls allowed this run: " + str(host.max_calls), flush=True)
        host.serve_forever()
    finally:
        host.server_close()


def main():
    parser = argparse.ArgumentParser(description="Owner-only AI draft gateway; no deployment")
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--max-drafts", type=int, default=1, choices=(1, 2, 3))
    options = parser.parse_args()
    serve(options.workspace, options.port, owner_token=os.environ.get("TOAD_OWNER_AI_TOKEN"),
          max_calls=options.max_drafts)


if __name__ == "__main__":
    main()
