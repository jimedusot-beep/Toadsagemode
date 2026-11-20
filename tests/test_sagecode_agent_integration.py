"""SageCode V2 integrates source-only tools into the existing ControlledAgent."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from toad_core.controlled_agent import ControlledAgent
from toad_core.engine import Engine
from toad_core.project_tools import SageProjectTools
from toad_core.schema import PackageError


def source_package():
    return {"schema": "toad-ability-v2", "name": "sagecode-example", "version": "0.1.0",
            "entrypoint": "src/main.py", "permissions": [], "dependencies": [], "tests": [],
            "files": [{"path": "src/main.py", "content": "print('hello')\n"},
                      {"path": "README.md", "content": "# Demo\n"}]}


class ScriptedModel:
    def __init__(self, actions):
        self.actions = list(actions)
        self.prompts = []

    def generate_json(self, prompt, **kwargs):
        self.prompts.append(json.loads(prompt))
        return self.actions.pop(0)


class SageCodeAgentIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.engine = Engine(self.root)
        self.addCleanup(self.engine.close)
        self.candidate = self.engine.ingest_package(source_package())
        self.candidate_id = self.candidate["id"]
        self.manifest = self.engine.get(self.candidate_id)["manifest"]
        self.project = SageProjectTools.create(self.root, "sagecode-example", self.manifest,
                                                allowed_project_ids={"sagecode-example"})
        self.baseline = self.project.status()["revision"]

    def test_model_uses_project_actions_in_existing_bounded_loop(self):
        scripted = ScriptedModel([
            {"action": "project_status"},
            {"action": "project_tree"},
            {"action": "project_read", "path": "src/main.py"},
            {"action": "project_search", "term": "hello"},
            {"action": "project_propose_edit", "path": "src/main.py",
             "content": "print('updated')\n", "expected_revision": self.baseline},
            {"action": "finish", "message": "Source update ready for review"},
        ])
        agent = ControlledAgent(self.engine, "sage-v2", candidate_id=self.candidate_id,
                                project_tools=self.project, model=scripted)
        state = agent.run("Update a greeting")
        self.assertEqual(state["status"], "awaiting_review")
        self.assertEqual(state["verification"], "unverified")
        self.assertEqual(len(state["actions"]), 6)
        self.assertEqual([x["tool"] for x in state["actions"]],
                         ["project_status", "project_tree", "project_read", "project_search",
                          "project_propose_edit", "finish"])
        result = state["actions"][-1]["observation"]
        self.assertTrue(result["owner_review_required"])
        self.assertEqual(result["project_id"], "sagecode-example")
        self.assertEqual(result["project_revision"], self.project.status()["revision"])
        self.assertEqual(result["project_verification"], "unverified")
        self.assertFalse(result["release_allowed"])
        self.assertFalse(result["installed"])
        self.assertEqual(self.engine.get(self.candidate_id)["manifest"], self.manifest)
        self.assertIn("updated", self.project.read_file("src/main.py")["content"])
        prompt = scripted.prompts[0]
        self.assertEqual(prompt["project_context"]["project_id"], "sagecode-example")
        self.assertIn("project_propose_edit", prompt["allowed_actions"])
        self.assertNotIn("shell", prompt["allowed_actions"])

    def test_unbound_candidate_agent_cannot_select_project_tools(self):
        agent = ControlledAgent(self.engine, "plain-v2", candidate_id=self.candidate_id,
                                model=ScriptedModel([]))
        self.assertNotIn("project_tree", agent._allowed_actions())
        with self.assertRaises(PackageError):
            agent.execute_actions({"action": "project_tree"})
        self.assertEqual(agent.state["actions"], [])
        self.assertEqual(agent.state["status"], "ready")

    def test_reopening_requires_exact_trusted_binding(self):
        ControlledAgent(self.engine, "bound-v2", candidate_id=self.candidate_id,
                        project_tools=self.project, model=ScriptedModel([]))
        with self.assertRaisesRegex(PackageError, "requires trusted project"):
            ControlledAgent(self.engine, "bound-v2", model=ScriptedModel([]))
        restored = ControlledAgent(self.engine, "bound-v2", project_tools=self.project, model=ScriptedModel([]))
        self.assertIn("project_tree", restored._allowed_actions())
        second = SageProjectTools.create(self.root, "another-project", self.manifest,
                                         allowed_project_ids={"another-project"})
        with self.assertRaisesRegex(PackageError, "binding changed"):
            ControlledAgent(self.engine, "bound-v2", project_tools=second, model=ScriptedModel([]))
        with self.assertRaises(PackageError):
            ControlledAgent(self.engine, "bound-v2", candidate_id="forged", project_tools=self.project,
                            model=ScriptedModel([]))
        with self.assertRaisesRegex(PackageError, "Cannot attach"):
            self._create_plain_and_bind()

    def _create_plain_and_bind(self):
        ControlledAgent(self.engine, "plain-bind", candidate_id=self.candidate_id, model=ScriptedModel([]))
        return ControlledAgent(self.engine, "plain-bind", project_tools=self.project, model=ScriptedModel([]))

    def test_mismatched_project_baseline_blocks_session_creation(self):
        other = self.engine.ingest_package({**source_package(), "version": "0.2.0"})
        with self.assertRaisesRegex(PackageError, "baseline"):
            ControlledAgent(self.engine, "mismatched", candidate_id=other["id"],
                            project_tools=self.project, model=ScriptedModel([]))
        self.assertFalse((self.root / "agent-trajectories" / "mismatched.json").exists())

    def test_model_cannot_request_restore_shell_approval_or_policy_changes(self):
        for i, action in enumerate((
            {"action": "project_restore", "revision": self.baseline},
            {"action": "shell", "command": "id"},
            {"action": "project_read", "path": "README.md", "policy": "write"},
            {"action": "project_status", "project_id": "other-project"},
        )):
            with self.subTest(action=action):
                agent = ControlledAgent(self.engine, f"bad-{i}", candidate_id=self.candidate_id,
                                        project_tools=self.project, model=ScriptedModel([action]))
                result = agent.run("unsafe request")
                self.assertEqual(result["status"], "blocked")
                self.assertNotEqual(result.get("verification"), "verified")
        self.assertEqual(self.project.status()["revision"], self.baseline)

    def test_stale_expected_revision_fails_closed_and_changes_no_source(self):
        agent = ControlledAgent(self.engine, "stale-v2", candidate_id=self.candidate_id,
                                project_tools=self.project, model=ScriptedModel([
                                    {"action": "project_propose_edit", "path": "README.md", "content": "bad\n", "expected_revision": "a"*64}
                                ]))
        self.assertEqual(agent.run("edit")["status"], "blocked")
        self.assertEqual(self.project.status()["revision"], self.baseline)
        self.assertEqual(self.engine.get(self.candidate_id)["manifest"], self.manifest)

    def test_pending_checkpoint_is_not_replayed_after_restart(self):
        agent = ControlledAgent(self.engine, "pending-v2", candidate_id=self.candidate_id,
                                project_tools=self.project, model=ScriptedModel([]))
        agent.state["pending"] = {"tool": "project_propose_edit", "action_hash": "abc"}
        agent._save()
        resumed = ControlledAgent(self.engine, "pending-v2", project_tools=self.project, model=ScriptedModel([]))
        state = resumed.run("resume")
        self.assertEqual(state["status"], "blocked")
        self.assertIn("no automatic replay", state["blocked_reason"])
        self.assertEqual(self.project.status()["revision"], self.baseline)

    def test_rejects_surrogates_in_model_action_before_checkpoint(self):
        agent = ControlledAgent(self.engine, "surrogate-v2", candidate_id=self.candidate_id,
                                project_tools=self.project, model=ScriptedModel([
                                    {"action": "project_search", "term": "\ud800"}
                                ]))
        result = agent.run("find term")
        self.assertEqual(result["status"], "blocked")
        self.assertNotEqual(result.get("verification"), "verified")
        self.assertEqual(self.project.status()["revision"], self.baseline)


if __name__ == "__main__":
    unittest.main()
