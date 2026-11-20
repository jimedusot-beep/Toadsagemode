"""SageCode V1: source-only project tools and negative security regressions."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from toad_core.project_tools import SageProjectTools
from toad_core.schema import PackageError


def package():
    return {
        "schema": "toad-ability-v2", "name": "study-planner", "version": "0.1.0",
        "entrypoint": "src/main.py", "permissions": [], "dependencies": [], "tests": [],
        "files": [
            {"path": "src/main.py", "content": "from utils import title\nprint(title)\n"},
            {"path": "src/utils.py", "content": "title = 'Daily Plan'\n"},
            {"path": "README.md", "content": "# Daily Plan\nA test project.\n"},
        ],
    }


class SageProjectToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name)
        self.source = package()
        self.tools = SageProjectTools.create(self.workspace, "study-planner", self.source,
                                             allowed_project_ids={"study-planner"})
        self.baseline = self.tools.status()["revision"]

    def test_created_project_has_explicit_unverified_state(self):
        status = self.tools.status()
        self.assertEqual(status["baseline_revision"], self.baseline)
        self.assertEqual(status["review_status"], "pending_review")
        self.assertFalse(status["approved"])
        self.assertFalse(status["executed"])
        self.assertFalse(status["release_allowed"])
        self.assertIsNone(status["test_evidence"])
        self.assertNotIn("git", str(self.tools.project))

    def test_tree_contains_actual_directories_and_bounded_hashes(self):
        entries = self.tools.list_tree()["entries"]
        self.assertEqual({(e["path"], e["kind"]) for e in entries},
                         {("src", "directory"), ("src/main.py", "file"),
                          ("src/utils.py", "file"), ("README.md", "file")})
        self.assertEqual(len(next(x for x in entries if x["path"] == "src/main.py")["sha256"]), 64)

    def test_read_lines_and_search_filename_and_content(self):
        result = self.tools.read_file("src/main.py", start_line=2, max_lines=1)
        self.assertEqual(result["content"], "print(title)\n")
        self.assertEqual(result["total_lines"], 2)
        self.assertFalse(result["truncated"])
        matches = self.tools.search("plan")["matches"]
        self.assertTrue(any(x["path"] == "README.md" and x["line"] > 0 for x in matches))
        self.assertTrue(any(x["path"] == "src/utils.py" and x["line"] > 0 for x in matches))
        self.assertTrue(any(x["path"] == "src/main.py" for x in self.tools.search("main.py")["matches"]))

    def test_read_is_bounded_for_long_lines_and_many_lines(self):
        huge = ("ü" * 10000) + "\n" + "line\n" * 210
        modified = self.tools.propose_edit("src/utils.py", huge, expected_revision=self.baseline)
        read = self.tools.read_file("src/utils.py", max_lines=200)
        self.assertLessEqual(len(read["content"].encode("utf-8")), 16000)
        self.assertTrue(read["truncated"])
        self.assertEqual(read["revision"], modified["revision"])

    def test_edit_generates_diff_revision_and_does_not_modify_original_package(self):
        original = copy.deepcopy(self.source)
        result = self.tools.propose_edit("src/utils.py", "title = 'Homework'\n", expected_revision=self.baseline)
        self.assertFalse(result["unchanged"])
        self.assertIn("-title = 'Daily Plan'", result["diff"])
        self.assertIn("+title = 'Homework'", result["diff"])
        self.assertEqual(self.tools.read_file("src/utils.py")["content"], "title = 'Homework'\n")
        self.assertEqual(self.source, original)
        self.assertEqual(result["verification"], "unverified")
        self.assertNotEqual(result["revision"], self.baseline)
        reopened = SageProjectTools(self.workspace, "study-planner", allowed_project_ids={"study-planner"})
        self.assertEqual(reopened.status()["revision"], result["revision"])

    def test_restore_baseline_and_reopen(self):
        changed = self.tools.propose_edit("README.md", "# Changed\n", expected_revision=self.baseline)
        restored = self.tools.restore(self.baseline, expected_revision=changed["revision"])
        self.assertTrue(restored["restored"])
        self.assertEqual(self.tools.read_file("README.md")["content"], self.source["files"][2]["content"])
        self.assertFalse(restored["release_allowed"])
        self.assertEqual(SageProjectTools(self.workspace, "study-planner", allowed_project_ids={"study-planner"}).status()["revision"], self.baseline)
        self.tools.restore(changed["revision"], expected_revision=self.baseline)
        self.assertEqual(self.tools.read_file("README.md")["content"], "# Changed\n")

    def test_unmodified_edit_does_not_create_revision(self):
        prior = len(list(self.tools.revisions.iterdir()))
        result = self.tools.propose_edit("README.md", "# Daily Plan\nA test project.\n", expected_revision=self.baseline)
        self.assertTrue(result["unchanged"])
        self.assertEqual(prior, len(list(self.tools.revisions.iterdir())))

    def test_wrong_project_does_not_grant_access(self):
        with self.assertRaises(PackageError):
            SageProjectTools(self.workspace, "study-planner", allowed_project_ids={"another-project"})
        with self.assertRaises(PackageError):
            SageProjectTools.create(self.workspace, "bad-id", self.source, allowed_project_ids=set())
        with self.assertRaises(PackageError):
            SageProjectTools(self.workspace, "../study-planner", allowed_project_ids={"../study-planner"})

    def test_traversal_absolute_and_protected_paths_refused(self):
        for path in ("../README.md", "/etc/passwd", "C:/evil.py", "src/../../README.md", "src\\main.py", "toad_core/models.py", "src/.env", "not-listed.py", ".git/config"):
            with self.subTest(path=path):
                with self.assertRaises(PackageError):
                    self.tools.read_file(path)
                with self.assertRaises(PackageError):
                    self.tools.propose_edit(path, "bad", expected_revision=self.baseline)
        self.assertEqual(self.tools.status()["revision"], self.baseline)

    def test_initial_package_rejects_secret_named_and_protected_files(self):
        for name in ("secrets.json", "src/credentials.json", "src/api_key.json", "src/token.json", "src/.env", "toad_core/worker.py"):
            altered = package()
            altered["files"][1]["path"] = name
            with self.subTest(name=name):
                with self.assertRaises(PackageError):
                    SageProjectTools.create(self.workspace, "different", altered, allowed_project_ids={"different"})

    def test_duplicate_case_aliases_rejected_by_existing_manifest_validation(self):
        altered = package()
        altered["files"].append({"path": "SRC/Main.py", "content": "aliased"})
        with self.assertRaises(PackageError):
            SageProjectTools.create(self.workspace, "different", altered, allowed_project_ids={"different"})

    def test_oversized_file_and_full_manifest_blocked_without_head_change(self):
        for content in ("x" * 250001, "a\x00b"):
            with self.assertRaises(PackageError):
                self.tools.propose_edit("README.md", content, expected_revision=self.baseline)
        self.assertEqual(self.tools.status()["revision"], self.baseline)

    def test_stale_revision_fails_closed(self):
        first = self.tools.propose_edit("src/main.py", "print('changed')\n", expected_revision=self.baseline)
        with self.assertRaisesRegex(PackageError, "Stale"):
            self.tools.propose_edit("src/main.py", "print('bad')\n", expected_revision=self.baseline)
        with self.assertRaisesRegex(PackageError, "Stale"):
            self.tools.restore(self.baseline, expected_revision=self.baseline)
        self.assertEqual(self.tools.status()["revision"], first["revision"])

    def test_revision_tampering_blocks_reads_and_edits(self):
        revised = self.tools.propose_edit("README.md", "# New\n", expected_revision=self.baseline)
        revision_path = self.tools.revisions / (revised["revision"] + ".json")
        body = json.loads(revision_path.read_text())
        body["manifest"]["files"][0]["content"] = "malicious change"
        revision_path.write_text(json.dumps(body), encoding="utf-8")
        with self.assertRaisesRegex(PackageError, "integrity"):
            self.tools.read_file("README.md")
        with self.assertRaises(PackageError):
            self.tools.propose_edit("README.md", "# Other\n", expected_revision=revised["revision"])

    def test_duplicate_json_keys_in_head_are_rejected(self):
        head = self.tools.project / "head.json"
        head.write_text('{"revision":"' + self.baseline + '","revision":"' + self.baseline + '"}')
        with self.assertRaises(PackageError):
            self.tools.status()

    def test_missing_revision_and_forged_head_are_rejected(self):
        self.tools.project.joinpath("head.json").write_text(json.dumps({"revision": "a" * 64}))
        with self.assertRaises(PackageError):
            self.tools.status()

    @unittest.skipUnless(hasattr(os, "symlink"), "Symlinks not available")
    def test_symlinked_head_and_revision_do_not_escape_workspace(self):
        external = self.workspace / "outside.txt"
        external.write_text("canary", encoding="utf-8")
        head = self.tools.project / "head.json"
        head.unlink()
        try:
            head.symlink_to(external)
        except OSError:
            self.skipTest("Symlink creation not permitted")
        with self.assertRaises(PackageError):
            self.tools.propose_edit("README.md", "bad", expected_revision=self.baseline)
        self.assertEqual(external.read_text(), "canary")
        head.unlink()
        head.write_text(json.dumps({"revision": self.baseline}), encoding="utf-8")
        revision = self.tools.revisions / (self.baseline + ".json")
        revision.unlink()
        revision.symlink_to(external)
        with self.assertRaises(PackageError):
            self.tools.read_file("README.md")
        self.assertEqual(external.read_text(), "canary")

    def test_directory_symlink_is_rejected(self):
        external = self.workspace / "alternate"
        external.mkdir()
        revisions = self.tools.revisions
        backup = self.tools.project / "revisions-backup"
        revisions.rename(backup)
        try:
            revisions.symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("Symlink creation not permitted")
        with self.assertRaises(PackageError):
            self.tools.list_tree()
        self.assertFalse((external / "head.json").exists())

    def test_malformed_arguments_are_rejected(self):
        for bad in (0, -1, True, 201, "100"):
            with self.assertRaises(PackageError):
                self.tools.read_file("README.md", max_lines=bad)
        for bad in (0, True, 101, "10"):
            with self.assertRaises(PackageError):
                self.tools.search("plan", limit=bad)
        for bad in ("", "\x00", "a" * 101):
            with self.assertRaises(PackageError):
                self.tools.search(bad)
        with self.assertRaises(PackageError):
            self.tools.propose_edit("README.md", None, expected_revision=self.baseline)
        with self.assertRaises(PackageError):
            self.tools.restore("bad-revision", expected_revision=self.baseline)

    def test_approved_or_executable_result_is_never_fabricated(self):
        original = self.tools.status()
        self.assertFalse(original["release_allowed"])
        for op in [lambda: self.tools.read_file("src/utils.py"),
                   lambda: self.tools.search("plan"),
                   lambda: self.tools.propose_edit("README.md", "# Changed\n", expected_revision=self.baseline)]:
            op()
        self.assertEqual(self.tools.status()["verification"], "unverified")
        self.assertFalse(self.tools.status()["approved"])


if __name__ == "__main__":
    unittest.main()
