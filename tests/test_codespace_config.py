"""Guard the optional Codespaces lab configuration against silent privilege drift.

These tests parse trusted JSON. They do not provision a Codespace, install
software, start Docker, pull a model or execute imported code.
"""
import json
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / ".devcontainer" / "devcontainer.json"


class CodespaceConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(CONFIG.read_text(encoding="utf-8"))

    def test_explicit_trusted_python_and_docker_in_docker_feature(self):
        self.assertIn("python:1-3.12-bookworm", self.config["image"])
        self.assertEqual(
            list(self.config["features"]),
            ["ghcr.io/devcontainers/features/docker-in-docker:2"],
        )
        self.assertEqual(self.config["remoteUser"], "vscode")

    def test_no_implicit_model_download_or_execution(self):
        forbidden = (
            "initializeCommand", "onCreateCommand", "updateContentCommand",
            "postCreateCommand", "postStartCommand", "postAttachCommand",
        )
        for key in forbidden:
            with self.subTest(key=key):
                self.assertNotIn(key, self.config)
        self.assertNotIn("runArgs", self.config)
        self.assertNotIn("mounts", self.config)
        self.assertNotIn("containerEnv", self.config)

    def test_ports_are_not_forwarded_by_default(self):
        self.assertEqual(self.config["forwardPorts"], [])
        self.assertEqual(
            self.config["otherPortsAttributes"]["onAutoForward"], "ignore"
        )
        self.assertNotIn("appPort", self.config)

    def test_operator_documentation_requires_real_containment(self):
        docs = (REPO / "docs" / "CODESPACES_LAB.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "python tools/lab_smoke.py --run",
            "live_verified=true",
            "python tools/broken_calculator_demo.py --run",
            "local",
            "private",
            "budget",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), docs.lower())


if __name__ == "__main__":
    unittest.main()
