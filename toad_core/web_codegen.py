"""Quarantined AI-authored static web source — DATA ONLY, never runnable here.

The existing Ollama adapter may propose HTML/CSS/JS. This module validates
a small manifest and stores raw strings in a private JSON record. It does NOT
extract files, render a preview, invoke a browser, install or deploy anything.
A future independent JavaScript worker and human release gate are required.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from .app_studio import _validate_name, _validate_title
from .models import ModelError, OllamaAdapter
from .schema import PackageError, json_bytes, strict_json

SCHEMA = "toad-web-source-draft-v1"
RECORD_SCHEMA = "toad-web-draft-record-v1"
SOURCE_NAMES = ("index.html", "styles.css", "app.js")
REQUIRED_KEYS = frozenset(("schema", "name", "title", "files", "declared_features"))
SOURCE_CAP = 64000
TOTAL_CAP = 180000
MAX_REQUEST_BYTES = 2500
MAX_RECORDS = 100

PATTERNS = (
    ("network_or_remote_resource", re.compile(r"https?://|\bfetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon|EventSource", re.I)),
    ("dynamic_code_execution", re.compile(r"\beval\s*\(|new\s+Function\s*\(|\bFunction\s*\(", re.I)),
    ("html_injection_or_dynamic_markup", re.compile(r"\.innerHTML\s*=|\.outerHTML\s*=|document\.write\s*\(", re.I)),
    ("sensitive_browser_api", re.compile(r"document\.cookie|navigator\.serviceWorker|indexedDB|\bwindow\.open\s*\(", re.I)),
    ("inline_script", re.compile(r"<script\b(?![^>]*\bsrc\s*=)", re.I)),
)


def _digest(data):
    return hashlib.sha256(json_bytes(data)).hexdigest()


def validate_web_source(value):
    """Accept exactly three bounded text files, preserving them as inert data."""
    if not isinstance(value, dict) or set(value) != REQUIRED_KEYS:
        raise PackageError("Web source draft has unknown fields, missing fields or injected permissions")
    if value["schema"] != SCHEMA:
        raise PackageError("Unsupported web source draft schema")
    name = _validate_name(value["name"])
    title = _validate_title(value["title"])
    raw_files = value["files"]
    if not isinstance(raw_files, list) or len(raw_files) != len(SOURCE_NAMES):
        raise PackageError("Source draft requires exactly index.html, styles.css and app.js")
    mapping = {}
    for file in raw_files:
        if not isinstance(file, dict) or set(file) != {"path", "content"}:
            raise PackageError("Each source entry must have only path and content")
        path, content = file["path"], file["content"]
        if not isinstance(path, str) or path not in SOURCE_NAMES or path in mapping:
            raise PackageError("Unsupported, duplicated or unsafe source file path")
        if not isinstance(content, str) or not content.strip() or "\x00" in content:
            raise PackageError("Source file must contain nonempty plain UTF-8 text")
        try:
            encoded = content.encode("utf-8")
        except UnicodeError as exc:
            raise PackageError("Invalid UTF-8 source") from exc
        if len(encoded) > SOURCE_CAP:
            raise PackageError("Source file exceeds 64 KB limit")
        mapping[path] = content
    if set(mapping) != set(SOURCE_NAMES):
        raise PackageError("Missing source files")
    features = value["declared_features"]
    if not isinstance(features, list) or len(features) > 8:
        raise PackageError("Feature declarations must be a list of at most eight strings")
    feature_names = []
    for feature in features:
        if not isinstance(feature, str) or not feature.strip() or len(feature) > 120:
            raise PackageError("Invalid declared feature")
        if any(ord(c) < 32 or ord(c) == 127 for c in feature):
            raise PackageError("Feature declarations must be single-line text")
        feature_names.append(feature.strip())
    if len(set(feature_names)) != len(feature_names):
        raise PackageError("Duplicate declared feature")
    output = {
        "schema": SCHEMA,
        "name": name,
        "title": title,
        "files": [{"path": path, "content": mapping[path]} for path in SOURCE_NAMES],
        "declared_features": feature_names,
    }
    if len(json_bytes(output)) > TOTAL_CAP:
        raise PackageError("Total source draft exceeds manifest size limit")
    return output


def scan_strings_only(source):
    """Heuristics, never a security certificate. No parse/eval/execute."""
    all_text = "\n".join(file["content"] for file in source["files"])
    observations = [name for name, pattern in PATTERNS if pattern.search(all_text)]
    if "<script" in all_text.lower() and "app.js" not in all_text.lower():
        observations.append("nonstandard_script_reference")
    return sorted(set(observations))


class QuarantinedWebGenerator:
    def __init__(self, workspace, *, model=None):
        self.workspace = Path(workspace)
        self.model = model

    def _root(self, create=False):
        if self.workspace.is_symlink():
            raise PackageError("Workspace cannot be a symlink")
        root = self.workspace / "ai-web-drafts"
        if root.is_symlink():
            raise PackageError("Quarantine directory cannot be a symlink")
        if create:
            root.mkdir(parents=True, mode=0o700, exist_ok=True)
        return root

    def propose(self, request):
        if not isinstance(request, str) or not request.strip():
            raise PackageError("App request must not be empty")
        try:
            request_bytes = len(request.encode("utf-8"))
        except UnicodeError as exc:
            raise PackageError("App request must be UTF-8 text") from exc
        if not 1 <= request_bytes <= MAX_REQUEST_BYTES or "\x00" in request:
            raise PackageError("App request must be 1-2500 UTF-8 bytes without NUL")
        root = self._root(create=True)
        if sum(1 for _ in root.glob("*.json")) >= MAX_RECORDS:
            raise PackageError("Quarantine is at capacity; archive reviewed drafts offline first")
        task = {
            "request": request.strip(),
            "task": "Propose exactly three static website source files for owner review, not execution",
            "schema": {
                "schema": SCHEMA,
                "name": "lowercase hyphenated app slug",
                "title": "visible app title",
                "files": [
                    {"path": "index.html", "content": "full UTF-8 HTML document"},
                    {"path": "styles.css", "content": "full CSS text"},
                    {"path": "app.js", "content": "full browser JS text"},
                ],
                "declared_features": ["short feature name"],
            },
            "constraints": [
                "Only static HTML/CSS/JS: no backend, network requests or third-party dependencies.",
                "Use content security policy, DOM textContent for user text, and localStorage only for non-sensitive demo data.",
                "Never include secrets, API tokens, data about people or hardware operations.",
                "No external scripts, imports, CDN resources, service workers, iframes or external endpoints.",
                "Return JSON only. Do not claim it passed tests or was deployed.",
            ],
            "warning": "All produced source will be quarantined and unexecuted; any unsafe behavior will require independent review.",
        }
        adapter = self.model if self.model is not None else OllamaAdapter()
        proposed = adapter.generate_json(
            json.dumps(task, ensure_ascii=False),
            purpose="draft untrusted static web app source for quarantine, not execution",
        )
        if isinstance(proposed, dict) and "error" in proposed:
            raise ModelError("Model could not draft the requested app: " + str(proposed["error"])[:160])
        draft = validate_web_source(proposed)
        identifier = uuid.uuid4().hex
        hashes = {
            file["path"]: hashlib.sha256(file["content"].encode("utf-8")).hexdigest()
            for file in draft["files"]
        }
        flags = scan_strings_only(draft)
        record = {
            "schema": RECORD_SCHEMA,
            "id": identifier,
            "request": request.strip(),
            "draft": draft,
            "draft_sha256": _digest(draft),
            "file_sha256": hashes,
            "risk_flags": flags,
            "source": "loopback_ollama" if self.model is None else "injected_model_adapter",
            "status": "quarantined_unverified",
            "model_authored_code": True,
            "executed": False,
            "tested": False,
            "installed": False,
            "deployed": False,
            "owner_review_required": True,
            "release_allowed": False,
            "blocking_requirement": "Independent isolated JavaScript tests and source review not yet implemented",
        }
        path = root / (identifier + ".json")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as writer:
            json.dump(record, writer, indent=2, ensure_ascii=False)
            writer.write("\n")
        return self.review(identifier)

    def _record(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise PackageError("Invalid draft ID")
        path = self._root() / (identifier + ".json")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > TOTAL_CAP + 12000:
            raise PackageError("Draft missing, linked or oversized")
        record = strict_json(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict) or record.get("schema") != RECORD_SCHEMA or record.get("id") != identifier:
            raise PackageError("Invalid stored draft record")
        draft = validate_web_source(record.get("draft"))
        if record.get("draft_sha256") != _digest(draft):
            raise PackageError("Stored source digest mismatch")
        expected = {file["path"]: hashlib.sha256(file["content"].encode("utf-8")).hexdigest() for file in draft["files"]}
        if record.get("file_sha256") != expected:
            raise PackageError("Stored file digest mismatch")
        return record

    def review(self, identifier):
        """Only metadata and hashes; raw JS never escapes into executable context."""
        record = self._record(identifier)
        return {key: record[key] for key in (
            "id", "status", "draft_sha256", "file_sha256", "risk_flags",
            "source", "model_authored_code", "executed", "tested",
            "installed", "deployed", "owner_review_required",
            "release_allowed", "blocking_requirement",
        )}

    def show(self, identifier):
        """Explicit source review; still returns JSON data, never executes it."""
        record = self._record(identifier)
        return {
            "id": identifier,
            "status": record["status"],
            "draft": record["draft"],
            "risk_flags": record["risk_flags"],
            "executed": False,
            "release_allowed": False,
            "requires_independent_javascript_worker": True,
        }
