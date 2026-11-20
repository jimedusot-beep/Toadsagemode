"""Owner-invoked SageCode V5 live repair trial (local Docker + loopback Ollama).

Default execution is a NO-EXECUTION status report. ``--check`` probes only
metadata. ``--run`` requires live Docker containment probes before staging
one known, deliberately broken calculator project. No public API, shell agent,
paid provider or automatic approval path is created by this script.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toad_core.engine import Engine, default_workspace
from toad_core.project_tools import SageProjectTools, _is_private_dir
from toad_core.project_testing import SageProjectTestGate
from toad_core.project_repair import SageRepairCoordinator
from toad_core.readiness import readiness
from toad_core.schema import PackageError
from tools.lab_smoke import run_probes


# This source is hand-authored, not from the model. It is the only source the
# opt-in CLI is willing to submit to the local worker.
BROKEN_SOURCE = """def add(a, b):
    return a - b  # deliberate test defect
"""
FROZEN_TEST_SOURCE = """import unittest
from src.ops import add

class AdditionAcceptance(unittest.TestCase):
    def test_positive(self):
        self.assertEqual(add(9, 4), 13)
        self.assertEqual(add(1, 1), 2)

    def test_negative(self):
        self.assertEqual(add(-5, -2), -7)
        self.assertEqual(add(-5, 2), -3)

    def test_zero(self):
        self.assertEqual(add(0, 0), 0)
        self.assertEqual(add(8, 0), 8)

    def test_fractional(self):
        self.assertEqual(add(0.25, 0.5), 0.75)
"""


def source_fixture():
    return {
        "schema": "toad-ability-v2", "name": "sagecode-live-addition", "version": "0.1.0",
        "description": "Deliberately incorrect addition to exercise a bounded repair trial",
        "entrypoint": "src/main.py", "permissions": [], "dependencies": [], "tests": [],
        "files": [
            {"path": "src/main.py", "content": "from src.ops import add\nprint(add(9, 4))\n"},
            {"path": "src/ops.py", "content": BROKEN_SOURCE},
            {"path": "README.md", "content": "# Local SageCode V5 repair trial (source-only)\n"},
        ],
    }


def frozen_acceptance():
    return {
        "tests": [{"kind": "unittest", "path": "tests"}],
        "files": [{"path": "tests/test_addition.py", "content": FROZEN_TEST_SOURCE}],
    }


def _write_private_report(workspace, report_id, label, value):
    """Persist local report without overwriting old evidence or following links."""
    if not re.fullmatch(r"[a-f0-9]{16}", report_id) or label not in ("containment", "trial"):
        raise PackageError("Invalid evidence record identifier")
    workspace = Path(workspace)
    _is_private_dir(workspace)
    dest = workspace / "sagecode-live-reports"
    if not dest.exists():
        dest.mkdir(mode=0o700)
    _is_private_dir(dest)
    path = dest / (label + "-" + report_id + ".json")
    data = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False).encode("utf-8") + b"\n"
    if len(data) > 256_000:
        raise PackageError("Local report exceeds 256 KB")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise PackageError("Cannot safely save private trial record") from exc
    return str(path)


def _smoke_summary(raw):
    """Use only established containment probe identities and boolean outcomes."""
    if not isinstance(raw, dict) or not isinstance(raw.get("results"), list):
        return {"live_verified": False, "probes": [], "reason": "Invalid smoke result"}
    probes = [{"probe": str(x.get("probe", ""))[:40],
               "restriction_observed": x.get("restriction_observed") is True}
              for x in raw["results"][:20] if isinstance(x, dict)]
    expected = {"hello", "host_files", "root_write", "network", "timeout", "output", "memory", "disk", "processes"}
    observed = {x["probe"] for x in probes}
    good = (raw.get("live_verified") is True and observed == expected
            and len(probes) == len(expected) and all(x["restriction_observed"] for x in probes))
    return {"live_verified": good, "probes": probes,
            "reason": None if good else "Containment probes incomplete or failed"}


def _default_workspace():
    return default_workspace() / "experiments" / "sagecode-live-v5"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Trusted owner-only SageCode local repair trial")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Probe only local Docker/Ollama metadata; never run source")
    group.add_argument("--run", action="store_true", help="Run local containment probes and a known repair fixture")
    parser.add_argument("--workspace", help="Private local workspace (not an app source directory)")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace).expanduser() if args.workspace else _default_workspace()
    if workspace.is_symlink():
        parser.error("Workspace must not be a symlink")
    # Doctor opens the private catalog but never runs submitted source. No
    # inference is attempted unless --run is supplied and all checks pass.
    try:
        diagnostic = readiness(workspace, probe=args.check or args.run)
        capabilities = diagnostic["capabilities"]
        if not args.run:
            print(json.dumps({"schema": "sagecode-live-trial-status-v1", "execution_performed": False,
                              "status": "metadata_ready" if args.check and capabilities["missions"] == "ready" else "not_run",
                              "capabilities": capabilities,
                              "containment_verified": False,
                              "next": "Review docs/SAGECODE_V5_LIVE_TRIAL.md; --run requires approved local Docker and Ollama."}, indent=2))
            return 0
        if capabilities["missions"] != "ready":
            print(json.dumps({"status": "blocked", "execution_performed": False,
                              "reason": "Required local Docker lab and loopback Ollama model are not ready.",
                              "capabilities": capabilities}, indent=2))
            return 2
        smoke = _smoke_summary(run_probes())
        if not smoke["live_verified"]:
            print(json.dumps({"status": "blocked", "execution_performed": False,
                              "reason": "Live containment checks failed or were incomplete.",
                              "containment": smoke}, indent=2))
            return 2
        # Storage is private, and both evidence and source snapshots remain on
        # the owner's local host. Unique IDs prevent accidental reuse.
        run_id = uuid.uuid4().hex[:16]
        engine = Engine(workspace)
        try:
            smoke_path = _write_private_report(engine.store.workspace, run_id, "containment", smoke)
            candidate = engine.ingest_package(source_fixture(), source="trusted-sagecode-v5-trial")
            project_id = "sage-live-" + run_id
            project = SageProjectTools.create(engine.store.workspace, project_id,
                                              engine.get(candidate["id"])["manifest"],
                                              allowed_project_ids={project_id})
            gate = SageProjectTestGate.create(project, frozen_acceptance())
            coordinator = SageRepairCoordinator(engine, candidate["id"], gate, max_repairs=2)
            result = coordinator.run(
                "Fix the incorrect addition behavior in src/ops.py. Inspect source first, "
                "make a minimal correction, and preserve all independent acceptance tests.",
                session_id="trial-" + run_id)
            # Trust only data from our owner-side controller, never model text.
            evidence = {"schema": "sagecode-live-trial-report-v1", "trial_id": run_id,
                        "live_containment_preflight": True, "project_id": project_id,
                        "smoke_report": smoke_path, "repair_report": result,
                        "owner_review_required": True, "release_allowed": False, "approved": False}
            saved = _write_private_report(engine.store.workspace, run_id, "trial", evidence)
            print(json.dumps({"status": result["status"], "evidence_mode": "local_docker_and_loopback_ollama",
                              "trial_report": saved, "containment_report": smoke_path,
                              "repairs": len(result["attempts"]),
                              "owner_review_required": True, "approved": False, "release_allowed": False}, indent=2))
            return 0 if result["status"] == "tests_passed_review_required" else 3
        finally:
            engine.close()
    except (PackageError, OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "blocked", "execution_performed": False,
                          "reason": "Local trial could not complete safely; review private logs and setup."}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
