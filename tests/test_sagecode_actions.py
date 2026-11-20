"""ControlledAgent's restricted SageCode action bridge: source-only tests."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from toad_core.project_tools import SageProjectTools
from toad_core.sagecode_actions import SageProjectActionAdapter, PROJECT_ACTIONS
from toad_core.schema import PackageError, normalize_package, package_digest


def source_package():
    return {"schema": "toad-ability-v2", "name": "source-demo", "version": "0.1.0",
            "entrypoint": "src/main.py", "permissions": [], "dependencies": [], "tests": [],
            "files": [{"path": "src/main.py", "content": "print('hello')\n"},
                      {"path": "README.md", "content": "# Source demo\n"}]}


class FakeEngine:
    def __init__(self, workspace, manifest):
        self.store = SimpleNamespace(workspace=Path(workspace))
        self.source = {"manifest": manifest, "digest": package_digest(manifest)}

    def get(self, candidate_id):
        if candidate_id != "candidate-1":
            raise PackageError("Not an allowed candidate")
        return self.source


class SageCodeActionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        self.manifest = normalize_package(source_package())
        self.engine = FakeEngine(self.workspace, self.manifest)
        self.project = SageProjectTools.create(self.workspace, "source-demo", self.manifest,
                                                allowed_project_ids={"source-demo"})
        self.adapter = SageProjectActionAdapter(self.engine, "candidate-1", self.project)
        self.baseline = self.project.status()["revision"]

    def test_binding_is_bound_to_trusted_project_and_candidate(self):
        self.assertEqual(self.adapter.binding["candidate_id"], "candidate-1")
        self.assertEqual(self.adapter.binding["project_id"], "source-demo")
        self.assertEqual(self.adapter.binding["baseline_revision"], self.baseline)
        self.assertEqual(len(PROJECT_ACTIONS), 5)
        self.assertEqual(self.adapter.status()["verification"], "unverified")

    def test_lists_searches_and_reads_without_claiming_execution(self):
        for action in ({"action": "project_status"}, {"action": "project_tree"},
                       {"action": "project_search", "term": "hello"},
                       {"action": "project_read", "path": "src/main.py"}):
            result = self.adapter.execute(action)
            self.assertEqual(result["project_id"], "source-demo")
            self.assertFalse(result["executed"])
            self.assertFalse(result["approved"])
            self.assertFalse(result["release_allowed"])
        self.assertEqual(self.adapter.execute({"action": "project_read", "path": "src/main.py"})["content"], "print('hello')\n")
        self.assertEqual(self.adapter.execute({"action": "project_search", "term": "hello"})["matches"][0]["kind"], "content")

    def test_proposed_edit_is_unverified_and_preserves_original_candidate(self):
        before = copy.deepcopy(self.engine.get("candidate-1"))
        response = self.adapter.execute({"action": "project_propose_edit", "path": "src/main.py", "content": "print('edited')\n", "expected_revision": self.baseline})
        self.assertIn("+print('edited')", response["diff"])
        self.assertEqual(response["verification"], "unverified")
        self.assertTrue(response["source_only"])
        self.assertNotEqual(response["revision"], self.baseline)
        self.assertEqual(self.engine.get("candidate-1"), before)
        self.assertFalse(self.adapter.status()["release_allowed"])

    def test_rejects_unapproved_parameters_and_tool_names(self):
        for action in ({"action": "project_read", "path": "README.md", "command": "whoami"},
                       {"action": "project_propose_edit", "path": "README.md", "content": "bad", "expected_revision": self.baseline, "permission": "write"},
                       {"action": "project_restore", "revision": self.baseline},
                       {"action": "shell", "command": "rm -rf ."},
                       {"action": "project_read", "path": "../etc/passwd"},
                       {"action": "project_status", "project_id": "other"},
                       {"action": "project_propose_edit", "path": "src/main.py"},
                       {"action": "project_search", "term": "\ud800"}):
            with self.subTest(action=repr(action)):
                with self.assertRaises(PackageError):
                    self.adapter.execute(action)
        self.assertEqual(self.adapter.status()["revision"], self.baseline)

    def test_rejects_wrong_workspace_tampering_and_mismatched_baseline(self):
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(PackageError):
                SageProjectActionAdapter(FakeEngine(other, self.manifest), "candidate-1", self.project)
        with self.assertRaises(PackageError):
            SageProjectActionAdapter(self.engine, "candidate-1", object())
        alternate = normalize_package(source_package())
        alternate["files"][0]["content"] = "print('different')\n"
        with self.assertRaises(PackageError):
            SageProjectActionAdapter(FakeEngine(self.workspace, alternate), "candidate-1", self.project)
        self.engine.source["digest"] = "bad"
        with self.assertRaises(PackageError):
            SageProjectActionAdapter(self.engine, "candidate-1", self.project)

    def test_stale_edit_and_bad_source_are_blocked_without_replacing_head(self):
        with self.assertRaises(PackageError):
            self.adapter.execute({"action": "project_propose_edit", "path": "src/main.py", "content": "oops", "expected_revision": "a"*64})
        with self.assertRaises(PackageError):
            self.adapter.execute({"action": "project_propose_edit", "path": "toad_core/models.py", "content": "bad", "expected_revision": self.baseline})
        self.assertEqual(self.adapter.status()["revision"], self.baseline)


if __name__ == "__main__":
    unittest.main()
