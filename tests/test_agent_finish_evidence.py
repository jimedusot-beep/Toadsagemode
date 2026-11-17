"""Regression tests: a model's finish instruction cannot fabricate verification.

WorkerDouble is a controlled test fixture, NOT evidence of a real Docker run.
A real acceptance test still needs a restricted local Docker receipt.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toad_core.controlled_agent import ControlledAgent
from toad_core.engine import Engine
from toad_core.schema import PackageError, package_digest


def demo_manifest():
    return {
        "schema": "toad-ability-v2",
        "name": "review-evidence-demo",
        "version": "0.1.0",
        "description": "A harmless deterministic package",
        "files": [{"path": "main.py", "content": "print('hello')\n"}],
        "entrypoint": "main.py",
        "permissions": [],
        "dependencies": [],
        "tests": [{"kind": "python", "path": "main.py",
                   "expected_stdout": "hello\n"}],
    }


class WorkerDouble:
    """Only exercises Store's receipt contract; does not execute code."""

    def __init__(self, *, executed=True, passed=True, cleanup_ok=True):
        self.executed = executed
        self.passed = passed
        self.cleanup_ok = cleanup_ok

    def run(self, package, *, cancel=None):
        return {
            "digest": package_digest(package),
            "backend": "docker",
            "executed": self.executed,
            "passed": self.passed,
            "cleanup_ok": self.cleanup_ok,
            "tests": [{
                "executed": self.executed,
                "passed": self.passed,
                "cleanup_ok": self.cleanup_ok,
            }],
        }


class AgentFinishEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Engine(Path(self.temp.name))
        self.candidate = self.engine.ingest_package(demo_manifest())

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def finish(self, trajectory):
        agent = ControlledAgent(self.engine, trajectory,
                                candidate_id=self.candidate["id"])
        observation = agent.execute_actions({
            "action": "finish",
            "candidate_id": self.candidate["id"],
            "message": "Model says the work is done",
        })
        return agent, observation

    def test_finish_without_tests_is_review_only(self):
        agent, observation = self.finish("no-receipt")
        self.assertEqual(agent.state["status"], "awaiting_review")
        self.assertEqual(observation["verification"], "unverified")
        self.assertIsNone(observation["receipt_id"])
        self.assertTrue(observation["owner_review_required"])
        self.assertFalse(observation["installed"])
        self.assertNotEqual(agent.state["status"], "completed")
        self.assertEqual(ControlledAgent(self.engine, "no-receipt").run("again"),
                         agent.state)
        with self.assertRaises(PackageError):
            agent.execute_actions({"action": "inspect_candidate",
                                   "candidate_id": self.candidate["id"]})

    def test_nonexecuted_receipt_does_not_verify(self):
        receipt = self.engine.test(self.candidate["id"],
                                   worker=WorkerDouble(executed=False))
        self.assertFalse(receipt["passed"])
        agent, observation = self.finish("not-executed")
        self.assertEqual(observation["verification"], "unverified")
        self.assertEqual(agent.state["status"], "awaiting_review")

    def test_test_double_receipt_is_bound_to_exact_candidate(self):
        receipt = self.engine.test(self.candidate["id"], worker=WorkerDouble())
        self.assertTrue(receipt["passed"])
        agent, observation = self.finish("with-double")
        self.assertEqual(agent.state["status"], "awaiting_review")
        self.assertEqual(observation["verification"], "verified")
        self.assertEqual(observation["candidate_id"], self.candidate["id"])
        self.assertEqual(observation["receipt_id"], receipt["id"])
        self.assertTrue(observation["owner_review_required"])
        self.assertFalse(observation["installed"])

    def test_stale_receipt_cannot_verify_another_digest(self):
        receipt = self.engine.test(self.candidate["id"], worker=WorkerDouble())
        stale = {**receipt, "digest": "mismatched-content"}
        with patch.object(self.engine.store, "latest_receipt", return_value=stale):
            _, observation = self.finish("stale")
        self.assertEqual(observation["verification"], "unverified")
        self.assertIsNone(observation["receipt_id"])

    def test_ambiguous_finish_requires_candidate_after_revisions(self):
        agent = ControlledAgent(self.engine, "ambiguous",
                                candidate_id=self.candidate["id"])
        agent.state["allowed_candidates"].append("another-review-revision")
        with self.assertRaises(PackageError):
            agent.execute_actions({"action": "finish", "message": "done"})
        self.assertIsNotNone(agent.state["pending"])


if __name__ == "__main__":
    unittest.main()
