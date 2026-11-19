"""AI app-planner tests. Deliberate model doubles: NO live model or deployment."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from toad_core.app_planner import AIAppPlanner, validate_blueprint
from toad_core.app_studio import AppStudio
from toad_core.models import ModelError
from toad_core.schema import PackageError


BLUEPRINT = {
    "schema": "toad-app-blueprint-v1",
    "name": "study-journal",
    "title": "Study Journal",
    "kind": "notes",
    "theme": "midnight",
    "summary": "Offline searchable notes for study sessions, without cloud sync.",
    "unmet_requirements": [],
}


class ModelDouble:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate_json(self, prompt, **options):
        self.calls.append((json.loads(prompt), options))
        if isinstance(self.response, Exception):
            raise self.response
        return copy.deepcopy(self.response)


class AIAppPlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name) / "private"

    def tearDown(self):
        self.temp.cleanup()

    def planner(self, response=None):
        model = ModelDouble(BLUEPRINT if response is None else response)
        return AIAppPlanner(self.workspace, model=model), model

    def test_propose_persists_untrusted_data_but_never_builds(self):
        planner, model = self.planner()
        result = planner.propose("Make an offline journal where I can search notes")
        self.assertEqual(result["status"], "awaiting_review")
        self.assertTrue(result["requires_human_approval"])
        self.assertFalse(result["deployed"])
        self.assertEqual(result["blueprint"]["kind"], "notes")
        self.assertEqual(len(model.calls), 1)
        self.assertIn("offline journal", model.calls[0][0]["goal"])
        self.assertEqual(model.calls[0][1]["purpose"], "propose an offline app blueprint selecting only trusted templates")
        self.assertFalse((self.workspace / "app-previews").exists())
        record = planner.show(result["id"])
        self.assertEqual(record["status"], "awaiting_review")
        self.assertEqual(record["blueprint"]["title"], "Study Journal")
        self.assertEqual(record["test_evidence"], "none")

    def test_build_requires_approval_and_source_is_not_model_written(self):
        planner, model = self.planner()
        p = planner.propose("Searchable offline notebook")
        with self.assertRaisesRegex(PackageError, "Human review"):
            planner.build(p["id"])
        self.assertFalse((self.workspace / "app-previews").exists())
        built = planner.build(p["id"], approve=True)
        self.assertTrue(built["approval_recorded"])
        self.assertFalse(built["model_wrote_executable_code"])
        self.assertFalse(built["deployed"])
        self.assertTrue(built["review_required_before_deploy"])
        app = built["app"]
        self.assertEqual(app["template"], "trusted-offline-notes-v1")
        self.assertEqual(app["status"], "generated_unverified")
        folder = Path(app["folder"])
        self.assertIn("Study Journal", (folder / "index.html").read_text())
        self.assertIn("toad-sage-notes-v1:study-journal", (folder / "app.js").read_text())
        self.assertEqual(AppStudio(self.workspace).inspect("study-journal")["status"], "source_intact_unverified")
        with self.assertRaisesRegex(PackageError, "already exists"):
            planner.build(p["id"], approve=True)

    def test_unmet_requirements_need_additional_explicit_approval(self):
        partial = {**BLUEPRINT, "unmet_requirements": ["Cloud sync requires a server and account system"]}
        planner, _ = self.planner(partial)
        p = planner.propose("Make my notes sync between my phones")
        with self.assertRaisesRegex(PackageError, "unmet requirements"):
            planner.build(p["id"], approve=True)
        result = planner.build(p["id"], approve=True, allow_partial=True)
        self.assertIn("Cloud sync", result["unmet_requirements"][0])
        self.assertFalse(result["deployed"])

    def test_malformed_or_privilege_expanding_proposals_never_save(self):
        cases = [
            {**BLUEPRINT, "kind": "server"},
            {**BLUEPRINT, "theme": "unknown"},
            {**BLUEPRINT, "name": "../escape"},
            {**BLUEPRINT, "title": "<bad>\n"},
            {**BLUEPRINT, "javascript": "eval('oops')"},
            {**BLUEPRINT, "unmet_requirements": ["x"] * 6},
            {**BLUEPRINT, "unmet_requirements": [False]},
            {**BLUEPRINT, "summary": ""},
        ]
        for proposal in cases:
            with self.subTest(case=proposal):
                planner, _ = self.planner(proposal)
                with self.assertRaises(PackageError):
                    planner.propose("Build me a notes app")
        self.assertFalse((self.workspace / "app-plans").exists())

    def test_goal_and_model_failures_are_bounded(self):
        planner, model = self.planner(ModelError("Model unavailable"))
        for goal in ("", "a" * 2001, "test\x00bad"):
            with self.subTest(goal=repr(goal)), self.assertRaises(PackageError):
                planner.propose(goal)
        with self.assertRaises(ModelError):
            planner.propose("Build an offline notebook")
        self.assertEqual(len(model.calls), 1)
        with self.assertRaises(ModelError):
            self.planner({"error": "Only unsupported capabilities requested"})[0].propose("Build a cloud service")
        self.assertFalse((self.workspace / "app-plans").exists())

    def test_plan_tampering_is_detected_before_build(self):
        planner, _ = self.planner()
        p = planner.propose("Build a notes app")
        file = Path(p["path"])
        data = json.loads(file.read_text())
        data["blueprint"]["name"] = "tampered-name"
        file.write_text(json.dumps(data))
        with self.assertRaisesRegex(PackageError, "hash mismatch"):
            planner.show(p["id"])
        with self.assertRaises(PackageError):
            planner.build(p["id"], approve=True)
        self.assertFalse((self.workspace / "app-previews").exists())

    def test_kind_and_storage_are_isolated_across_generated_apps(self):
        s = AppStudio(self.workspace)
        first = s.create("daily-plan", title="Tasks")
        second = s.create("my-notes", title="Notes", kind="notes")
        third = s.create("another-task", title="Another task app")
        one = (Path(first["folder"]) / "app.js").read_text()
        two = (Path(second["folder"]) / "app.js").read_text()
        three = (Path(third["folder"]) / "app.js").read_text()
        self.assertIn("toad-sage-tasks-v1:daily-plan", one)
        self.assertIn("toad-sage-notes-v1:my-notes", two)
        self.assertIn("toad-sage-tasks-v1:another-task", three)
        self.assertNotEqual(one, three)
        for result in (first, second, third):
            self.assertEqual(result["status"], "generated_unverified")
            self.assertFalse(result["deployed"])

    def test_unknown_or_symlink_plan_rejected(self):
        planner, _ = self.planner()
        with self.assertRaises(PackageError):
            planner.show("../../etc/passwd")
        with self.assertRaises(PackageError):
            planner.show("a" * 32)
        p = planner.propose("Make notes")
        path = Path(p["path"])
        path.unlink()
        try:
            path.symlink_to(Path(self.temp.name) / "not-here")
        except (OSError, NotImplementedError):
            return
        with self.assertRaises(PackageError):
            planner.show(p["id"])

    def test_cli_notes_create_and_explicit_build_rejection(self):
        def call(*args):
            return subprocess.run([
                sys.executable, "-m", "toad_core", "--workspace", str(self.workspace),
                *args
            ], capture_output=True, text=True, timeout=10)
        r = call("app", "create", "lab-notes", "--kind", "notes", "--title", "Lab Notes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["kind"], "notes")
        r = call("app", "build", "f" * 32)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(json.loads(r.stderr)["ok"])
        r = call("app", "plan", "f" * 32)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
