"""Tests for source-only agent actions, disposable Git drafts, and skill metadata."""
import shutil
import tempfile
import unittest
from pathlib import Path
from toad_core.controlled_agent import ControlledAgent
from toad_core.engine import Engine
from toad_core.git_drafts import GitDraft
from toad_core.schema import PackageError
from toad_core.skills import SkillCatalog, parse_skill


class ScriptedModel:
    def __init__(self, actions):
        self.actions = list(actions)
    def generate_json(self, prompt, **kwargs):
        return self.actions.pop(0)


class AgentAndSkillsTests(unittest.TestCase):
    def test_agent_restricted_actions_checkpoint_and_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(Path(folder))
            try:
                candidate = engine.ingest_text("print('hello')", name="hello-demo")
                agent = ControlledAgent(engine, "trial", candidate_id=candidate["id"], model=ScriptedModel([
                    {"action": "read_file", "candidate_id": candidate["id"], "path": "main.py"},
                    {"action": "inspect_candidate", "candidate_id": candidate["id"]},
                    {"action": "finish", "message": "done"},
                ]))
                state = agent.run("Review hello")
                self.assertEqual(state["status"], "completed")
                self.assertEqual([x["tool"] for x in state["actions"]], ["read_file", "inspect_candidate", "finish"])
                self.assertIn("hello", state["actions"][0]["observation"]["content"])
                reread = ControlledAgent(engine, "trial", model=ScriptedModel([]))
                self.assertEqual(reread.run("does not repeat"), state)
                self.assertFalse((Path(folder) / "BAD_MARKER").exists())
            finally:
                engine.close()

    def test_agent_refuses_shell_and_repeated_action(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(Path(folder))
            try:
                candidate = engine.ingest_text("print(1)", name="restriction-demo")
                agent = ControlledAgent(engine, "reject", candidate_id=candidate["id"], model=ScriptedModel([{"action": "shell", "command": "whoami"}]))
                self.assertEqual(agent.run("run commands")["status"], "blocked")
                self.assertEqual(agent.state["actions"], [])
                duplicate = ControlledAgent(engine, "again", candidate_id=candidate["id"])
                duplicate.execute_actions({"action": "finish", "message": "okay"})
                with self.assertRaises(PackageError):
                    duplicate.execute_actions({"action": "finish", "message": "okay"})
            finally:
                engine.close()

    def test_agent_edit_is_candidate_only(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(Path(folder))
            try:
                initial = engine.ingest_text("print('before')", name="safe-demo")
                model = ScriptedModel([{"action": "propose_edit", "candidate_id": initial["id"], "path": "main.py", "content": "print('after')"}])
                agent = ControlledAgent(engine, "edit", candidate_id=initial["id"], model=model)
                output = agent.step("Change greeting")
                self.assertTrue(output["candidate_id"])
                self.assertFalse(output["installed"])
                self.assertEqual(engine.get(initial["id"])["manifest"]["files"][0]["content"], "print('before')")
                self.assertEqual(engine.get(output["candidate_id"])["manifest"]["files"][0]["content"], "print('after')")
            finally:
                engine.close()

    def test_agent_edit_preserves_file_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            engine = Engine(Path(folder))
            try:
                package = {"schema": "toad-ability-v2", "name": "metadata-demo", "version": "0.1.0",
                           "entrypoint": "main.py", "dependencies": [], "permissions": [], "tests": [],
                           "files": [{"path": "main.py", "content": "value = 1\n", "extensions": {"owner": "user"}},
                                     {"path": "test_main.py", "content": "# regression\n", "extensions": {"purpose": "regression"}}]}
                initial = engine.ingest_package(package)
                agent = ControlledAgent(engine, "metadata", candidate_id=initial["id"])
                output = agent.execute_actions({"action": "propose_edit", "candidate_id": initial["id"],
                                                "path": "main.py", "content": "value = 2\n"})
                files = engine.get(output["candidate_id"])["manifest"]["files"]
                self.assertEqual(files[0]["extensions"], {"owner": "user"})
                self.assertEqual(files[1], engine.get(initial["id"])["manifest"]["files"][1])
            finally:
                engine.close()

    @unittest.skipUnless(shutil.which("git"), "git executable not installed")
    def test_git_draft_edit_diff_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            package = {"schema": "toad-ability-v2", "name": "demo", "version": "0.1.0",
                       "files": [{"path": "main.py", "content": "print('before')\n"}],
                       "entrypoint": "main.py", "permissions": [], "dependencies": [], "tests": []}
            draft = GitDraft(folder, package)
            try:
                first = draft.initial
                edited = draft.edit("main.py", "print('after')\n")
                self.assertIn("-print('before')", edited["diff"])
                self.assertEqual(draft.snapshot()[0]["content"], "print('after')\n")
                draft.rollback(first)
                self.assertEqual(draft.snapshot()[0]["content"], "print('before')\n")
                with self.assertRaises(PackageError):
                    draft.edit("../outside.py", "bad")
                with self.assertRaises(PackageError):
                    draft.rollback("deadbeef")
            finally:
                draft.close()

    def test_skills_are_quarantined_not_executable(self):
        sample = "---\nname: debugging-helper\ndescription: Teach systematic debugging\n---\nUse tests before changes."
        self.assertEqual(parse_skill(sample)["name"], "debugging-helper")
        with tempfile.TemporaryDirectory() as folder:
            catalog = SkillCatalog(folder)
            result = catalog.register(sample, kind="workflow", permissions=[], compatibility={"python": "3.11+"})
            self.assertEqual(result["status"], "quarantined")
            self.assertFalse(result["installed"])
            self.assertEqual(result["granted_permissions"], [])
            self.assertEqual(len(catalog.search("debugging")), 1)
            self.assertEqual(len(catalog.search("debugging", kind="executable")), 0)
            with self.assertRaises(ValueError):
                catalog.register(sample, kind="executable", permissions=[])
            with self.assertRaises(ValueError):
                catalog.register(sample.replace("debugging-helper", "../unsafe"), kind="knowledge", permissions=[])


if __name__ == "__main__":
    unittest.main()
