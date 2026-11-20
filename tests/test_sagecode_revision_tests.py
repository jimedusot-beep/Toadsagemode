"""Revision-bound test receipts: synthetic doubles never prove real execution."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toad_core.project_tools import SageProjectTools
from toad_core.sagecode_revision_tests import SageRevisionTestGate
from toad_core.schema import PackageError, package_digest


def fixture():
    return {
        "schema": "toad-ability-v2", "name": "source-check", "version": "0.1.0",
        "entrypoint": "src/app.py", "dependencies": [], "permissions": [],
        "tests": [{"kind": "unittest", "path": "tests"}],
        "files": [
            {"path": "src/app.py", "content": "def add(a, b):\n    return a + b\n"},
            {"path": "tests/test_app.py", "content": "import unittest\nfrom src.app import add\nclass T(unittest.TestCase):\n    def test_add(self): self.assertEqual(add(2, 3), 5)\n"},
            {"path": "README.md", "content": "# Bounded source test\n"},
        ],
    }


class SyntheticWorker:
    def __init__(self, *, missing_image=False, fake_pass=False, wrong_digest=False, wrong_test=False,
                 never_execute=False, on_run=None, cleanup_failure=False):
        self.calls = 0
        self.missing_image = missing_image
        self.fake_pass = fake_pass
        self.wrong_digest = wrong_digest
        self.wrong_test = wrong_test
        self.never_execute = never_execute
        self.on_run = on_run
        self.cleanup_failure = cleanup_failure

    def run(self, package, *, cancel=None):
        self.calls += 1
        if self.on_run is not None:
            self.on_run()
        spec = package["tests"][0]
        executed = not self.never_execute
        return {"schema": "toad-test-run-v1", "backend": "docker",
                "digest": "0" * 64 if self.wrong_digest else package_digest(package),
                "image_id": None if self.missing_image else "sha256:" + "a" * 64,
                "executed": executed, "passed": executed or self.fake_pass,
                "cleanup_ok": not self.cleanup_failure,
                "tests": ([{"index": 0, "kind": spec["kind"],
                            "path": "wrong.py" if self.wrong_test else spec["path"],
                            "passed": True, "executed": True,
                            "cleanup_ok": not self.cleanup_failure, "category": "passed"}]
                          if executed else [])}


class SageRevisionTestGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.project = SageProjectTools.create(self.workspace, "source-check", fixture(),
                                               allowed_project_ids={"source-check"})
        self.baseline = self.project.status()["revision"]

    def test_synthetic_pass_is_not_real_execution_or_release(self):
        worker = SyntheticWorker()
        report = SageRevisionTestGate(self.project, worker=worker).run(expected_revision=self.baseline)
        self.assertEqual(worker.calls, 1)
        self.assertEqual(report["outcome"], "rehearsal_passed")
        self.assertEqual(report["evidence_mode"], "test_double_rehearsal")
        self.assertFalse(report["executed"])
        self.assertFalse(report["passed"])
        self.assertEqual(report["verification"], "unverified")
        self.assertFalse(report["release_allowed"])
        self.assertTrue(report["owner_review_required"])
        self.assertFalse(report["stale"])
        self.assertEqual(len(report["receipt_id"]), 64)

    def test_changed_application_source_is_bound_to_exact_revision_and_frozen_plan(self):
        changed = self.project.propose_edit("src/app.py", "def add(a, b):\n    return a - b\n",
                                            expected_revision=self.baseline)
        report = SageRevisionTestGate(self.project, worker=SyntheticWorker()).run(
            expected_revision=changed["revision"])
        self.assertEqual(report["revision"], changed["revision"])
        self.assertEqual(report["package_digest"], package_digest(self.project._current()["manifest"]))
        self.assertEqual(report["outcome"], "rehearsal_passed")
        self.assertEqual(report["baseline_revision"], self.baseline)
        self.assertFalse(report["approved"])

    def test_frozen_test_file_change_rejected_before_worker_invocation(self):
        bad = self.project.propose_edit("tests/test_app.py", "assert True\n", expected_revision=self.baseline)
        worker = SyntheticWorker()
        with self.assertRaisesRegex(PackageError, "test"):
            SageRevisionTestGate(self.project, worker=worker).run(expected_revision=bad["revision"])
        self.assertEqual(worker.calls, 0)

    def test_stale_revision_rejected_before_worker_invocation(self):
        self.project.propose_edit("README.md", "# Update\n", expected_revision=self.baseline)
        worker = SyntheticWorker()
        with self.assertRaisesRegex(PackageError, "Stale"):
            SageRevisionTestGate(self.project, worker=worker).run(expected_revision=self.baseline)
        self.assertEqual(worker.calls, 0)

    def test_mocked_evidence_is_never_upgraded_even_if_pass_field_true(self):
        for options in ({"missing_image": True}, {"never_execute": True, "fake_pass": True},
                        {"cleanup_failure": True}, {"wrong_digest": True}, {"wrong_test": True}):
            with self.subTest(options=options):
                report = SageRevisionTestGate(self.project, worker=SyntheticWorker(**options)).run(
                    expected_revision=self.baseline)
                self.assertFalse(report["passed"])
                self.assertFalse(report["executed"])
                self.assertFalse(report["release_allowed"])
                self.assertNotEqual(report["outcome"], "tests_passed")
                self.assertEqual(report["verification"], "unverified")

    def test_no_docker_means_blocked_not_fallback(self):
        with patch("toad_core.lab.shutil.which", return_value=None):
            report = SageRevisionTestGate(self.project).run(expected_revision=self.baseline)
        self.assertEqual(report["evidence_mode"], "restricted_docker_worker")
        self.assertEqual(report["outcome"], "blocked")
        self.assertFalse(report["executed"])
        self.assertFalse(report["passed"])
        self.assertIsNone(report["image_id"])

    def test_evidence_is_immutable_and_detects_tampered_json(self):
        gate = SageRevisionTestGate(self.project, worker=SyntheticWorker())
        first = gate.run(expected_revision=self.baseline)
        evidence_path = self.project.project / "test-evidence" / (first["receipt_id"] + ".json")
        self.assertEqual(gate.read_receipt(first["receipt_id"])["outcome"], "rehearsal_passed")
        altered = json.loads(evidence_path.read_text())
        altered["approved"] = True
        evidence_path.write_text(json.dumps(altered))
        with self.assertRaisesRegex(PackageError, "integrity"):
            gate.read_receipt(first["receipt_id"])

    def test_previous_evidence_becomes_stale_after_new_revision(self):
        gate = SageRevisionTestGate(self.project, worker=SyntheticWorker())
        original = gate.run(expected_revision=self.baseline)
        self.project.propose_edit("README.md", "# Rewritten\n", expected_revision=self.baseline)
        last = gate.read_receipt(original["receipt_id"])
        self.assertTrue(last["stale"])
        self.assertFalse(last["release_allowed"])

    def test_project_changing_during_worker_call_blocks_receipt(self):
        worker = SyntheticWorker(on_run=lambda: self.project.propose_edit(
            "README.md", "# Changed during run\n", expected_revision=self.baseline))
        with self.assertRaisesRegex(PackageError, "changed during tests"):
            SageRevisionTestGate(self.project, worker=worker).run(expected_revision=self.baseline)
        self.assertFalse((self.project.project / "test-evidence").exists())

    def test_no_frozen_tests_blocks_without_worker(self):
        with tempfile.TemporaryDirectory() as another:
            data = fixture(); data["tests"] = []
            project = SageProjectTools.create(another, "empty-tests", data,
                                              allowed_project_ids={"empty-tests"})
            worker = SyntheticWorker()
            with self.assertRaisesRegex(PackageError, "No independent frozen tests"):
                SageRevisionTestGate(project, worker=worker).run(expected_revision=project.status()["revision"])
            self.assertEqual(worker.calls, 0)

    def test_bad_receipt_id_or_worker_rejected(self):
        gate = SageRevisionTestGate(self.project, worker=SyntheticWorker())
        with self.assertRaises(PackageError):
            gate.read_receipt("../bad")
        with self.assertRaises(PackageError):
            SageRevisionTestGate(self.project, worker=object())
        with self.assertRaises(PackageError):
            gate.run(expected_revision=True)


if __name__ == "__main__":
    unittest.main()
