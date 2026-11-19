"""Offline contract tests only. ReceiptDouble does NOT run Docker or a model."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toad_core.engine import Engine
from toad_core.repair_demo import FIXED_SOURCE, fixture
from toad_core.schema import package_digest
from tools.calculator_demo import independent_holdout


class ReceiptDouble:
    """Explicit boundary double: data structure tests, never live proof."""

    def __init__(self, passes=True, backend="docker"):
        self.passes = passes
        self.backend = backend
        self.packages = []

    def run(self, manifest, *, cancel=None):
        self.packages.append(copy.deepcopy(manifest))
        return {
            "schema": "toad-test-run-v1",
            "backend": self.backend,
            "digest": package_digest(manifest),
            "executed": True,
            "passed": self.passes,
            "cleanup_ok": True,
            "tests": [
                {"passed": self.passes, "executed": True, "cleanup_ok": True,
                 "category": "passed" if self.passes else "test_failure"}
                for _ in manifest["tests"]
            ],
        }


class IndependentCalculatorProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Engine(Path(self.temp.name) / "private")
        manifest = fixture()
        manifest["files"][0]["content"] = FIXED_SOURCE
        self.candidate = self.engine.ingest_package(manifest)

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def verify_fixture_with_double(self):
        self.engine.test(self.candidate["id"], worker=ReceiptDouble())

    def test_holdout_preserves_generated_source_and_replaces_model_tests(self):
        self.verify_fixture_with_double()
        worker = ReceiptDouble()
        proof = independent_holdout(self.engine, self.candidate["id"], worker=worker)
        self.assertEqual(proof["status"], "ready_for_owner_review")
        self.assertTrue(proof["owner_review_required"])
        self.assertFalse(proof["installed"])
        self.assertFalse(proof["deployed"])
        self.assertEqual(len(worker.packages), 1)
        manifest = worker.packages[0]
        source = next(f["content"] for f in manifest["files"]
                      if f["path"] == "calculator.py")
        self.assertEqual(source, FIXED_SOURCE)
        self.assertEqual(
            [f["path"] for f in manifest["files"]],
            ["calculator.py", "tests/test_calculator_holdout.py"])
        self.assertEqual(manifest["tests"], [{"kind": "unittest", "path": "tests"}])
        self.assertNotEqual(
            next(f["content"] for f in self.candidate["manifest"]["files"]
                 if f["path"] == "tests/test_calculator.py"),
            next(f["content"] for f in manifest["files"]
                 if f["path"] == "tests/test_calculator_holdout.py"))
        self.assertEqual(self.engine.store.latest_receipt(proof["holdout_candidate_id"])
                         ["id"], proof["holdout_receipt_id"])

    def test_no_prior_docker_receipt_refuses_holdout(self):
        with self.assertRaisesRegex(RuntimeError, "passing Docker receipt"):
            independent_holdout(self.engine, self.candidate["id"],
                                worker=ReceiptDouble())
        self.assertEqual(len(self.engine.list()), 1)

    def test_failed_holdout_is_not_a_success(self):
        self.verify_fixture_with_double()
        with self.assertRaisesRegex(RuntimeError, "did not pass"):
            independent_holdout(self.engine, self.candidate["id"],
                                worker=ReceiptDouble(passes=False))
        self.assertEqual(len(self.engine.list()), 2)
        holdout = next(c for c in self.engine.list() if c["id"] != self.candidate["id"])
        self.assertEqual(holdout["verification"], "unverified")

    def test_non_docker_holdout_is_not_a_success(self):
        self.verify_fixture_with_double()
        with self.assertRaisesRegex(RuntimeError, "did not pass"):
            independent_holdout(self.engine, self.candidate["id"],
                                worker=ReceiptDouble(backend="fake-worker"))

    def test_missing_required_module_fails_closed(self):
        self.verify_fixture_with_double()
        with patch.object(self.engine, "get") as get:
            edited = copy.deepcopy(self.candidate)
            edited["manifest"]["files"][0]["path"] = "another.py"
            get.return_value = edited
            with self.assertRaisesRegex(RuntimeError, "calculator.py"):
                independent_holdout(self.engine, self.candidate["id"],
                                    worker=ReceiptDouble())

    def test_stale_generated_receipt_is_rejected(self):
        self.verify_fixture_with_double()
        prior = self.engine.store.latest_receipt(self.candidate["id"])
        with patch.object(self.engine.store, "latest_receipt",
                          return_value={**prior, "digest": "stale"}):
            with self.assertRaisesRegex(RuntimeError, "passing Docker receipt"):
                independent_holdout(self.engine, self.candidate["id"],
                                    worker=ReceiptDouble())


if __name__ == "__main__":
    unittest.main()
