"""Trusted rehearsal only: scripted agent and Docker doubles never run candidates."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toad_core.engine import Engine
from toad_core.repair_demo import BROKEN_SOURCE, FIXED_SOURCE, HOLDOUT_TESTS, fixture, run_experiment
from toad_core.schema import package_digest
from tools import broken_calculator_demo as cli


class ScriptedModel:
    def __init__(self):
        self.step = 0

    def generate_json(self, prompt, **kwargs):
        request = json.loads(prompt)
        candidates = request["allowed_candidate_ids"]
        self.step += 1
        if self.step == 1:
            return {"action": "read_file", "candidate_id": candidates[0],
                    "path": "calculator.py"}
        if self.step == 2:
            return {"action": "read_file", "candidate_id": candidates[0],
                    "path": "tests/test_calculator.py"}
        if self.step == 3:
            return {"action": "propose_edit", "candidate_id": candidates[0],
                    "path": "calculator.py", "content": FIXED_SOURCE}
        if self.step == 4:
            return {"action": "test_candidate", "candidate_id": candidates[-1]}
        if self.step == 5:
            return {"action": "finish", "candidate_id": candidates[-1],
                    "message": "Proposed correction for owner review"}
        raise AssertionError("Unexpected model call")


class WorkerDouble:
    """Synthesizes evidence for CI control flow. No candidate is executed."""

    def __init__(self, *, execute=True, always_pass=False, fail_holdout=False):
        self.calls = 0
        self.execute = execute
        self.always_pass = always_pass
        self.fail_holdout = fail_holdout

    def run(self, package, *, cancel=None):
        self.calls += 1
        code = next(x["content"] for x in package["files"]
                    if x["path"] == "calculator.py")
        passed = self.always_pass or (code == FIXED_SOURCE)
        if self.fail_holdout and any(f["path"] == "tests/test_holdout.py"
                                     for f in package["files"]):
            passed = False
        return {
            "schema": "toad-test-run-v1",
            "backend": "docker",
            "image_id": "sha256:" + "c" * 64,
            "policy": {"image": "toad-sage-lab:1", "timeout_seconds": 10,
                       "output_bytes": 64000, "memory_mb": 128,
                       "cpus": 0.5, "pids": 32, "disk_mb": 32},
            "digest": package_digest(package),
            "executed": self.execute,
            "passed": passed if self.execute else False,
            "cleanup_ok": True,
            "tests": ([{"index": 0, "kind": "unittest", "path": "tests",
                       "executed": self.execute, "cleanup_ok": True,
                       "passed": passed if self.execute else False,
                       "category": "passed" if passed else "test_failure",
                       "stderr": "" if passed else "AssertionError: 9 != 5",
                       "stdout": ""}] if self.execute else []),
        }


class FinishEarlyModel:
    def generate_json(self, prompt, **kwargs):
        original = json.loads(prompt)["allowed_candidate_ids"][0]
        return {"action": "finish", "candidate_id": original,
                "message": "Everything passes (unsubstantiated)"}


class ModifyTestsModel:
    def generate_json(self, prompt, **kwargs):
        original = json.loads(prompt)["allowed_candidate_ids"][0]
        return {"action": "propose_edit", "candidate_id": original,
                "path": "tests/test_calculator.py", "content": "pass\n"}


class RepairExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Engine(Path(self.temp.name))

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def test_fixture_is_a_deliberately_wrong_subtraction_with_frozen_tests(self):
        p = fixture()
        self.assertIn("return a + b  # Intentionally wrong", BROKEN_SOURCE)
        self.assertIn("return a - b", FIXED_SOURCE)
        self.assertEqual(p["permissions"], [])
        self.assertEqual(p["dependencies"], [])
        self.assertEqual(p["tests"], [{"kind": "unittest", "path": "tests"}])
        self.assertIn("assertRaises(ValueError)", p["files"][1]["content"])
        self.assertNotIn("test_holdout.py", str(p))
        self.assertIn("(17, 99)", HOLDOUT_TESTS)

    @unittest.skipUnless(shutil.which("git"), "Disposable candidate diffs require git")
    def test_broken_then_fixed_rehearsal_preserves_tests_and_requires_review(self):
        worker = WorkerDouble()
        report = run_experiment(self.engine, model=ScriptedModel(),
                                worker=worker, trajectory_id="calculator-rehearsal")
        self.assertEqual(worker.calls, 3)
        self.assertEqual(report["status"], "rehearsal_passed")
        self.assertEqual(report["evidence_mode"], "test_double_rehearsal")
        self.assertFalse(report["baseline"]["passed"])
        self.assertTrue(report["repair"]["passed"])
        self.assertTrue(report["holdout"]["passed"])
        self.assertTrue(report["holdout_passed"])
        self.assertEqual(report["comparison"]["status"], "comparable")
        self.assertEqual(report["comparison"]["scores"],
                         {"baseline": 0, "challenger": 1})
        self.assertTrue(report["comparison"]["owner_review_required"])
        self.assertNotEqual(report["holdout_candidate_id"], report["final_candidate_id"])
        self.assertTrue(report["baseline"]["executed"])
        self.assertEqual(report["baseline"]["test_categories"], ["test_failure"])
        self.assertEqual(report["agent_status"], "awaiting_review")
        self.assertEqual(report["agent_actions"],
                         ["read_file", "read_file", "propose_edit", "test_candidate", "finish"])
        self.assertEqual(report["changed_paths"], ["calculator.py"])
        self.assertTrue(report["tests_unchanged"])
        self.assertNotEqual(report["original_digest"], report["final_digest"])
        self.assertNotEqual(report["original_candidate_id"], report["final_candidate_id"])
        self.assertTrue(report["owner_review_required"])
        self.assertFalse(report["installation_performed"])
        self.assertFalse(report["deployment_performed"])
        self.assertIn("NOT real Docker", report["reason"])
        self.assertIn("-    return a + b", report["proposed_diff"])
        self.assertFalse(any(x["installed"] for x in self.engine.list()))

    @unittest.skipUnless(shutil.which("git"), "Disposable candidate diffs require git")
    def test_separate_holdout_rejects_a_superficially_passing_patch(self):
        worker = WorkerDouble(fail_holdout=True)
        report = run_experiment(self.engine, model=ScriptedModel(),
                                worker=worker, trajectory_id="failed-holdout")
        self.assertEqual(worker.calls, 3)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(report["repair"]["passed"])
        self.assertFalse(report["holdout"]["passed"])
        self.assertIn("Independent holdout", report["reason"])
        self.assertFalse(report["installation_performed"])

    def test_missing_execution_blocks_before_any_model_action(self):
        model = ScriptedModel()
        worker = WorkerDouble(execute=False)
        report = run_experiment(self.engine, model=model, worker=worker,
                                trajectory_id="no-execution")
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(worker.calls, 1)
        self.assertEqual(model.step, 0)
        self.assertFalse(report["baseline"]["executed"])
        self.assertIsNone(report["repair"])

    def test_already_passing_fixture_does_not_trigger_repair(self):
        report = run_experiment(self.engine, model=ScriptedModel(),
                                worker=WorkerDouble(always_pass=True),
                                trajectory_id="no-original-bug")
        self.assertEqual(report["status"], "blocked")
        self.assertIn("not proven", report["reason"])

    def test_model_cannot_finish_failing_original_as_verified(self):
        report = run_experiment(self.engine, model=FinishEarlyModel(),
                                worker=WorkerDouble(),
                                trajectory_id="premature-finish")
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["agent_status"], "awaiting_review")
        self.assertEqual(report["agent_actions"], ["finish"])
        self.assertNotIn("final_candidate_id", report)

    @unittest.skipUnless(shutil.which("git"), "Disposable candidate diffs require git")
    def test_model_cannot_change_frozen_test_file(self):
        report = run_experiment(self.engine, model=ModifyTestsModel(),
                                worker=WorkerDouble(),
                                trajectory_id="frozen-tests")
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["agent_status"], "blocked")
        self.assertIsNone(report["repair"])


class DemoCliTests(unittest.TestCase):
    def test_preflight_never_runs_worker_or_candidate(self):
        status = {"capabilities": {"missions": "blocked", "library": "ready"}}
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(cli, "readiness", return_value=status), \
                patch.object(cli, "run_probes") as smoke, \
                patch.object(cli, "run_experiment") as experiment:
            self.assertEqual(cli.main(["--workspace", temp]), 0)
            smoke.assert_not_called()
            experiment.assert_not_called()

    def test_run_blocks_missing_prerequisites_without_smoke(self):
        status = {"capabilities": {"missions": "blocked", "library": "ready"}}
        with tempfile.TemporaryDirectory() as temp, \
                patch.object(cli, "readiness", return_value=status), \
                patch.object(cli, "run_probes") as smoke, \
                patch.object(cli, "run_experiment") as experiment:
            self.assertEqual(cli.main(["--run", "--workspace", temp]), 2)
            smoke.assert_not_called()
            experiment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
