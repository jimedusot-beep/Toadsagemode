"""V4: frozen-test-guided source repair, never a host execution or release test.

The DockerWorker.run method is patched in these tests. Its reported values
simulate tests; they do NOT establish actual Docker execution or containment.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from toad_core.controlled_agent import ControlledAgent
from toad_core.engine import Engine
from toad_core.lab import DockerWorker
from toad_core.project_tools import SageProjectTools
from toad_core.project_testing import SageProjectTestGate
from toad_core.project_repair import SageRepairCoordinator
from toad_core.schema import PackageError, package_digest


def source_package():
    return {"schema": "toad-ability-v2", "name": "sage-v4-demo", "version": "0.1.0",
            "entrypoint": "src/main.py", "dependencies": [], "permissions": [], "tests": [],
            "files": [
                {"path": "src/main.py", "content": "from src.ops import add\nprint(add(1, 1))\n"},
                {"path": "src/ops.py", "content": "def add(a, b):\n    return a - b\n"},
                {"path": "README.md", "content": "# Example\n"},
            ]}


class ScriptedModel:
    def __init__(self, actions):
        self.actions = list(actions)
        self.prompts = []

    def generate_json(self, prompt, **kwargs):
        info = json.loads(prompt)
        self.prompts.append(info)
        if not self.actions:
            raise PackageError("Scripted model ran out of actions")
        action = dict(self.actions.pop(0))
        if action.pop("_use_current_revision", False):
            action["expected_revision"] = info["project_context"]["revision"]
        return action


def edit(content="def add(a, b):\n    return a + b\n"):
    return {"action": "project_propose_edit", "path": "src/ops.py", "content": content,
            "_use_current_revision": True}


def pretend_docker(_self, staged, *, cancel=None):
    """A deterministic MOCK worker result, NEVER live Docker evidence."""
    original = next(x["content"] for x in staged["files"] if x["path"] == "src/ops.py")
    correct = "return a + b" in original
    return {"backend": "docker", "digest": package_digest(staged), "executed": True,
            "passed": correct, "cleanup_ok": True, "blocked_reason": None,
            "image_id": "sha256:" + "a" * 64,
            "tests": [{"index": i, "kind": case["kind"], "path": case["path"],
                       "passed": correct, "executed": True, "cleanup_ok": True,
                       "category": "passed" if correct else "test_failure"}
                      for i, case in enumerate(staged["tests"])]}


class SageRepairTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.workspace = Path(temp.name)
        self.engine = Engine(self.workspace)
        self.addCleanup(self.engine.close)
        self.candidate = self.engine.ingest_package(source_package())
        self.candidate_id = self.candidate["id"]
        self.manifest = self.engine.get(self.candidate_id)["manifest"]
        self.project = SageProjectTools.create(self.workspace, "sage-v4-demo", self.manifest,
                                               allowed_project_ids={"sage-v4-demo"})
        self.gate = SageProjectTestGate.create(self.project, {
            "tests": [{"kind": "python", "path": "src/main.py", "expected_stdout": "2\n"}],
            "files": []})
        self.baseline = self.project.status()["revision"]

    def repair(self, model, *, session="v4-run", max_repairs=2, goal="Fix arithmetic"):  # modeled, not real inference
        runner = SageRepairCoordinator(self.engine, self.candidate_id, self.gate,
                                       model=model, max_repairs=max_repairs)
        with patch.object(DockerWorker, "run", pretend_docker):
            return runner.run(goal, session_id=session)

    def test_mocked_failure_proposes_fix_retests_and_awaits_owner(self):
        model = ScriptedModel([{"action": "project_tree"}, {"action": "project_read", "path": "src/ops.py"}, edit()])
        out = self.repair(model)
        self.assertEqual(out["status"], "tests_passed_review_required")
        self.assertEqual(out["initial_test"]["display_status"], "failed")
        self.assertEqual(out["final_test"]["display_status"], "passed")
        self.assertTrue(out["final_test"]["executed"])  # simulated trusted worker in this unit test
        self.assertFalse(out["approved"])
        self.assertFalse(out["release_allowed"])
        self.assertEqual(out["verification"], "unverified")
        self.assertTrue(out["owner_review_required"])
        self.assertNotEqual(out["final_revision"], self.baseline)
        self.assertEqual(len(out["attempts"]), 1)
        self.assertTrue(out["attempts"][0]["diff"].startswith("--- a/"))
        self.assertEqual(self.engine.get(self.candidate_id)["manifest"], self.manifest)
        self.assertEqual(self.project.read_file("src/ops.py")["content"], "def add(a, b):\n    return a + b\n")
        self.assertEqual(model.prompts[0]["allowed_actions"],
                         ["project_status", "project_tree", "project_read", "project_search", "project_propose_edit", "finish"])
        self.assertIn("test_failure", model.prompts[0]["goal"])
        self.assertNotIn("expected_stdout", model.prompts[0]["goal"])
        self.assertEqual(out["plan_digest"], self.gate.plan_digest)

    def test_two_repair_attempts_then_fixed(self):
        model = ScriptedModel([edit("def add(a, b):\n    return a * b\n"), edit()])
        out = self.repair(model, session="twostep")
        self.assertEqual(out["status"], "tests_passed_review_required")
        self.assertEqual(len(out["attempts"]), 2)
        self.assertNotEqual(out["attempts"][0]["revision_after"], out["attempts"][1]["revision_after"])

    def test_failed_after_two_attempts_never_claims_success(self):
        model = ScriptedModel([edit("def add(a, b):\n    return a * b\n"),
                               edit("def add(a, b):\n    return a // b\n")])
        out = self.repair(model, session="stillbad")
        self.assertEqual(out["status"], "repair_budget_exhausted")
        self.assertEqual(len(out["attempts"]), 2)
        self.assertEqual(out["final_test"]["display_status"], "failed")
        self.assertFalse(out["release_allowed"])

    def test_source_already_passing_skips_model(self):
        self.project.propose_edit("src/ops.py", "def add(a, b):\n    return a + b\n",
                                  expected_revision=self.baseline)
        model = ScriptedModel([])
        out = self.repair(model, session="already")
        self.assertEqual(out["status"], "already_passing_review_required")
        self.assertEqual(out["attempts"], [])
        self.assertFalse(model.prompts)

    def test_unavailable_docker_blocks_without_model_or_host_fallback(self):
        model = ScriptedModel([edit()])
        runner = SageRepairCoordinator(self.engine, self.candidate_id, self.gate, model=model)
        def unavailable(_self, stage, *, cancel=None):
            return {"backend": "docker", "digest": package_digest(stage), "executed": False,
                    "passed": False, "cleanup_ok": True, "blocked_reason": "Docker unavailable", "tests": []}
        with patch.object(DockerWorker, "run", unavailable):
            out = runner.run("Fix broken code", session_id="no-docker")
        self.assertEqual(out["status"], "test_unavailable_or_unrepairable")
        self.assertEqual(out["attempts"], [])
        self.assertEqual(self.project.status()["revision"], self.baseline)
        self.assertFalse(model.prompts)

    def test_test_double_cannot_trigger_model_or_claim_pass(self):
        class ClaimWorker:
            def run(self, stage, *, cancel=None):
                return pretend_docker(None, stage, cancel=cancel)
        model = ScriptedModel([edit()])
        runner = SageRepairCoordinator(self.engine, self.candidate_id, self.gate, model=model)
        original = self.gate.run_current
        with patch.object(SageProjectTestGate, "run_current", lambda _self, *, cancel=None: original(worker=ClaimWorker(), cancel=cancel)):
            out = runner.run("Fix code", session_id="faked")
        self.assertEqual(out["status"], "test_unavailable_or_unrepairable")
        self.assertEqual(out["initial_test"]["display_status"], "test_double_unverified")
        self.assertFalse(model.prompts)
        self.assertFalse(out["release_allowed"])

    def test_invalid_model_action_blocks_without_source_or_tests_changed(self):
        model = ScriptedModel([{"action": "shell", "command": "cat /etc/passwd"}])
        out = self.repair(model, session="bad-model")
        self.assertEqual(out["status"], "agent_blocked")
        self.assertEqual(self.project.status()["revision"], self.baseline)
        self.assertEqual(self.gate.summary()["plan_digest"], out["plan_digest"])

    def test_model_cannot_modify_frozen_test_file(self):
        model = ScriptedModel([{"action": "project_propose_edit", "path": "tests/test_math.py",
                               "content": "pass\n", "_use_current_revision": True}])
        out = self.repair(model, session="badtest")
        self.assertEqual(out["status"], "agent_blocked")
        self.assertEqual(self.project.status()["revision"], self.baseline)

    def test_finish_without_edit_returns_no_repair(self):
        out = self.repair(ScriptedModel([{"action": "finish", "message": "Nothing to fix"}]), session="noedit")
        self.assertEqual(out["status"], "no_repair_proposed")
        self.assertEqual(len(out["attempts"]), 1)
        self.assertEqual(out["attempts"][0]["outcome"], "no_edit")

    def test_repeating_same_session_is_blocked_before_test(self):
        model = ScriptedModel([edit()])
        self.repair(model, session="replay")
        previous = self.project.status()["revision"]
        next_model = ScriptedModel([])
        with self.assertRaisesRegex(PackageError, "already started"):
            self.repair(next_model, session="replay")
        self.assertEqual(self.project.status()["revision"], previous)
        self.assertFalse(next_model.prompts)

    def test_cancelled_before_first_test_does_not_invoke_model(self):
        model = ScriptedModel([edit()])
        runner = SageRepairCoordinator(self.engine, self.candidate_id, self.gate, model=model)
        result = runner.run("Fix this", session_id="cancelled", cancel=lambda: True)
        self.assertEqual(result["status"], "cancelled")
        self.assertFalse(model.prompts)
        self.assertEqual(self.project.status()["revision"], self.baseline)

    def test_stale_test_evidence_blocks_repair(self):
        runner = SageRepairCoordinator(self.engine, self.candidate_id, self.gate, model=ScriptedModel([edit()]))
        def side_effect(_self, stage, *, cancel=None):
            current = self.project.status()["revision"]
            self.project.propose_edit("README.md", "# Unexpected parallel change\n", expected_revision=current)
            return pretend_docker(_self, stage, cancel=cancel)
        with patch.object(DockerWorker, "run", side_effect):
            out = runner.run("Fix this", session_id="stale")
        self.assertEqual(out["status"], "stale_test_evidence")
        self.assertEqual(out["attempts"], [])
        self.assertNotEqual(self.project.status()["revision"], self.baseline)
        self.assertEqual(out["final_revision"], self.project.status()["revision"])

    def test_cancellation_session_claim_prevents_replay(self):
        runner = SageRepairCoordinator(self.engine, self.candidate_id, self.gate, model=ScriptedModel([]))
        out = runner.run("Fix this", session_id="cancel-once", cancel=lambda: True)
        self.assertEqual(out["status"], "cancelled")
        with self.assertRaisesRegex(PackageError, "already started"):
            runner.run("Fix this", session_id="cancel-once")

    def test_symlinked_agent_trajectory_directory_is_rejected(self):
        external = self.workspace / "outside"
        external.mkdir()
        current = self.workspace / "agent-trajectories"
        try:
            current.symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("Symlinks unavailable")
        runner = SageRepairCoordinator(self.engine, self.candidate_id, self.gate, model=ScriptedModel([]))
        with self.assertRaises(PackageError):
            runner.run("Fix this", session_id="symlinked")
        self.assertFalse((external / "sage-repair-symlinked-1.json").exists())

    def test_symlinked_session_file_is_not_overwritten(self):
        sessions = self.workspace / "sagecode-v4" / "sage-v4-demo"
        sessions.mkdir(parents=True, mode=0o700)
        external = self.workspace / "canary"
        external.write_text("SENSITIVE", encoding="utf-8")
        try:
            (sessions / "poison.json").symlink_to(external)
        except OSError:
            self.skipTest("Symlinks unavailable")
        runner = SageRepairCoordinator(self.engine, self.candidate_id, self.gate, model=ScriptedModel([]))
        with self.assertRaises(PackageError):
            runner.run("Fix", session_id="poison")
        self.assertEqual(external.read_text(encoding="utf-8"), "SENSITIVE")

    def test_resource_limit_or_cleanup_failure_never_triggers_model(self):
        model = ScriptedModel([edit()])
        runner = SageRepairCoordinator(self.engine, self.candidate_id, self.gate, model=model)
        def unclean(_self, stage, *, cancel=None):
            result = pretend_docker(_self, stage, cancel=cancel)
            result["cleanup_ok"] = False
            result["tests"][0]["category"] = "cleanup_failed"
            return result
        with patch.object(DockerWorker, "run", unclean):
            out = runner.run("Repair", session_id="unclean")
        self.assertEqual(out["status"], "test_unavailable_or_unrepairable")
        self.assertFalse(model.prompts)
        self.assertEqual(self.project.status()["revision"], self.baseline)

    def test_model_exception_does_not_expose_private_message(self):
        from toad_core.models import ModelError
        class FailingModel:
            def generate_json(self, prompt, **kwargs):
                raise ModelError("TOP-SECRET-DO-NOT-SHOW")
        out = self.repair(FailingModel(), session="model-error")
        self.assertEqual(out["status"], "agent_blocked")
        self.assertNotIn("TOP-SECRET", json.dumps(out))
        self.assertEqual(self.project.status()["revision"], self.baseline)

    def test_refuses_wrong_candidate_and_wrong_project_binding(self):
        other = source_package()
        other["files"][1]["content"] = "def add(a, b):\n    return a + b\n"
        candidate = self.engine.ingest_package(other)
        with self.assertRaises(PackageError):
            SageRepairCoordinator(self.engine, candidate["id"], self.gate)

    def test_reject_invalid_goal_session_and_budget(self):
        badbudgets = [0, 3, True, None, "2"]
        for num in badbudgets:
            with self.subTest(num=num):
                with self.assertRaises(PackageError):
                    SageRepairCoordinator(self.engine, self.candidate_id, self.gate, max_repairs=num)
        runner = SageRepairCoordinator(self.engine, self.candidate_id, self.gate)
        for bad in ("", "../bad", "a" * 41, 4, True):
            with self.subTest(bad=bad):
                with self.assertRaises(PackageError):
                    runner.run("Fix", session_id=bad)
        for bad in ("", "\ud800", "x" * 1001, "a\x00b", None):
            with self.subTest(goal=repr(bad)):
                with self.assertRaises(PackageError):
                    runner.run(bad, session_id="valid")
        self.assertEqual(self.project.status()["revision"], self.baseline)

    def test_reject_cancel_callback_that_cannot_be_called(self):
        runner = SageRepairCoordinator(self.engine, self.candidate_id, self.gate)
        with self.assertRaises(PackageError):
            runner.run("Goal", session_id="goall", cancel=True)


if __name__ == "__main__":
    unittest.main()
