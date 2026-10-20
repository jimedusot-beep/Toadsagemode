"""Private, read/write feed bridge; no public remote execution endpoint.

Serve ONLY on loopback and put a trusted private HTTPS ingress (such as
Tailscale Serve, not Funnel) in front for iPhone access. The public GitHub
Pages site does not contain secrets or connect to this bridge.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import secrets
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .engine import Engine
from .schema import PackageError, MAX_PACKAGE_BYTES

MAX_BODY = MAX_PACKAGE_BYTES + 4096
SESSION_SECONDS = 3600 * 4
ASSETS = {
    "/private/ui.js": ("application/javascript; charset=utf-8", "private/ui.js"),
    "/private/ui.css": ("text/css; charset=utf-8", "private/ui.css"),
}
ROOT = Path(__file__).resolve().parents[1]


def _same_origin(origin, host):
    """Require a browser Origin from the exact public hostname; no wildcards."""
    try:
        parsed = urlsplit(origin)
        return parsed.scheme in ("https", "http") and parsed.netloc == host and not parsed.path and not parsed.query and not parsed.fragment
    except (ValueError, TypeError):
        return False


class BridgeHTTP(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, *, workspace=None, pairing_code=None):
        host, port = address
        if host not in ("127.0.0.1", "::1"):
            raise ValueError("Bridge must bind loopback only")
        self.workspace = workspace
        self.pairing_code = pairing_code or secrets.token_urlsafe(24)
        if len(self.pairing_code) < 20:
            raise ValueError("Pairing code must have at least 20 characters")
        self.sessions = {}
        self.failures = 0
        self.blocked_until = 0.0
        super().__init__(address, BridgeHandler)


class BridgeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, format, *args):
        # Never log feed bodies, pairing tokens, cookies, or private URLs.
        pass

    def _headers(self, code, mime="application/json; charset=utf-8", length=0, extra=None):
        self.send_response(code)
        for key, value in {
            "Content-Type": mime,
            "Content-Length": str(length),
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            **(extra or {}),
        }.items():
            self.send_header(key, value)
        self.end_headers()

    def _respond(self, code, data, mime="application/json; charset=utf-8", extra=None):
        body = data if isinstance(data, bytes) else data.encode("utf-8") if isinstance(data, str) else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._headers(code, mime, len(body), extra)
        self.wfile.write(body)

    def _redirect(self, path, extra=None):
        self._headers(303, length=0, extra={"Location": path, **(extra or {})})

    def _session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            entry = cookie.get("toad_session")
            token = entry.value if entry else None
        except Exception:
            return None
        if token is None:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        session = self.server.sessions.get(digest)
        if session and session["expires"] > time.monotonic():
            return session
        return None

    def _authorized(self):
        if not self._session():
            self._respond(401, {"error": "Sign in to the private bridge"})
            return False
        return True

    def _payload(self):
        length = self.headers.get("Content-Length", "")
        if not length.isdigit() or int(length) > MAX_BODY or int(length) < 1:
            raise ValueError("Missing or oversized request")
        raw = self.rfile.read(int(length))
        if len(raw) != int(length):
            raise ValueError("Incomplete request")
        return raw

    def _origin_ok(self):
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin", "")
        return bool(host) and _same_origin(origin, host)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/healthz":
            return self._respond(200, {"service": "toad-private-bridge", "remote_execution": False})
        if path == "/login":
            return self._respond(200, '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Toad private sign-in</title></head><body><h1>Toad Sage · Private Bridge</h1><p>Enter the pairing code displayed by the local Toad bridge command. Never paste it into GitHub Pages.</p><form action="/login" method="post"><label>Pairing code <input type="password" name="code" autocomplete="off" required></label><button>Connect</button></form></body></html>', "text/html; charset=utf-8")
        if path == "/private":
            if not self._session():
                return self._redirect("/login")
            return self._respond(200, (ROOT / "private" / "index.html").read_bytes(), "text/html; charset=utf-8")
        if path in ASSETS:
            if not self._authorized():
                return
            mime, name = ASSETS[path]
            return self._respond(200, (ROOT / name).read_bytes(), mime)
        if path in ("/api/status", "/api/candidates", "/api/missions"):
            if not self._authorized():
                return
            try:
                engine = Engine(self.server.workspace)
                try:
                    if path == "/api/status":
                        data = engine.status()
                        data["bridge"] = {"connected": True, "execution_enabled": False, "csrf": self._session()["csrf"]}
                    elif path == "/api/candidates":
                        data = [{"id": a["id"], "name": a["name"], "status": a["status"], "language": a["language"]} for a in engine.list()[:100]]
                    else:
                        from .mission_engine import MissionEngine
                        data = [{"id": m["id"], "status": m["status"], "goal": m["goal"][:150], "phase": m["progress"]["phase"]} for m in MissionEngine(engine).list()[:100]]
                finally:
                    engine.close()
            except (OSError, ValueError) as e:
                return self._respond(503, {"error": "Local catalog unavailable", "detail": str(e)[:120]})
            return self._respond(200, data)
        return self._respond(404, {"error": "Not found"})

    def do_POST(self):
        path = urlsplit(self.path).path
        if not self._origin_ok():
            return self._respond(403, {"error": "Same-origin browser request required"})
        if path == "/login":
            if time.monotonic() < self.server.blocked_until:
                return self._respond(429, {"error": "Too many attempts; wait and retry"})
            try:
                if self.headers.get("Content-Type", "").split(";")[0] != "application/x-www-form-urlencoded":
                    raise ValueError("Expected form")
                params = parse_qs(self._payload().decode("utf-8"), keep_blank_values=True)
                candidate = params.get("code", [""])[0]
            except (ValueError, UnicodeError):
                return self._respond(400, {"error": "Invalid sign-in request"})
            if not hmac.compare_digest(candidate, self.server.pairing_code):
                self.server.failures += 1
                if self.server.failures >= 5:
                    self.server.blocked_until = time.monotonic() + 60
                    self.server.failures = 0
                return self._respond(401, {"error": "Incorrect pairing code"})
            self.server.failures = 0
            token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(24)
            self.server.sessions = {k: v for k, v in self.server.sessions.items() if v["expires"] > time.monotonic()}
            if len(self.server.sessions) >= 8:
                self.server.sessions.clear()
            self.server.sessions[hashlib.sha256(token.encode()).hexdigest()] = {"csrf": csrf, "expires": time.monotonic() + SESSION_SECONDS}
            return self._redirect("/private", {"Set-Cookie": "toad_session=" + token + "; Path=/; Max-Age=14400; HttpOnly; Secure; SameSite=Strict"})
        if path != "/api/feed":
            return self._respond(404, {"error": "Not found"})
        session = self._session()
        if not session:
            return self._respond(401, {"error": "Sign in"})
        if not hmac.compare_digest(self.headers.get("X-Toad-CSRF", ""), session["csrf"]):
            return self._respond(403, {"error": "Invalid request token"})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self._respond(415, {"error": "Expected JSON"})
        try:
            data = json.loads(self._payload())
            if not isinstance(data, dict) or not isinstance(data.get("content"), str):
                raise ValueError("Content must be text")
            if len(data["content"].encode("utf-8")) > MAX_PACKAGE_BYTES:
                raise ValueError("Content too large")
            if data.get("name") is not None and (not isinstance(data["name"], str) or len(data["name"]) > 100):
                raise ValueError("Invalid name")
            engine = Engine(self.server.workspace)
            try:
                options = {"source": "private-phone-bridge"}
                if data.get("name"):
                    options["name"] = data["name"]
                result = engine.ingest_text(data["content"], **options)
                engine.inspect(result["id"])
                saved = engine.get(result["id"])
            finally:
                engine.close()
            return self._respond(201, {"id": saved["id"], "status": saved["status"], "name": saved["name"], "received": True, "executed": False})
        except (ValueError, OSError, TypeError) as e:
            return self._respond(400, {"error": str(e)[:180]})


def serve(workspace=None, port=8765, *, pairing_code=None):
    """Starts a local-only HTTP service. HTTPS must terminate at trusted private ingress."""
    server = BridgeHTTP(("127.0.0.1", port), workspace=workspace, pairing_code=pairing_code)
    try:
        print("Toad private bridge listening on 127.0.0.1:" + str(server.server_port), flush=True)
        print("Pairing code (keep private): " + server.pairing_code, flush=True)
        print("For iPhone, use a private HTTPS reverse proxy such as Tailscale Serve (never Funnel).", flush=True)
        server.serve_forever()
    finally:
        server.server_close()
