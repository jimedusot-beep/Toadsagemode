"""Offline regression tests for the OpenCode V2 starter; NOT a live agent test."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import opencode_v2_starter as starter


class OpenCodeStarterTests(unittest.TestCase):
    def setUp(self):
        self.original = starter.validate_config()

    def write_changed(self, transform):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "opencode.jsonc"
            copy = json.loads(json.dumps(self.original))
            transform(copy)
            path.write_text(json.dumps(copy), encoding="utf-8")
            with self.assertRaises((ValueError, KeyError, TypeError)):
                starter.validate_config(path)

    def test_reviewed_policy_passes(self):
        self.assertEqual(starter.validate_config(), self.original)

    def test_unexpected_config_field_fails(self):
        self.write_changed(lambda d: d.update({"model": "unapproved/paid"}))

    def test_missing_deny_fails(self):
        self.write_changed(lambda d: d["permissions"].pop(9))

    def test_secret_edit_cannot_be_overridden_by_wildcard_ask(self):
        def reorder(d):
            rules = d["permissions"]
            wildcard = next(r for r in rules if r == {"action": "edit", "resource": "*", "effect": "ask"})
            rules.remove(wildcard)
            rules.append(wildcard)
        self.write_changed(reorder)

    def test_missing_hard_policy_fails(self):
        self.write_changed(lambda d: d["policies"].pop(9))

    def test_unapproved_provider_fails(self):
        self.write_changed(lambda d: d["policies"].append(
            {"action": "provider.use", "resource": "anthropic", "effect": "allow"}))

    def test_no_hidden_extra_tool_permission(self):
        self.write_changed(lambda d: d["permissions"].append(
            {"action": "shell", "resource": "*", "effect": "allow"}))

    def test_invalid_schema_fails(self):
        self.write_changed(lambda d: d.update({"$schema": "bad"}))

    def test_pinned_release_is_exact_v2(self):
        self.assertEqual(starter.pinned_version(), "2.3.2")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "pin.txt"
            path.write_text("latest", encoding="utf-8")
            with self.assertRaises(ValueError):
                starter.pinned_version(path)

    def test_missing_executable_fails(self):
        with patch.object(starter.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "missing"):
                starter.verify_binary("2.3.2")

    def test_wrong_binary_version_fails(self):
        bad = subprocess.CompletedProcess(["opencode", "--version"], 0, "2.2.7\n", "")
        with patch.object(starter.subprocess, "run", return_value=bad):
            with self.assertRaisesRegex(RuntimeError, "Expected"):
                starter.verify_binary("2.3.2", "/tmp/mock-opencode")

    def test_exact_binary_version_passes(self):
        good = subprocess.CompletedProcess(["opencode", "--version"], 0, "opencode 2.3.2\n", "")
        with patch.object(starter.subprocess, "run", return_value=good) as run:
            self.assertEqual(starter.verify_binary("2.3.2", "/tmp/mock-opencode"), "/tmp/mock-opencode")
            run.assert_called_once()

    def test_version_check_timeout_fails_closed(self):
        with patch.object(starter.subprocess, "run", side_effect=subprocess.TimeoutExpired("x", 15)):
            with self.assertRaises(subprocess.TimeoutExpired):
                starter.verify_binary("2.3.2", "/tmp/mock-opencode")

    def test_child_environment_discards_inherited_secrets(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "must-not-leak",
                                     "GITHUB_TOKEN": "must-not-leak",
                                     "PATH": "/usr/bin"}):
            env = starter.isolated_environment(Path("/tmp/disposable-home"))
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("GITHUB_TOKEN", env)
        self.assertEqual(env["HOME"], "/tmp/disposable-home")

    def test_launch_has_private_home_and_standalone_flag(self):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d) / "session"
            directory.mkdir()
            with patch.object(starter.tempfile, "mkdtemp", return_value=str(directory)):
                with patch.object(starter.subprocess, "call", return_value=0) as call:
                    self.assertEqual(starter.launch("/tmp/fake-opencode"), 0)
            args, kwargs = call.call_args
            self.assertEqual(args[0], ["/tmp/fake-opencode", "--standalone"])
            self.assertEqual(kwargs["cwd"], directory / "project")
            self.assertEqual(kwargs["env"]["HOME"], str(directory / "home"))
            self.assertEqual((directory / "project" / "opencode.jsonc").read_bytes(),
                             starter.CONFIG.read_bytes())

    def test_offline_validation_does_not_launch_binary(self):
        with patch.object(starter, "verify_binary", side_effect=AssertionError("binary touched")):
            self.assertEqual(starter.main(["--validate-config"]), 0)

    def test_main_blocks_failed_version_check(self):
        with patch.object(starter, "verify_binary", side_effect=RuntimeError("bad version")):
            self.assertEqual(starter.main(["--check"]), 2)


if __name__ == "__main__":
    unittest.main()
