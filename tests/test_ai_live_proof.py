"""No-inference contract tests for the opt-in live Ollama proof runner.

These tests DO NOT call Ollama, run generated code, or create a live
inference receipt. All positive model availability results are TEST DOUBLES.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import ai_live_proof as proof
from toad_core.models import OllamaAdapter
from toad_core.schema import PackageError
from toad_core.web_acceptance import FrozenWebAcceptance


class LiveProofTests(unittest.TestCase):
    def test_cold_status_makes_no_model_call_or_file_write(self):
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.dict(os.environ, {
                 "TOAD_MODEL_PROVIDER": "ollama",
                 "TOAD_WORKSPACE": d,
             }, clear=True), \
             mock.patch.object(OllamaAdapter, "availability",
                               side_effect=AssertionError("No model calls in cold status")), \
             mock.patch.object(FrozenWebAcceptance, "create_plan",
                               side_effect=AssertionError("No plan in cold status")):
            output = io.StringIO()
            with redirect_stdout(output):
                code = proof.main([])
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], "not_run")
            self.assertFalse(result["model_response_received"])
            self.assertFalse(result["candidate_executed"])
            self.assertFalse(result["deployed"])
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_local_probe_is_model_listing_only_and_success_is_not_inference(self):
        """A test double cannot turn model availability into a live proof."""
        with mock.patch.dict(os.environ, {
            "TOAD_MODEL_PROVIDER": "ollama",
        }, clear=True), mock.patch.object(
            OllamaAdapter, "availability",
            return_value={"available": True, "model": "test-model"},
        ) as fake_tags, mock.patch.object(
            FrozenWebAcceptance, "draft",
            side_effect=AssertionError("Probe must never generate"),
        ):
            data = proof.model_probe()
            self.assertEqual(data["status"], "model_available_not_inferred")
            self.assertTrue(data["probe_performed"])
            self.assertFalse(data["model_response_received"])
            self.assertFalse(data["candidate_executed"])
            fake_tags.assert_called_once()

    def test_paid_provider_or_paid_opt_in_blocked_even_when_run_requested(self):
        cases = (
            {"TOAD_MODEL_PROVIDER": "openai",
             "TOAD_ALLOW_REAL_OLLAMA_PROOF": "YES"},
            {"TOAD_MODEL_PROVIDER": "ollama",
             "TOAD_ALLOW_PAID_AI": "YES",
             "TOAD_ALLOW_REAL_OLLAMA_PROOF": "YES"},
        )
        for case in cases:
            with self.subTest(case=case), mock.patch.dict(
                os.environ, case, clear=True
            ), mock.patch.object(
                OllamaAdapter, "availability",
                side_effect=AssertionError("Paid path must never touch a model"),
            ):
                self.assertEqual(proof.cold_status()["model"], None)
                self.assertFalse(proof.model_probe()["probe_performed"])
                with self.assertRaisesRegex(PackageError, "Only the local"):
                    proof.run_live()

    def test_model_call_needs_explicit_live_opt_in(self):
        with mock.patch.dict(os.environ, {"TOAD_MODEL_PROVIDER": "ollama"}, clear=True), \
             mock.patch.object(OllamaAdapter, "availability",
                               side_effect=AssertionError("Must refuse before probing")):
            with self.assertRaisesRegex(PackageError, "requires TOAD_ALLOW"):
                proof.run_live()

    def test_missing_ollama_model_creates_no_source_or_plan(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {
            "TOAD_MODEL_PROVIDER": "ollama",
            "TOAD_ALLOW_REAL_OLLAMA_PROOF": "YES",
        }, clear=True), mock.patch.object(
            OllamaAdapter, "availability",
            return_value={"available": False, "model": "unavailable", "reason": "blocked"},
        ), mock.patch.object(
            FrozenWebAcceptance, "create_plan",
            side_effect=AssertionError("No freeze before preflight succeeded"),
        ):
            with self.assertRaisesRegex(PackageError, "No configured Ollama model"):
                proof.run_live(Path(d))
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_failed_live_probe_uses_nonzero_exit_and_no_success_receipt(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {
            "TOAD_MODEL_PROVIDER": "ollama",
            "TOAD_ALLOW_REAL_OLLAMA_PROOF": "YES",
        }, clear=True), mock.patch.object(
            OllamaAdapter, "availability",
            return_value={"available": False, "model": "unavailable", "reason": "sensitive log"},
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                code = proof.main(["--run", "--workspace", d])
            record = json.loads(output.getvalue())
            self.assertEqual(code, 2)
            self.assertEqual(record["status"], "blocked_no_live_proof")
            self.assertNotIn("sensitive log", output.getvalue())
            self.assertFalse(record["live_response_record_created"])
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_symlinked_private_workspace_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "real"
            target.mkdir()
            symlink = root / "linked"
            try:
                symlink.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink unavailable on this platform")
            with self.assertRaisesRegex(PackageError, "symlink"):
                proof._workspace(symlink)

    def test_unexecuted_frozen_acceptance_is_fixed_before_model_request(self):
        self.assertEqual(proof.CHECKS[0]["kind"], "title")
        self.assertEqual(proof.CHECKS[1]["kind"], "click_text")
        self.assertEqual(proof.CHECKS[1]["selector"], "#flip")
        self.assertNotIn("eval(", proof.GOAL)
        with tempfile.TemporaryDirectory() as d:
            root = proof._workspace(Path(d))
            frozen = FrozenWebAcceptance(root)
            plan = frozen.create_plan(proof.GOAL, list(proof.CHECKS))
            record = frozen.plan(plan["plan_id"])
            self.assertFalse(record["model_wrote_checks"])
            self.assertFalse(record["executed"])
            self.assertFalse(record["release_allowed"])
            self.assertFalse((root / "ai-web-drafts").exists())

    def test_sanitized_receipt_store_is_private_and_exclusive(self):
        with tempfile.TemporaryDirectory() as d:
            root = proof._workspace(Path(d))
            test_only = {"proof_id": "f" * 32, "evidence_class": "TEST_FIXTURE_NOT_LIVE"}
            receipt = proof._save_receipt(root, test_only)
            self.assertEqual(json.loads(receipt.read_text()), test_only)
            self.assertNotIn("source", receipt.read_text())
            if os.name == "posix":
                self.assertEqual(receipt.stat().st_mode & 0o077, 0)
            with self.assertRaises(FileExistsError):
                proof._save_receipt(root, test_only)


if __name__ == "__main__":
    unittest.main()
