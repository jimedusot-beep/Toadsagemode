"""Trusted, deterministic app builder. No model call or candidate execution.

This is a small reviewable application scaffold, NOT an autonomous generator.
Web assets are packaged with this trusted Python module and are exercised by
separate browser CI. The current Docker worker still handles Python only.
"""
from __future__ import annotations

import hashlib
import html
from importlib.resources import files
import json
import os
from pathlib import Path
import re
import shutil
import zipfile

from .schema import PackageError, strict_json


NAME = re.compile(r"[a-z][a-z0-9-]{1,39}\Z")
THEMES = ("forest", "midnight")
APP_KINDS = ("tasks", "notes")
SOURCE_FILES = ("index.html", "styles.css", "app.js", "README.md")
REPORT = "build_report.json"
TEMPLATES = "toad_core.studio_templates"


def _validate_name(name):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise PackageError("App name must be 2–40 lowercase letters, digits or hyphens and begin with a letter")
    return name


def _validate_title(title):
    if not isinstance(title, str) or not title.strip() or len(title) > 80:
        raise PackageError("App title must contain 1–80 characters")
    clean = title.strip()
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in clean):
        raise PackageError("App title cannot contain control characters")
    try:
        clean.encode("utf-8")
    except UnicodeError as exc:
        raise PackageError("App title must be UTF-8 text") from exc
    return clean


class AppStudio:
    """Scaffold and inspect reviewed template output within a private workspace."""

    def __init__(self, workspace):
        self.workspace = Path(workspace)

    def _root(self, *, create=False):
        if self.workspace.is_symlink():
            raise PackageError("Workspace cannot be a symlink")
        root = self.workspace / "app-previews"
        if root.is_symlink():
            raise PackageError("App output parent cannot be a symlink")
        if create:
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
        return root

    @staticmethod
    def _templates(name, title, theme, kind):
        template = files(TEMPLATES)
        is_notes = kind == "notes"
        page = "notes.html" if is_notes else "tasks.html"
        script = "notes.js" if is_notes else "app.js"
        base_js = template.joinpath(script).read_text(encoding="utf-8")
        # The slug comes from a strict allowlist, not from untrusted JS.
        storage_key = "toad-sage-" + kind + "-v1:" + name
        if is_notes:
            base_js = base_js.replace("{{STORAGE_KEY}}", storage_key)
        else:
            original = "const KEY = 'toad-sage-task-list-v1';"
            if original not in base_js:
                raise PackageError("Trusted task storage-key anchor is missing")
            base_js = base_js.replace(original, "const KEY = '" + storage_key + "';")
        css = template.joinpath("styles.css").read_text(encoding="utf-8")
        if is_notes:
            css += template.joinpath("notes.css").read_text(encoding="utf-8")
        return {
            "index.html": template.joinpath(page).read_text(encoding="utf-8")
                .replace("{{TITLE}}", html.escape(title, quote=True))
                .replace("{{THEME}}", theme),
            "styles.css": css,
            "app.js": base_js,
            "README.md": (
                "# Offline " + kind + " application\n\n"
                "Built from a reviewed, versioned Toad Sage " + kind + " template.\n"
                "A browser stores this app's data locally under a distinct key.\n"
                "The notes app supports create/edit/search/delete; the tasks app supports "
                "create/toggle/filter/delete/clear completed.\n"
                "Use a trusted local static server or Netlify preview for browser storage.\n"
                "Browser storage is not an encrypted backup or cross-device sync.\n"
                "Do not put secrets or client medical data into this demo.\n"
                "Review source and browser tests before any deployment.\n"
                "No AI-authored executable source, Docker execution, installation or "
                "deployment occurred during this build.\n"
            ),
        }

    def create(self, name, *, title=None, theme="forest", kind="tasks"):
        name = _validate_name(name)
        title = _validate_title(title if title is not None else name.replace("-", " ").title())
        if theme not in THEMES:
            raise PackageError("Theme must be forest or midnight")
        if kind not in APP_KINDS:
            raise PackageError("Supported app kinds are tasks or notes")
        parent = self._root(create=True)
        destination = parent / name
        if destination.exists() or destination.is_symlink():
            raise PackageError("App already exists; do not overwrite a reviewable build")

        # mkdir fails if a directory or symlink appears concurrently.
        destination.mkdir(mode=0o700, exist_ok=False)
        try:
            payloads = self._templates(name, title, theme, kind)
            hashes = {}
            for path in SOURCE_FILES:
                body = payloads[path].encode("utf-8")
                hashes[path] = hashlib.sha256(body).hexdigest()
                with (destination / path).open("xb") as writer:
                    writer.write(body)
            report = {
                "schema": "toad-app-build-v1",
                "name": name,
                "title": title,
                "theme": theme,
                "template": "trusted-offline-" + kind + "-v1",
                "kind": kind,
                "status": "generated_unverified",
                "files_sha256": hashes,
                "test_evidence": "none_for_this_build",
                "requires_owner_review": True,
                "deployed": False,
                "model_generated": False,
                "sandbox_executed": False,
            }
            with (destination / REPORT).open("x", encoding="utf-8") as writer:
                json.dump(report, writer, indent=2, ensure_ascii=False)
                writer.write("\n")
            archive_path = destination / "app.zip"
            with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in (*SOURCE_FILES, REPORT):
                    archive.write(destination / path, path)
            report["zip_sha256"] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            report["folder"] = str(destination)
            report["zip"] = str(archive_path)
            return report
        except BaseException:
            shutil.rmtree(destination)
            raise

    def inspect(self, name):
        name = _validate_name(name)
        root = self._root()
        folder = root / name
        if folder.is_symlink() or not folder.is_dir():
            raise PackageError("App folder missing or linked elsewhere")
        report_path = folder / REPORT
        if report_path.is_symlink() or not report_path.is_file() or report_path.stat().st_size > 10000:
            raise PackageError("Missing or invalid build report")
        report = strict_json(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or report.get("schema") != "toad-app-build-v1" or report.get("name") != name:
            raise PackageError("Unsupported or mismatched build report")
        expected = report.get("files_sha256")
        if not isinstance(expected, dict) or set(expected) != set(SOURCE_FILES):
            raise PackageError("Missing source hashes")
        checks = {}
        for path in SOURCE_FILES:
            source = folder / path
            if source.is_symlink() or not source.is_file() or source.stat().st_size > 150000:
                checks[path] = False
                continue
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            checks[path] = digest == expected[path]
        return {
            "name": name,
            "status": "source_intact_unverified" if all(checks.values()) else "source_modified",
            "files": checks,
            "requires_owner_review": True,
            "deployed": False,
            "browser_tested_this_build": False,
        }
