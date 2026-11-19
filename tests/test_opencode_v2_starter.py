"""Static preflight regression tests. These do NOT exercise a live OpenCode agent."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "opencode_v2_starter.py"
spec = importlib.util.spec_from_file_location("opencode_v2_starter", SCRIPT)
starter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(starter)


class StarterTests(unittest.TestCase):
    def _modified(self, change):
        data = json.loads(starter.CONFIG.read_text(encoding="utf-8"))
        change(data)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.jsonc"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                starter.check_config(path)

    def test_config_is_valid(self):
        starter.check_config()

    def test_final_broad_edit_rule_fails_closed(self):
        self._modified(lambda data: data["permissions"].append(
            {"action": "edit", "resource": "*", "effect": "allow"}))

    def test_removed_secret_deny_fails_closed(self):
        self._modified(lambda data: data["permissions"].pop())

    def test_removed_external_deny_fails_closed(self):
        self._modified(lambda data: data["permissions"].pop(10))

    def test_broad_provider_allow_fails_closed(self):
        self._modified(lambda data: data["policies"].append(
            {"action": "provider.use", "resource": "*", "effect": "allow"}))

    def test_removed_policy_deny_fails_closed(self):
        self._modified(lambda data: data["policies"].pop(5))

    def test_unexpected_config_key_fails_closed(self):
        self._modified(lambda data: data.update({"plugins": ["unapproved-plugin"]}))

    def test_unapproved_paid_model_fails_closed(self):
        self._modified(lambda data: data.update({"model": "opencode/paid-model"}))

    def test_version_pin_success(self):
        with patch.object(starter.subprocess, "run") as run:
            run.return_value.stdout = "opencode 2.3.2\n"
            self.assertEqual(starter.installed_version("/bin/opencode", "2.3.2"), "opencode 2.3.2")

    def test_version_mismatch(self):
        with patch.object(starter.subprocess, "run") as run:
            run.return_value.stdout = "2.3.3\n"
            with self.assertRaises(RuntimeError):
                starter.installed_version("/bin/opencode", "2.3.2")

    def test_old_version_rejected_before_executing(self):
        with patch.object(starter.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                starter.installed_version("/bin/opencode", "2.2.5")
            run.assert_not_called()

    def test_environment_strips_api_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(starter.os.environ, {"OPENAI_API_KEY": "secret", "GH_TOKEN": "secret"}):
                env = starter.clean_environment(Path(folder))
                self.assertNotIn("OPENAI_API_KEY", env)
                self.assertNotIn("GH_TOKEN", env)
                self.assertEqual(env["HOME"], str(Path(folder) / "home"))

    def test_launch_requires_binary(self):
        with patch.object(starter.shutil, "which", return_value=None):
            with self.assertRaises(RuntimeError):
                starter.launch("2.3.2", starter.FREE_MODEL_CANDIDATES[0])

    def test_launch_blocks_paid_model(self):
        with self.assertRaises(ValueError):
            starter.launch("2.3.2", "opencode/paid-model")

    def test_launch_runs_mini_with_isolated_home(self):
        with patch.object(starter.shutil, "which", return_value="/bin/opencode"), \
             patch.object(starter, "installed_version", return_value="2.3.2"), \
             patch.object(starter.subprocess, "call", return_value=0) as call:
            self.assertEqual(starter.launch("2.3.2", starter.FREE_MODEL_CANDIDATES[0]), 0)
            kwargs = call.call_args.kwargs
            command = call.call_args.args[0]
            self.assertEqual(command[:3], ["/bin/opencode", "mini", "--standalone"])
            self.assertEqual(command[-1], starter.FREE_MODEL_CANDIDATES[0])
            self.assertTrue((kwargs["cwd"] / "opencode.jsonc").exists())
            self.assertTrue((kwargs["cwd"] / "CALCULATOR_MISSION.md").exists())
            self.assertTrue((kwargs["cwd"] / "calculator-acceptance.test.mjs").exists())
            self.assertTrue(str(kwargs["cwd"]).startswith("/tmp/"))
            self.assertNotIn("OPENAI_API_KEY", kwargs["env"])

    def test_check_pinned_version_calls_binary(self):
        with patch.object(starter.shutil, "which", return_value="/bin/opencode"), \
             patch.object(starter, "installed_version", return_value="2.3.2") as verify:
            self.assertEqual(starter.main(["--check", "--expected-version", "2.3.2"]), 0)
            verify.assert_called_once_with("/bin/opencode", "2.3.2")


if __name__ == "__main__":
    unittest.main()
