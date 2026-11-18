"""Trusted App Studio regression tests; no Ollama/Docker/candidate execution."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from toad_core.app_studio import AppStudio
from toad_core.schema import PackageError


class AppStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.studio = AppStudio(self.root / "private")

    def tearDown(self):
        self.temp.cleanup()

    def test_builds_real_offline_source_bundle_with_no_claim_of_ai_or_deployment(self):
        report = self.studio.create("my-tasks", title="My Tasks", theme="midnight")
        folder = Path(report["folder"])
        self.assertEqual(report["status"], "generated_unverified")
        self.assertFalse(report["deployed"])
        self.assertFalse(report["sandbox_executed"])
        self.assertFalse(report["model_generated"])
        self.assertTrue(report["requires_owner_review"])
        for file in ("index.html", "app.js", "styles.css", "README.md", "build_report.json", "app.zip"):
            self.assertTrue((folder / file).is_file(), file)
        html = (folder / "index.html").read_text()
        self.assertIn("<title>My Tasks</title>", html)
        self.assertIn('data-theme="midnight"', html)
        self.assertIn("Content-Security-Policy", html)
        self.assertNotIn("https://", html)
        self.assertEqual(self.studio.inspect("my-tasks")["status"], "source_intact_unverified")
        self.assertEqual(hashlib.sha256((folder / "app.zip").read_bytes()).hexdigest(), report["zip_sha256"])
        with zipfile.ZipFile(folder / "app.zip") as archive:
            self.assertEqual(sorted(archive.namelist()), sorted(["index.html", "app.js", "styles.css", "README.md", "build_report.json"]))
            saved = json.loads(archive.read("build_report.json"))
            self.assertEqual(saved["schema"], "toad-app-build-v1")
            self.assertEqual(saved["files_sha256"]["app.js"], hashlib.sha256(archive.read("app.js")).hexdigest())

    def test_title_is_html_escaped(self):
        injected = '</title><script>alert("x")</script>'
        build = self.studio.create("safe-title", title=injected)
        html = (Path(build["folder"]) / "index.html").read_text()
        self.assertNotIn(injected, html)
        self.assertIn("&lt;/title&gt;", html)
        self.assertIn("&lt;script&gt;", html)

    def test_input_validation_refuses_traversal_overlong_and_controls(self):
        for name in ("../oops", "/private", "A", "a", "bad_slug", "bad/name", "a"*41):
            with self.subTest(name=name), self.assertRaises(PackageError):
                self.studio.create(name)
        for title in ("", "x"*81, "bad\nname", "bad\x00name", "\ud800"):
            with self.subTest(title=repr(title)), self.assertRaises(PackageError):
                self.studio.create("safe-app", title=title)
        with self.assertRaises(PackageError):
            self.studio.create("safe-app", theme="../evil")
        self.assertFalse((self.root / "private" / "app-previews" / "safe-app").exists())

    def test_cannot_overwrite_existing_build_or_follow_output_parent_symlink(self):
        self.studio.create("my-tasks")
        with self.assertRaises(PackageError):
            self.studio.create("my-tasks", title="Overwrite attempt")
        if hasattr(Path, "symlink_to"):
            other = self.root / "other"
            other.mkdir()
            linked = self.root / "linked"
            try:
                linked.symlink_to(other, target_is_directory=True)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(PackageError):
                AppStudio(linked).create("other-app")

    def test_inspection_detects_changed_and_symlinked_files(self):
        build = self.studio.create("my-tasks")
        file = Path(build["folder"]) / "app.js"
        file.write_text("modified\n")
        report = self.studio.inspect("my-tasks")
        self.assertEqual(report["status"], "source_modified")
        self.assertFalse(report["files"]["app.js"])
        self.assertFalse(report["browser_tested_this_build"])
        self.assertTrue(report["requires_owner_review"])

    def test_cli_creates_and_inspects_without_model_or_worker(self):
        base = self.root / "cli"
        def call(*args):
            return subprocess.run(
                [sys.executable, "-m", "toad_core", "--workspace", str(base), *args],
                capture_output=True, text=True, timeout=10,
            )
        created = call("app", "create", "daily-plan", "--title", "Daily Plan")
        self.assertEqual(created.returncode, 0, created.stderr)
        payload = json.loads(created.stdout)
        self.assertEqual(payload["status"], "generated_unverified")
        integrity = call("app", "inspect", "daily-plan")
        self.assertEqual(integrity.returncode, 0, integrity.stderr)
        self.assertEqual(json.loads(integrity.stdout)["status"], "source_intact_unverified")
        again = call("app", "create", "daily-plan")
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("already exists", json.loads(again.stderr)["error"])


if __name__ == "__main__":
    unittest.main()
