"""Free build mode tests. No model calls, network access or deployment."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from toad_core.app_studio import AppStudio
from toad_core.free_builder import build_from_brief, interpret_brief
from toad_core.schema import PackageError


class FreeAppBuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name) / "toad-workspace"

    def tearDown(self):
        self.tmp.cleanup()

    def test_recognizes_supported_types_without_inference(self):
        cases = [
            ("Make an offline flashcard app for vocabulary", "flashcards"),
            ("I need a deck of flash cards", "flashcards"),
            ("Build a to-do list for college", "tasks"),
            ("Create a checklist of assignments", "tasks"),
            ("Make a notebook to save study ideas", "notes"),
            ("Create a private journal app", "notes"),
        ]
        for brief, kind in cases:
            with self.subTest(brief=brief):
                selected = interpret_brief(brief)
                self.assertEqual(selected["kind"], kind)
                self.assertFalse(selected["model_called"])
                self.assertEqual(selected["paid_requests"], 0)
                self.assertFalse(selected["supports_arbitrary_code"])

    def test_unsupported_or_ambiguous_requests_fail_without_output(self):
        cases = [
            "",
            "Make a beautiful app",
            "Make an app for tasks and notes",
            "Make a flashcard app with cloud sync",
            "Make a flashcard app with accounts",
            "Make a quiz app with automatic grading",
            "Make an AI powered flashcards app",
            "Make flashcards with spaced repetition",
            "Make notes and export as PDF",
            "Make a flashcard app with a camera",
            "Make tasks with multiplayer collaboration",
            "a" * 1201,
            "Flashcards\nPlease",
            42,
        ]
        for index, brief in enumerate(cases):
            with self.subTest(brief=str(brief)[:80]):
                with self.assertRaises(PackageError):
                    build_from_brief(self.workspace, brief, name="unwanted-"+str(index))
        root = self.workspace / "app-previews"
        self.assertFalse(root.exists())

    def test_builds_three_independent_templates_with_distinct_storage(self):
        result = build_from_brief(
            self.workspace, "Please make offline flashcards",
            name="my-study-cards", title="My Study Cards", theme="midnight"
        )
        app = result["app"]
        self.assertEqual(result["selection"]["kind"], "flashcards")
        self.assertFalse(result["model_called"])
        self.assertEqual(result["paid_requests"], 0)
        self.assertFalse(result["deployed"])
        self.assertEqual(app["template"], "trusted-offline-flashcards-v1")
        self.assertEqual(app["status"], "generated_unverified")
        folder = Path(app["folder"])
        self.assertIn("My Study Cards", (folder / "index.html").read_text())
        self.assertIn('data-theme="midnight"', (folder / "index.html").read_text())
        self.assertIn("toad-sage-flashcards-v1:my-study-cards", (folder / "app.js").read_text())
        self.assertIn("Flip card", (folder / "app.js").read_text() + (folder / "index.html").read_text())
        self.assertIn("flashcards", (folder / "README.md").read_text())
        self.assertTrue(Path(app["zip"]).is_file())
        self.assertEqual(AppStudio(self.workspace).inspect("my-study-cards")["status"], "source_intact_unverified")

        notes = build_from_brief(self.workspace, "A notes app", name="my-notes")
        tasks = build_from_brief(self.workspace, "A task list", name="my-tasks")
        self.assertEqual(notes["app"]["kind"], "notes")
        self.assertEqual(tasks["app"]["kind"], "tasks")
        self.assertIn("toad-sage-notes-v1:my-notes", (Path(notes["app"]["folder"])/"app.js").read_text())
        self.assertIn("toad-sage-tasks-v1:my-tasks", (Path(tasks["app"]["folder"])/"app.js").read_text())
        self.assertNotEqual(app["zip_sha256"], notes["app"]["zip_sha256"])
        with self.assertRaisesRegex(PackageError, "already exists"):
            build_from_brief(self.workspace, "Flashcards", name="my-study-cards")

    def test_cli_free_build_creates_reviewable_local_zip(self):
        command = [
            sys.executable, "-m", "toad_core", "--workspace", str(self.workspace),
            "app", "free-build", "Make an offline flashcard deck for studying",
            "--name", "study-terms", "--title", "Study Terms", "--theme", "forest"
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out["selection"]["kind"], "flashcards")
        self.assertEqual(out["paid_requests"], 0)
        self.assertFalse(out["deployed"])
        report = out["app"]
        self.assertTrue(Path(report["zip"]).is_file())
        self.assertEqual(
            json.loads(subprocess.run(
                [sys.executable, "-m", "toad_core", "--workspace", str(self.workspace),
                 "app", "inspect", "study-terms"],
                capture_output=True, text=True, timeout=10
            ).stdout)["status"], "source_intact_unverified"
        )


if __name__ == "__main__":
    unittest.main()
