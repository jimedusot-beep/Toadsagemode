"""V5 trial tests. No test runs a real container or invokes a model.

All external readiness, containment, and coordinator paths are mocked when
exercising the explicit --run CLI. No test outcome is live hardware evidence.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import sagecode_live_trial as live
from toad_core.project_tools import SageProjectTools
from toad_core.project_testing import SageProjectTestGate
from toad_core.schema import PackageError


PROBES = ("hello", "host_files", "root_write", "network", "timeout", "output", "memory", "disk", "processes")


def fake_smoke(*, omit=None, fail=None):
    return {"live_verified": True, "results": [
        {"probe": name, "restriction_observed": name != fail, "run": {"stdout": "PRIVATE-DO-NOT-LEAK"}}
        for name in PROBES if name != omit
    ]}


def output_of(*args):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        result = live.main(list(args))
    return result, json.loads(stream.getvalue())


class SageCodeLiveTrialTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_fixture_has_broken_addition_and_independent_unittest(self):
        package = live.source_fixture()
        plan = live.frozen_acceptance()
        self.assertIn("return a - b", package["files"][1]["content"])
        self.assertEqual(package["permissions"], [])
        self.assertEqual(package["dependencies"], [])
        self.assertEqual(package["tests"], [])
        self.assertEqual(plan["tests"], [{"kind": "unittest", "path": "tests"}])
        assert_names = ("test_positive", "test_negative", "test_zero", "test_fractional")
        for name in assert_names:
            self.assertIn("def " + name, plan["files"][0]["content"])
        self.assertNotIn("tests/test_addition.py", {x["path"] for x in package["files"]})

    def test_frozen_acceptance_integrates_with_real_v3_test_gate(self):
        project = SageProjectTools.create(self.root, "trial-demo", live.source_fixture(),
                                          allowed_project_ids={"trial-demo"})
        gate = SageProjectTestGate.create(project, live.frozen_acceptance())
        self.assertEqual(gate.summary()["test_count"], 1)
        self.assertFalse(gate.summary()["release_allowed"])
        self.assertEqual(gate.plan["files"][0]["path"], "tests/test_addition.py")
        self.assertFalse(any(x["path"].startswith("tests/") for x in project._current()["manifest"]["files"]))

    def test_smoke_summary_requires_all_nine_named_probes(self):
        value = live._smoke_summary(fake_smoke())
        self.assertTrue(value["live_verified"])
        self.assertEqual(len(value["probes"]), 9)
        self.assertNotIn("PRIVATE-DO-NOT-LEAK", json.dumps(value))
        for bad in (fake_smoke(omit="memory"), fake_smoke(fail="network"),
                    {"live_verified": False, "results": fake_smoke()["results"]},
                    {"live_verified": True, "results": []}, "bad", None):
            with self.subTest(bad=str(bad)[:45]):
                self.assertFalse(live._smoke_summary(bad)["live_verified"])

    def test_smoke_summary_rejects_duplicate_or_unexpected_probes(self):
        dups = fake_smoke()
        dups["results"][1] = dict(dups["results"][0])
        self.assertFalse(live._smoke_summary(dups)["live_verified"])
        additional = fake_smoke()
        additional["results"].append({"probe": "other", "restriction_observed": True})
        self.assertFalse(live._smoke_summary(additional)["live_verified"])

    def test_report_is_private_and_cannot_overwrite_previous_record(self):
        path = Path(live._write_private_report(self.root, "a" * 16, "trial", {"a": 3}))
        self.assertEqual(json.loads(path.read_text()), {"a": 3})
        self.assertEqual(path.stat().st_mode & 0o077, 0)
        self.assertEqual(path.parent.stat().st_mode & 0o077, 0)
        with self.assertRaises(PackageError):
            live._write_private_report(self.root, "a" * 16, "trial", {"a": 4})
        self.assertEqual(json.loads(path.read_text()), {"a": 3})

    def test_report_refuses_symlinked_output_folder(self):
        external = self.root / "outside"
        external.mkdir()
        link = self.root / "sagecode-live-reports"
        try:
            link.symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("Cannot create symlinks")
        with self.assertRaises(PackageError):
            live._write_private_report(self.root, "a" * 16, "trial", {"a": 1})
        self.assertEqual(list(external.iterdir()), [])

    def test_report_refuses_bad_identity_and_large_records(self):
        for key, label in (("../", "trial"), ("a" * 17, "trial"), ("A" * 16, "trial"),
                           ("a" * 16, "unexpected")):
            with self.subTest(key=key, label=label), self.assertRaises(PackageError):
                live._write_private_report(self.root, key, label, {})
        with self.assertRaises(PackageError):
            live._write_private_report(self.root, "b" * 16, "trial", {"large": "x" * 260000})
        self.assertFalse((self.root / "sagecode-live-reports" / ("trial-" + "b" * 16 + ".json")).exists())

    def test_default_never_probes_or_executes(self):
        with patch.object(live, "readiness", return_value={"capabilities": {"missions": "not_checked"}}) as doctor, \
             patch.object(live, "run_probes") as smoke, \
             patch.object(live.SageRepairCoordinator, "run") as repair:
            status, data = output_of("--workspace", str(self.root))
        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "not_run")
        self.assertFalse(data["execution_performed"])
        self.assertFalse(data["containment_verified"])
        doctor.assert_called_once_with(self.root, probe=False)
        smoke.assert_not_called()
        repair.assert_not_called()

    def test_check_is_metadata_only_even_when_missions_ready(self):
        with patch.object(live, "readiness", return_value={"capabilities": {"missions": "ready"}}) as doctor, \
             patch.object(live, "run_probes") as smoke, \
             patch.object(live.SageRepairCoordinator, "run") as repair:
            status, data = output_of("--check", "--workspace", str(self.root))
        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "metadata_ready")
        doctor.assert_called_once_with(self.root, probe=True)
        smoke.assert_not_called()
        repair.assert_not_called()

    def test_missing_lab_or_model_blocks_before_smoke_and_project_creation(self):
        with patch.object(live, "readiness", return_value={"capabilities": {"missions": "blocked"}}), \
             patch.object(live, "run_probes") as smoke, \
             patch.object(live.SageRepairCoordinator, "run") as repair:
            status, data = output_of("--run", "--workspace", str(self.root))
        self.assertEqual(status, 2)
        self.assertEqual(data["status"], "blocked")
        self.assertFalse(data["execution_performed"])
        smoke.assert_not_called()
        repair.assert_not_called()
        self.assertFalse((self.root / "sagecode-v1").exists())

    def test_failed_smoke_blocks_before_ever_asking_model(self):
        with patch.object(live, "readiness", return_value={"capabilities": {"missions": "ready"}}), \
             patch.object(live, "run_probes", return_value=fake_smoke(fail="disk")), \
             patch.object(live.SageRepairCoordinator, "run") as repair:
            status, data = output_of("--run", "--workspace", str(self.root))
        self.assertEqual(status, 2)
        self.assertIn("containment", data["reason"].lower())
        repair.assert_not_called()
        self.assertFalse((self.root / "sagecode-v1").exists())

    def test_simulated_run_wires_existing_controller_without_claiming_approval(self):
        # SIMULATION: run() is patched; this test does not run Ollama or Docker.
        response = {"status": "tests_passed_review_required", "attempts": [{"attempt": 1}],
                    "verification": "unverified", "approved": False, "release_allowed": False}
        with patch.object(live, "readiness", return_value={"capabilities": {"missions": "ready"}}), \
             patch.object(live, "run_probes", return_value=fake_smoke()), \
             patch.object(live.SageRepairCoordinator, "run", return_value=response) as repair:
            status, data = output_of("--run", "--workspace", str(self.root))
        self.assertEqual(status, 0)
        self.assertEqual(data["status"], "tests_passed_review_required")
        self.assertEqual(data["repairs"], 1)
        self.assertFalse(data["approved"])
        self.assertFalse(data["release_allowed"])
        self.assertTrue(data["owner_review_required"])
        repair.assert_called_once()
        details = json.loads(Path(data["trial_report"]).read_text())
        self.assertEqual(details["repair_report"], response)
        self.assertEqual(details["live_containment_preflight"], True)  # mocked in this test only
        self.assertEqual(details["approved"], False)
        self.assertIn("sagecode-live-reports", data["trial_report"])
        self.assertEqual(len(list((self.root / "sagecode-v1").iterdir())), 1)
        self.assertEqual(len(list((self.root / "sagecode-v3").iterdir())), 1)

    def test_simulated_failed_repair_returns_nonzero(self):
        response = {"status": "repair_budget_exhausted", "attempts": [], "verification": "unverified"}
        with patch.object(live, "readiness", return_value={"capabilities": {"missions": "ready"}}), \
             patch.object(live, "run_probes", return_value=fake_smoke()), \
             patch.object(live.SageRepairCoordinator, "run", return_value=response):
            status, data = output_of("--run", "--workspace", str(self.root))
        self.assertEqual(status, 3)
        self.assertEqual(data["status"], "repair_budget_exhausted")
        self.assertFalse(data["approved"])

    def test_workspace_symlink_is_rejected(self):
        target = self.root / "target"
        target.mkdir()
        link = self.root / "link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            self.skipTest("Symlinks unavailable")
        with self.assertRaises(SystemExit):
            live.main(["--workspace", str(link)])


if __name__ == "__main__":
    unittest.main()
