"""Trusted, revision-bound test gate for SageCode drafts.

This is NOT a model tool, HTTP endpoint, unrestricted shell, or approval gate.
Only an independently configured, restricted DockerWorker can provide genuine
execution evidence. Injected worker doubles are explicitly rehearsal-only.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import time
import uuid

from .lab import DockerWorker
from .project_tools import SageProjectTools, _create_exclusive, _is_private_dir, _read_record, _json_bytes
from .repair import validate_repair
from .schema import PackageError, package_digest

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SCHEMA = "sagecode-revision-test-v1"


def _fingerprint(record):
    return hashlib.sha256(_json_bytes(record)).hexdigest()


class SageRevisionTestGate:
    """Owner-side test orchestration of a pre-authorized, immutable snapshot.

    A SageProjectTools instance is created by trusted local code. No incoming
    model action can choose the project root, worker, plan, or test limits.
    """

    def __init__(self, project, *, worker=None):
        if not isinstance(project, SageProjectTools):
            raise PackageError("Trusted SageCode project is required")
        if worker is not None and not callable(getattr(worker, "run", None)):
            raise PackageError("Trusted worker must implement run(package)")
        self.project = project
        self.worker = worker if worker is not None else DockerWorker()
        # Substituted workers deliberately cannot produce authentic receipts.
        self.authentic_worker = type(self.worker) is DockerWorker

    def _frozen_snapshot(self, expected_revision):
        status = self.project.status()
        if not isinstance(expected_revision, str) or status["revision"] != expected_revision:
            raise PackageError("Stale or missing expected test revision")
        baseline = self.project._validated_revision(self.project.baseline)["manifest"]
        current = self.project._validated_revision(expected_revision)["manifest"]
        if not baseline["tests"]:
            raise PackageError("No independent frozen tests were supplied before editing")
        if current != baseline:
            # Existing source repair validator freezes test specs, test files,
            # permissions, dependencies, entrypoints and the declared file set.
            validate_repair(baseline, current)
        if current["permissions"] or current["dependencies"]:
            raise PackageError("Test execution cannot grant permissions or dependencies")
        return copy.deepcopy(current), _fingerprint(baseline["tests"])

    @staticmethod
    def _summarize_worker(result, manifest):
        """Never trust a worker's top-level `passed` field on its own."""
        if not isinstance(result, dict):
            return None
        if result.get("schema") != "toad-test-run-v1" or result.get("backend") != "docker":
            return None
        if result.get("digest") != package_digest(manifest):
            return None
        cases = result.get("tests")
        if not isinstance(cases, list) or len(cases) > len(manifest["tests"]):
            return None
        summaries = []
        for idx, item in enumerate(cases):
            spec = manifest["tests"][idx]
            if not isinstance(item, dict) or type(item.get("index")) is not int or item["index"] != idx:
                return None
            if item.get("kind") != spec["kind"] or item.get("path") != spec["path"]:
                return None
            summaries.append({"index": idx, "kind": spec["kind"], "passed": item.get("passed") is True,
                              "executed": item.get("executed") is True,
                              "cleanup_ok": item.get("cleanup_ok") is True,
                              "category": str(item.get("category", "unknown"))[:60]})
        image = result.get("image_id")
        image_ok = isinstance(image, str) and bool(_IMAGE_ID.fullmatch(image))
        full_pass = (
            result.get("passed") is True and result.get("executed") is True
            and result.get("cleanup_ok") is True and image_ok
            and len(summaries) == len(manifest["tests"])
            and all(x["passed"] and x["executed"] and x["cleanup_ok"] for x in summaries)
        )
        # Fewer cases are valid for a worker that stopped at its first failure.
        executed = result.get("executed") is True and any(x["executed"] for x in summaries)
        return {"full_pass": full_pass, "executed": executed, "cases": summaries,
                "image_id": image if image_ok else None,
                "cleanup_ok": result.get("cleanup_ok") is True,
                "worker_blocked": bool(result.get("blocked_reason"))}

    def _evidence_dir(self):
        self.project._check_layout()
        directory = self.project.project / "test-evidence"
        try:
            directory.mkdir(mode=0o700, exist_ok=True)
        except OSError as exc:
            raise PackageError("Test evidence storage is unavailable") from exc
        _is_private_dir(directory)
        return directory

    def run(self, *, expected_revision, cancel=None):
        """Test exact private revision in Docker or record a labeled rehearsal.

        The caller must already be a trusted owner-side controller. This
        method is never included in ControlledAgent's model action allowlist.
        """
        manifest, plan_sha = self._frozen_snapshot(expected_revision)
        digest = package_digest(manifest)
        if cancel is not None and not callable(cancel):
            raise PackageError("Invalid trusted cancellation callback")
        try:
            result = self.worker.run(copy.deepcopy(manifest), cancel=cancel)
        except (OSError, ValueError, TypeError) as exc:
            # Never persist exception strings: they may contain private paths.
            result = {"schema": "toad-test-run-v1", "backend": "docker", "digest": digest,
                      "passed": False, "executed": False, "cleanup_ok": False, "tests": [],
                      "blocked_reason": "worker_exception"}
        # The session is single-writer; reject any observed HEAD movement.
        if self.project.status()["revision"] != expected_revision:
            raise PackageError("Project changed during tests; cannot bind result to stale source")
        summary = self._summarize_worker(result, manifest)
        if summary is None:
            outcome = "blocked_invalid_worker_evidence"
            summary = {"full_pass": False, "executed": False, "cases": [],
                       "image_id": None, "cleanup_ok": False, "worker_blocked": True}
        elif not self.authentic_worker and summary["full_pass"]:
            outcome = "rehearsal_passed"
        elif summary["full_pass"]:
            outcome = "tests_passed"
        elif summary["executed"]:
            outcome = "tests_failed"
        else:
            outcome = "blocked"

        evidence = {
            "schema": _SCHEMA, "project_id": self.project.project_id,
            "revision": expected_revision, "baseline_revision": self.project.baseline,
            "package_digest": digest, "frozen_test_plan_sha256": plan_sha,
            "evidence_mode": "restricted_docker_worker" if self.authentic_worker else "test_double_rehearsal",
            "outcome": outcome,
            "executed": bool(self.authentic_worker and summary["executed"]),
            "passed": bool(self.authentic_worker and summary["full_pass"]),
            "cleanup_ok": bool(self.authentic_worker and summary["cleanup_ok"]),
            "image_id": summary["image_id"] if self.authentic_worker else None,
            "tests": summary["cases"], "created_at": int(time.time()),
            "nonce": uuid.uuid4().hex, "verification": "unverified",
            "approved": False, "owner_review_required": True, "release_allowed": False,
        }
        receipt_id = _fingerprint(evidence)
        evidence["receipt_id"] = receipt_id
        location = self._evidence_dir() / (receipt_id + ".json")
        _create_exclusive(location, evidence)
        return self.read_receipt(receipt_id)

    def read_receipt(self, receipt_id):
        if not isinstance(receipt_id, str) or not _DIGEST.fullmatch(receipt_id):
            raise PackageError("Invalid test receipt identifier")
        location = self._evidence_dir() / (receipt_id + ".json")
        receipt = _read_record(location)
        required = {"schema", "project_id", "revision", "baseline_revision",
                    "package_digest", "frozen_test_plan_sha256", "evidence_mode", "outcome",
                    "executed", "passed", "cleanup_ok", "image_id", "tests", "created_at",
                    "nonce", "verification", "approved", "owner_review_required",
                    "release_allowed", "receipt_id"}
        if (not isinstance(receipt, dict) or set(receipt) != required
                or receipt.get("schema") != _SCHEMA
                or receipt.get("project_id") != self.project.project_id
                or receipt.get("baseline_revision") != self.project.baseline
                or receipt.get("receipt_id") != receipt_id
                or receipt.get("verification") != "unverified"
                or receipt.get("approved") is not False
                or receipt.get("release_allowed") is not False
                or receipt.get("owner_review_required") is not True
                or receipt.get("evidence_mode") not in ("test_double_rehearsal", "restricted_docker_worker")
                or not isinstance(receipt.get("tests"), list)
                or (receipt.get("evidence_mode") == "test_double_rehearsal"
                    and (receipt.get("passed") is not False or receipt.get("executed") is not False))
                or _fingerprint({k: v for k, v in receipt.items() if k != "receipt_id"}) != receipt_id):
            raise PackageError("Test evidence integrity check failed")
        manifest = self.project._validated_revision(receipt["revision"])["manifest"]
        baseline = self.project._validated_revision(self.project.baseline)["manifest"]
        if (receipt["package_digest"] != package_digest(manifest)
                or receipt["frozen_test_plan_sha256"] != _fingerprint(baseline["tests"])):
            raise PackageError("Test evidence no longer matches trusted source or tests")
        return {**receipt, "stale": self.project.status()["revision"] != receipt["revision"]}
