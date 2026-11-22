"""SageCode V3: independent test-plan freeze, revision binding, no fake passes.

No untrusted application source is executed by these unit tests. They use
controlled return values and, optionally, DockerWorker's fail-closed path.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toad_core.project_tools import SageProjectTools
from toad_core.project_testing import SageProjectTestGate, _stage_package
from toad_core.schema import PackageError, package_digest
from toad_core.lab import DockerWorker


def project_package():
    return {
        "schema": "toad-ability-v2", "name": "test-project", "version": "0.1.0",
        "entrypoint": "src/main.py", "permissions": [], "dependencies": [], "tests": [],
        "files": [
            {"path": "src/main.py", "content": "from src.mathlib import add\nprint(add(1, 1))\n"},
            {"path": "src/mathlib.py", "content": "def add(a, b):\n    return a + b\n"},
            {"path": "README.md", "content": "# source only\n"},
        ]}


def stdout_plan():
    return {"tests": [{"kind": "python", "path": "src/main.py", "expected_stdout": "2\n"}], "files": []}


def unittest_plan():
    return {
        "tests": [{"kind": "unittest", "path": "tests"}],
        "files": [{"path": "tests/test_math.py", "content":
                   "import unittest\nfrom src.mathlib import add\n"
                   "class MathTests(unittest.TestCase):\n"
                   "    def test_add(self):\n        self.assertEqual(add(1, 1), 2)\n"}],
    }


class ClaimWorker:
    def __init__(self, hook=None):
        self.calls = []
        self.hook = hook

    def run(self, stage, *, cancel=None):
        self.calls.append(stage)
        if self.hook:
            self.hook()
        return {"backend": "docker", "digest": package_digest(stage),
                "passed": True, "executed": True, "cleanup_ok": True,
                "image_id": "sha256:" + "a" * 64,
                "tests": [{"passed": True, "executed": True, "cleanup_ok": True,
                           "category": "passed"} for _ in stage["tests"]]}


class TestProjectTesting(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.workspace = Path(tmp.name)
        self.project = SageProjectTools.create(
            self.workspace, "test-project", project_package(),
            allowed_project_ids={"test-project"})
        self.baseline = self.project.status()["revision"]

    def freeze(self, plan=None):
        return SageProjectTestGate.create(self.project, stdout_plan() if plan is None else plan)

    def test_initial_freeze_is_bound_to_baseline_and_private_directory(self):
        gate = self.freeze()
        summary = gate.summary()
        self.assertEqual(summary["baseline_revision"], self.baseline)
        self.assertEqual(summary["project_id"], "test-project")
        self.assertEqual(summary["test_count"], 1)
        self.assertFalse(summary["release_allowed"])
        self.assertEqual(len(summary["plan_digest"]), 64)
        self.assertTrue(gate.directory.is_dir())
        self.assertFalse(gate.directory.is_symlink())
        self.assertEqual(SageProjectTestGate(self.project).plan_digest, summary["plan_digest"])
        if os.name != "nt":
            self.assertEqual(gate.directory.stat().st_mode & 0o077, 0)

    def test_second_plan_cannot_replace_frozen_plan(self):
        gate = self.freeze()
        with self.assertRaises(PackageError):
            SageProjectTestGate.create(self.project, unittest_plan())
        self.assertEqual(gate.summary()["plan_digest"], SageProjectTestGate(self.project).plan_digest)

    def test_plan_cannot_be_created_after_source_edit(self):
        self.project.propose_edit("src/mathlib.py", "# change\n", expected_revision=self.baseline)
        with self.assertRaisesRegex(PackageError, "before proposing"):
            self.freeze()

    def test_expected_stdout_is_independent_of_source_changes(self):
        gate = self.freeze()
        change = self.project.propose_edit("src/mathlib.py", "def add(a, b):\n    return 100\n",
                                           expected_revision=self.baseline)
        worker = ClaimWorker()
        evidence = gate.run_current(worker=worker)
        self.assertEqual(evidence["revision"], change["revision"])
        self.assertEqual([{k: t[k] for k in ("kind", "path", "expected_stdout")} for t in worker.calls[0]["tests"]], stdout_plan()["tests"])
        self.assertEqual(worker.calls[0]["files"][1]["content"], "def add(a, b):\n    return 100\n")
        self.assertEqual(evidence["status"], "test_double_unverified")
        self.assertFalse(evidence["passed"])
        self.assertFalse(evidence["executed"])
        self.assertFalse(evidence["release_allowed"])

    def test_unittest_files_remain_frozen_and_are_not_in_project(self):
        gate = self.freeze(unittest_plan())
        before = self.project.status()["revision"]
        worker = ClaimWorker()
        gate.run_current(worker=worker)
        tested = worker.calls[0]
        self.assertEqual([{k: t[k] for k in ("kind", "path")} for t in tested["tests"]], unittest_plan()["tests"])
        self.assertTrue(any(f["path"] == "tests/test_math.py" for f in tested["files"]))
        self.assertFalse(any(f["path"] == "tests/test_math.py" for f in self.project._current()["manifest"]["files"]))
        self.assertEqual(self.project.status()["revision"], before)
        with self.assertRaises(PackageError):
            self.project.propose_edit("tests/test_math.py", "assert False", expected_revision=before)

    def test_fake_worker_cannot_create_a_verified_result(self):
        gate = self.freeze()
        out = gate.run_current(worker=ClaimWorker())
        self.assertEqual(out["backend"], "test_double")
        self.assertEqual(out["verification"], "unverified")
        self.assertFalse(out["approved"])
        self.assertFalse(out["passed"])
        self.assertFalse(out["executed"])
        self.assertEqual(gate.evidence_for_current(out["receipt_id"])["display_status"], "test_double_unverified")

    def test_real_docker_worker_without_executable_blocks_without_host_fallback(self):
        gate = self.freeze()
        real = DockerWorker()
        real.docker = None  # prove deterministic fail-closed behavior without docker startup
        out = gate.run_current(worker=real)
        self.assertEqual(out["status"], "blocked")
        self.assertFalse(out["passed"])
        self.assertFalse(out["executed"])
        self.assertEqual(out["backend"], "docker")

    def test_test_failure_stays_unverified_and_does_not_release(self):
        gate = self.freeze()
        real = DockerWorker()
        fake_result = {"backend": "docker", "digest": None, "passed": False,
                       "executed": True, "cleanup_ok": True,
                       "tests": [{"passed": False, "executed": True, "cleanup_ok": True,
                                  "category": "test_failure"}]}
        def failures(self, package, *, cancel=None):
            return {**fake_result, "digest": package_digest(package)}
        with patch.object(DockerWorker, "run", failures):
            out = gate.run_current(worker=real)
        # Unit-test monkeypatch simulates a return; it is NOT real Docker execution.
        self.assertEqual(out["status"], "failed")
        self.assertFalse(out["passed"])
        self.assertFalse(out["release_allowed"])
        self.assertEqual(out["cases"][0]["category"], "test_failure")

    def test_simulated_valid_docker_receipt_is_still_not_owner_approval(self):
        gate = self.freeze()
        real = DockerWorker()
        def reported_pass(_self, stage, *, cancel=None):
            spec = stage["tests"][0]
            return {"backend": "docker", "digest": package_digest(stage),
                    "passed": True, "executed": True, "cleanup_ok": True,
                    "image_id": "sha256:" + "f" * 64, "blocked_reason": None,
                    "tests": [{"index": 0, "kind": spec["kind"], "path": spec["path"],
                               "passed": True, "executed": True, "cleanup_ok": True,
                               "category": "passed"}]}
        # Structural validation only: patched worker is NOT evidence of Docker execution.
        with patch.object(DockerWorker, "run", reported_pass):
            receipt = gate.run_current(worker=real)
        self.assertEqual(receipt["status"], "passed")
        self.assertTrue(receipt["passed"])
        self.assertEqual(receipt["verification"], "unverified")
        self.assertFalse(receipt["approved"])
        self.assertFalse(receipt["release_allowed"])

    def test_contradictory_passing_category_cannot_verify_revision(self):
        gate = self.freeze()
        real = DockerWorker()
        for category in ("test_failure", "timeout", "unknown"):
            with self.subTest(category=category):
                def contradictory(_self, stage, *, cancel=None):
                    spec = stage["tests"][0]
                    return {"backend": "docker", "digest": package_digest(stage),
                            "passed": True, "executed": True, "cleanup_ok": True,
                            "image_id": "sha256:" + "f" * 64, "blocked_reason": None,
                            "tests": [{"index": 0, "kind": spec["kind"], "path": spec["path"],
                                       "passed": True, "executed": True, "cleanup_ok": True,
                                       "category": category}]}
                # Simulated DockerWorker response, never a real container run.
                with patch.object(DockerWorker, "run", contradictory):
                    receipt = gate.run_current(worker=real)
                self.assertEqual(receipt["status"], "failed")
                self.assertFalse(receipt["passed"])
                self.assertFalse(receipt["release_allowed"])
                self.assertEqual(receipt["verification"], "unverified")

    def test_unmatched_container_test_identity_cannot_count_as_passed(self):
        gate = self.freeze()
        real = DockerWorker()
        def wrong_identity(_self, stage, *, cancel=None):
            return {"backend": "docker", "digest": package_digest(stage),
                    "passed": True, "executed": True, "cleanup_ok": True,
                    "image_id": "sha256:" + "f" * 64, "blocked_reason": None,
                    "tests": [{"index": 0, "kind": "python", "path": "wrong.py",
                               "passed": True, "executed": True, "cleanup_ok": True}]}
        # Fake return values are deliberately not described as real execution.
        with patch.object(DockerWorker, "run", wrong_identity):
            receipt = gate.run_current(worker=real)
        self.assertEqual(receipt["status"], "failed")
        self.assertFalse(receipt["passed"])
        self.assertFalse(receipt["release_allowed"])

    def test_stale_revision_during_test_invalidates_pass(self):
        gate = self.freeze()
        worker = ClaimWorker(lambda: self.project.propose_edit(
            "README.md", "# modified while testing\n", expected_revision=self.baseline))
        out = gate.run_current(worker=worker)
        self.assertEqual(out["status"], "stale_revision")
        self.assertFalse(out["passed"])
        self.assertEqual(gate.evidence_for_current(out["receipt_id"])["display_status"], "stale_revision")

    def test_historical_result_becomes_stale_after_edit_and_restores_when_revision_restored(self):
        gate = self.freeze()
        out = gate.run_current(worker=ClaimWorker())
        changed = self.project.propose_edit("README.md", "# changed\n", expected_revision=self.baseline)
        self.assertFalse(gate.evidence_for_current(out["receipt_id"])["is_current"])
        self.project.restore(self.baseline, expected_revision=changed["revision"])
        self.assertTrue(gate.evidence_for_current(out["receipt_id"])["is_current"])
        self.assertFalse(gate.evidence_for_current(out["receipt_id"])["passed"])

    def test_source_revision_and_frozen_test_hash_are_bound_to_evidence(self):
        gate = self.freeze()
        worker = ClaimWorker()
        out = gate.run_current(worker=worker)
        self.assertEqual(out["plan_digest"], gate.plan_digest)
        self.assertEqual(out["revision"], self.baseline)
        self.assertEqual(out["tested_package_digest"], package_digest(worker.calls[0]))
        self.assertEqual(len(out["evidence_digest"]), 64)
        self.assertEqual(len(out["receipt_id"]), 32)

    def test_plan_tampering_and_symlink_are_rejected(self):
        gate = self.freeze()
        plan_file = gate.directory / "frozen-tests.json"
        data = json.loads(plan_file.read_text())
        data["plan"]["tests"][0]["expected_stdout"] = "hacked\n"
        plan_file.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(PackageError, "changed"):
            gate.run_current(worker=ClaimWorker())
        plan_file.unlink()
        external = self.workspace / "sensitive-file"
        external.write_text("CANARY", encoding="utf-8")
        try:
            plan_file.symlink_to(external)
        except OSError:
            self.skipTest("No permission to create symlinks")
        with self.assertRaises(PackageError):
            gate.summary()
        self.assertEqual(external.read_text(), "CANARY")

    def test_receipt_tampering_is_rejected(self):
        gate = self.freeze()
        out = gate.run_current(worker=ClaimWorker())
        path = gate.receipts / (out["receipt_id"] + ".json")
        data = json.loads(path.read_text())
        data["passed"] = True
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(PackageError, "integrity"):
            gate.evidence_for_current(out["receipt_id"])
        for bad in ("../secret", "xxx", "a" * 33, None):
            with self.assertRaises(PackageError):
                gate.evidence_for_current(bad)

    def test_reject_malformed_untrusted_tests_before_writing(self):
        cases = [
            {"tests": [{"kind": "shell", "command": "echo hi"}], "files": []},
            {"tests": [{"kind": "unittest", "path": "tests"}], "files": []},
            {"tests": [{"kind": "python", "path": "../etc/passwd", "expected_stdout": ""}], "files": []},
            {"tests": [{"kind": "python", "path": "src/main.py", "expected_stdout": "2\n", "url": "https://x"}], "files": []},
            {"tests": [{"kind": "python", "path": "src/main.py", "expected_stdout": "2\n"}],
             "files": [{"path": "tests/test_math.py", "content": "x" * 64001}]},
            {"tests": [{"kind": "unittest", "path": "tests"}],
             "files": [{"path": "tests/secret.py", "content": "x"}]},
            {"tests": [{"kind": "unittest", "path": "tests"}],
             "files": [{"path": "tests/test_math.py", "content": "\ud800"}]},
        ]
        for bad in cases:
            with self.subTest(case=str(bad)[:80]):
                with self.assertRaises(PackageError):
                    self.freeze(bad)
        self.assertFalse((self.project.root.parent / "sagecode-v3" / "test-project").exists())

    def test_reject_test_file_alias_or_colliding_path(self):
        for path in ("src/mathlib.py", "TESTS/TEST_main.py", "tests/../../x.py", "tests/.env", "tests/test_math.txt"):
            with self.subTest(path=path):
                bad = unittest_plan()
                bad["files"][0]["path"] = path
                with self.assertRaises(PackageError):
                    self.freeze(bad)

    def test_worker_raises_without_leaking_exception_details(self):
        gate = self.freeze()
        class ExplodingWorker:
            def run(self, stage, *, cancel=None):
                raise RuntimeError("TOP-SECRET-SHOULD-NOT-LEAK")
        out = gate.run_current(worker=ExplodingWorker())
        self.assertEqual(out["status"], "test_double_unverified")
        self.assertNotIn("TOP-SECRET", json.dumps(out))

    def test_evidence_limit_blocks_before_worker_is_invoked(self):
        gate = self.freeze()
        for i in range(40):
            evidence = gate.run_current(worker=ClaimWorker())
        before_count = len(list(gate.receipts.iterdir()))
        worker = ClaimWorker()
        with self.assertRaisesRegex(PackageError, "limit"):
            gate.run_current(worker=worker)
        self.assertEqual(len(worker.calls), 0)
        self.assertEqual(len(list(gate.receipts.iterdir())), before_count)

    def test_model_cannot_change_or_gain_access_to_frozen_plan(self):
        gate = self.freeze()
        with self.assertRaises(PackageError):
            self.project.propose_edit("tests/test_math.py", "payload", expected_revision=self.baseline)
        self.assertEqual(self.project.status()["revision"], self.baseline)
        self.assertTrue(gate.summary()["source_only"])


if __name__ == "__main__":
    unittest.main()
