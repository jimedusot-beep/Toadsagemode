"""Evidence-first comparison tests. Explicit doubles do not run Docker code."""
import copy
import tempfile
import unittest
from pathlib import Path

from toad_core.cli import parser, dispatch
from toad_core.engine import Engine
from toad_core.experiment_review import compare_candidates
from toad_core.schema import PackageError, package_digest
from test_packages import package


IMAGE = "sha256:" + "a" * 64
OTHER_IMAGE = "sha256:" + "b" * 64
POLICY = {"image": "toad-sage-lab:1", "timeout_seconds": 10,
          "output_bytes": 64000, "memory_mb": 128, "cpus": 0.5,
          "pids": 32, "disk_mb": 32}


class ReceiptDouble:
    """Emit receipt-shaped data only; never execute the candidate code."""

    def __init__(self, *, image=IMAGE, policy=None, cleanup=True,
                 executed=True, wrong_index=False):
        self.image = image
        self.policy = copy.deepcopy(POLICY if policy is None else policy)
        self.cleanup = cleanup
        self.executed = executed
        self.wrong_index = wrong_index

    def run(self, manifest, *, cancel=None):
        # Explicit fake outcome for deterministic data-contract tests.
        passed = manifest["files"][0]["content"].startswith('print("hello")\n')
        tests = [{
            "index": 42 if self.wrong_index else 0,
            "kind": manifest["tests"][0]["kind"],
            "path": manifest["tests"][0]["path"],
            "passed": passed and self.executed and self.cleanup,
            "executed": self.executed,
            "cleanup_ok": self.cleanup,
            "category": "passed" if passed else "test_failure",
            "stdout": "hello\n" if passed else "wrong\n",
            "stderr": "" if passed else "AssertionError",
        }]
        return {
            "backend": "docker", "digest": package_digest(manifest),
            "executed": self.executed,
            "passed": passed and self.executed and self.cleanup,
            "cleanup_ok": self.cleanup,
            "image_id": self.image, "policy": copy.deepcopy(self.policy),
            "tests": tests if self.executed else [],
        }


class CandidateComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.engine = Engine(Path(self.temporary.name))
        self.broken = self.engine.ingest_package(package('print("wrong")\n'))
        self.fixed = self.engine.ingest_package(package())

    def tearDown(self):
        self.engine.close()
        self.temporary.cleanup()

    def test_failing_then_passing_revision_qualifies_for_review_only(self):
        self.engine.test(self.broken["id"], ReceiptDouble())
        self.engine.test(self.fixed["id"], ReceiptDouble())
        before_events = len(self.engine.store.events())
        report = compare_candidates(self.engine, self.broken["id"], self.fixed["id"])
        self.assertEqual(report["status"], "comparable")
        self.assertEqual(report["assessment"], "challenger_improved_test_outcome")
        self.assertEqual(report["scores"], {"baseline": 0, "challenger": 1})
        self.assertEqual(report["changed_paths"], ["main.py"])
        self.assertTrue(all(x["passed"] for x in report["gate_results"]))
        self.assertTrue(report["owner_review_required"])
        for key in ("approved", "installed", "merged", "deployed"):
            self.assertFalse(report[key])
        self.assertEqual(len(self.engine.store.events()), before_events)
        self.assertEqual(report, compare_candidates(self.engine, self.broken["id"], self.fixed["id"]))
        self.assertEqual(len(report["evidence_sha256"]), 64)

    def test_no_execution_or_missing_receipt_blocks(self):
        report = compare_candidates(self.engine, self.broken["id"], self.fixed["id"])
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["assessment"], "incomparable")
        self.assertIsNone(report["scores"]["challenger"])
        self.assertFalse(next(x["passed"] for x in report["gate_results"]
                              if x["gate"] == "baseline-receipt"))
        self.engine.test(self.broken["id"], ReceiptDouble(executed=False))
        self.engine.test(self.fixed["id"], ReceiptDouble())
        report = compare_candidates(self.engine, self.broken["id"], self.fixed["id"])
        self.assertEqual(report["status"], "blocked")

    def test_cleanup_failure_does_not_count_as_test_regression(self):
        self.engine.test(self.broken["id"], ReceiptDouble(cleanup=False))
        self.engine.test(self.fixed["id"], ReceiptDouble())
        report = compare_candidates(self.engine, self.broken["id"], self.fixed["id"])
        self.assertEqual(report["status"], "blocked")
        self.assertIn("cleanup", str(report["gate_results"]).lower())

    def test_different_image_or_resource_policy_blocks_comparison(self):
        for worker in (ReceiptDouble(image=OTHER_IMAGE),
                       ReceiptDouble(policy={**POLICY, "memory_mb": 64})):
            with self.subTest(image=worker.image, policy=worker.policy):
                self.engine.test(self.broken["id"], ReceiptDouble())
                self.engine.test(self.fixed["id"], worker)
                report = compare_candidates(self.engine, self.broken["id"], self.fixed["id"])
                self.assertEqual(report["status"], "blocked")
                self.assertTrue(any(not g["passed"] and g["gate"] in
                                    ("same-image", "same-policy") for g in report["gate_results"]))

    def test_fake_receipt_with_wrong_test_index_is_rejected(self):
        self.engine.test(self.broken["id"], ReceiptDouble(wrong_index=True))
        self.engine.test(self.fixed["id"], ReceiptDouble())
        report = compare_candidates(self.engine, self.broken["id"], self.fixed["id"])
        self.assertEqual(report["status"], "blocked")
        self.assertIn("metadata", str(report["gate_results"]))

    def test_frozen_test_changes_never_compare(self):
        self.engine.test(self.broken["id"], ReceiptDouble())
        modified = package()
        modified["tests"][0]["expected_stdout"] = "another value\n"
        different = self.engine.ingest_package(modified)
        self.engine.test(different["id"], ReceiptDouble())
        report = compare_candidates(self.engine, self.broken["id"], different["id"])
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(next(x["passed"] for x in report["gate_results"]
                              if x["gate"] == "frozen-repair-contract"))

    def test_equal_outcomes_never_claim_better_code(self):
        extra = self.engine.ingest_package(package('print("wrong2")\n'))
        self.engine.test(self.broken["id"], ReceiptDouble())
        self.engine.test(extra["id"], ReceiptDouble())
        self.assertEqual(compare_candidates(
            self.engine, self.broken["id"], extra["id"])["assessment"],
            "both_fail_no_winner")

        previous = self.engine.ingest_package(package('print("hello")\n# benign comment\n'))
        self.engine.test(previous["id"], ReceiptDouble())
        self.engine.test(self.fixed["id"], ReceiptDouble())
        report = compare_candidates(self.engine, previous["id"], self.fixed["id"])
        self.assertEqual(report["assessment"], "both_pass_no_quality_winner")
        self.assertEqual(report["scores"], {"baseline": 1, "challenger": 1})

    def test_regression_is_not_preferred(self):
        self.engine.test(self.fixed["id"], ReceiptDouble())
        self.engine.test(self.broken["id"], ReceiptDouble())
        report = compare_candidates(self.engine, self.fixed["id"], self.broken["id"])
        self.assertEqual(report["assessment"], "challenger_regressed")
        self.assertEqual(report["scores"], {"baseline": 1, "challenger": 0})

    def test_same_revision_rejected_and_cli_is_read_only(self):
        with self.assertRaises(PackageError):
            compare_candidates(self.engine, self.fixed["id"], self.fixed["id"])
        self.engine.test(self.broken["id"], ReceiptDouble())
        self.engine.test(self.fixed["id"], ReceiptDouble())
        args = parser().parse_args(["experiments", "compare", self.broken["id"], self.fixed["id"]])
        out = dispatch(self.engine, args)
        self.assertEqual(out["status"], "comparable")


if __name__ == "__main__":
    unittest.main()
