"""Trusted, source-revision-bound test gateway; never callable by an AI action.

Only a concrete DockerWorker result can be marked as a passed test. Source
verification/owner approval are deliberately out of scope. Frozen tests are
created by trusted orchestration at the initial project revision.
"""
from __future__ import annotations

import copy
import hashlib
import re
import uuid
from pathlib import Path

from .lab import DockerWorker
from .project_tools import (
    SageProjectTools, _create_exclusive, _is_private_dir, _json_bytes,
    _read_record, _validate_source_path,
)
from .schema import PackageError, MAX_PACKAGE_BYTES, normalize_package, package_digest

_PLAN_SCHEMA = "sagecode-frozen-tests-v1"
_RECEIPT_SCHEMA = "sagecode-test-evidence-v1"
_MAX_RECEIPTS = 40
_MAX_TEST_FILES = 10
_MAX_TEST_FILE_BYTES = 64_000
_MAX_TEST_SUPPORT_BYTES = 128_000
_RECEIPT_RE = re.compile(r"[0-9a-f]{32}\Z")
_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")


def _frozen_plan(value, source_manifest):
    """Validate an independently supplied plan, not tests produced by a model."""
    if not isinstance(value, dict) or set(value) != {"tests", "files"}:
        raise PackageError("Trusted test plan needs exactly tests and files")
    try:
        plan = copy.deepcopy(value)
    except (TypeError, ValueError, RecursionError) as exc:
        raise PackageError("Invalid test plan structure") from exc
    specs = plan.get("tests")
    support = plan.get("files")
    if not isinstance(specs, list) or not 1 <= len(specs) <= 10:
        raise PackageError("Trusted test plan needs 1 to 10 tests")
    if not isinstance(support, list) or len(support) > _MAX_TEST_FILES:
        raise PackageError("Trusted test support exceeds file limit")
    current_files = {item["path"].casefold() for item in source_manifest["files"]}
    support_paths = set()
    total = 0
    for f in support:
        if not isinstance(f, dict) or set(f) != {"path", "content"}:
            raise PackageError("Invalid trusted test support file")
        path = _validate_source_path(f["path"])
        if not path.startswith("tests/") or not path.endswith(".py"):
            raise PackageError("Frozen test support must be Python files under tests/")
        folded = path.casefold()
        if folded in current_files or folded in support_paths:
            raise PackageError("Trusted tests may not replace or alias project files")
        support_paths.add(folded)
        body = f["content"]
        if not isinstance(body, str) or "\x00" in body:
            raise PackageError("Invalid trusted test support content")
        try:
            size = len(body.encode("utf-8"))
        except UnicodeError as exc:
            raise PackageError("Invalid trusted test support encoding") from exc
        if size > _MAX_TEST_FILE_BYTES:
            raise PackageError("Trusted test support is oversized")
        total += size
        if total > _MAX_TEST_SUPPORT_BYTES:
            raise PackageError("Trusted test support exceeds total limit")
    for item in specs:
        if not isinstance(item, dict) or item.get("kind") not in ("python", "unittest"):
            raise PackageError("Only bounded Python and unittest checks are accepted")
        if item["kind"] == "python":
            if set(item) != {"kind", "path", "expected_stdout"}:
                raise PackageError("Invalid expected-output test fields")
            if item["path"] not in {f["path"] for f in source_manifest["files"]}:
                raise PackageError("Expected-output test must target original project source")
        else:
            if set(item) != {"kind", "path"} or item["path"] != "tests":
                raise PackageError("Unittest checks must target frozen tests/ directory")
            if not any(p.startswith("tests/test") and p.endswith(".py") for p in support_paths):
                raise PackageError("Unittest requires an independent frozen test_*.py file")
    _stage_package(source_manifest, plan)
    if len(_json_bytes(plan)) > _MAX_TEST_SUPPORT_BYTES + 16_000:
        raise PackageError("Frozen test plan too large")
    return plan


def _stage_package(manifest, plan):
    if manifest["permissions"] or manifest["dependencies"]:
        raise PackageError("Test revision requires no permissions or external dependencies")
    staged = copy.deepcopy(manifest)
    staged["tests"] = copy.deepcopy(plan["tests"])
    staged["files"].extend(copy.deepcopy(plan["files"]))
    result = normalize_package(staged)
    if len(_json_bytes(result)) > MAX_PACKAGE_BYTES:
        raise PackageError("Tested source and frozen checks exceed package limit")
    return result


def _plan_digest(project_id, baseline, plan):
    return hashlib.sha256(_json_bytes({"project_id": project_id, "baseline_revision": baseline,
                                       "plan": plan})).hexdigest()


def _is_true_test_result(result, digest, specs):
    """Validate a DockerWorker result, not arbitrary model/test-double claims."""
    if not isinstance(result, dict) or result.get("backend") != "docker" or result.get("digest") != digest:
        return False
    cases = result.get("tests")
    return (result.get("passed") is True and result.get("executed") is True
            and result.get("cleanup_ok") is True and not result.get("blocked_reason")
            and isinstance(result.get("image_id"), str)
            and bool(re.fullmatch(r"sha256:[a-f0-9]{64}", result["image_id"]))
            and isinstance(cases, list) and len(cases) == len(specs)
            and all(isinstance(t, dict) and t.get("index") == index
                    and t.get("kind") == spec["kind"] and t.get("path") == spec["path"]
                    and t.get("passed") is True and t.get("executed") is True
                    and t.get("cleanup_ok") is True
                    for index, (t, spec) in enumerate(zip(cases, specs))))


class SageProjectTestGate:
    """Trusted-only test receipt writer bound to a SageProjectTools project.

    No network API, no agent action, no shell fallback, no approval transition.
    The caller owns the authorized project and freezes tests before editing.
    """

    def __init__(self, project):
        if type(project) is not SageProjectTools:
            raise PackageError("Trusted SageProjectTools instance required")
        self.project = project
        self.directory = project.root.parent / "sagecode-v3" / project.project_id
        self.receipts = self.directory / "receipts"
        self._check_layout()
        record = _read_record(self.directory / "frozen-tests.json")
        if (set(record) != {"schema", "project_id", "baseline_revision", "plan", "plan_digest"}
                or record["schema"] != _PLAN_SCHEMA
                or record["project_id"] != project.project_id
                or record["baseline_revision"] != project.baseline
                or not isinstance(record["plan_digest"], str)
                or not _DIGEST_RE.fullmatch(record["plan_digest"])):
            raise PackageError("Frozen test plan binding is invalid")
        baseline = project._validated_revision(project.baseline)["manifest"]
        normalized = _frozen_plan(record["plan"], baseline)
        if normalized != record["plan"] or _plan_digest(project.project_id, project.baseline, normalized) != record["plan_digest"]:
            raise PackageError("Frozen test plan integrity check failed")
        self.plan = normalized
        self.plan_digest = record["plan_digest"]

    @classmethod
    def create(cls, project, plan):
        if type(project) is not SageProjectTools:
            raise PackageError("Trusted SageProjectTools instance required")
        record = project._current()
        if record["revision"] != project.baseline:
            raise PackageError("Freeze independent tests before proposing project edits")
        normalized = _frozen_plan(plan, record["manifest"])
        root = project.root.parent / "sagecode-v3"
        root.mkdir(mode=0o700, exist_ok=True)
        _is_private_dir(root)
        directory = root / project.project_id
        try:
            directory.mkdir(mode=0o700)
            (directory / "receipts").mkdir(mode=0o700)
        except OSError as exc:
            raise PackageError("Frozen test plan already exists or cannot be created") from exc
        data = {"schema": _PLAN_SCHEMA, "project_id": project.project_id,
                "baseline_revision": project.baseline, "plan": normalized,
                "plan_digest": _plan_digest(project.project_id, project.baseline, normalized)}
        _create_exclusive(directory / "frozen-tests.json", data)
        return cls(project)

    def _check_layout(self):
        self.project._check_layout()
        for path in (self.directory.parent, self.directory, self.receipts):
            _is_private_dir(path)

    def _ensure_plan(self):
        self._check_layout()
        record = _read_record(self.directory / "frozen-tests.json")
        if (not isinstance(record, dict) or set(record) != {"schema", "project_id", "baseline_revision", "plan", "plan_digest"}
                or record.get("schema") != _PLAN_SCHEMA or record.get("project_id") != self.project.project_id
                or record.get("baseline_revision") != self.project.baseline
                or record.get("plan_digest") != self.plan_digest or record.get("plan") != self.plan):
            raise PackageError("Frozen test plan changed after initialization")

    def summary(self):
        self._ensure_plan()
        return {"schema": "sagecode-test-plan-status-v1", "project_id": self.project.project_id,
                "baseline_revision": self.project.baseline, "plan_digest": self.plan_digest,
                "test_count": len(self.plan["tests"]), "source_only": True,
                "verification": "unverified", "release_allowed": False}

    def run_current(self, *, worker=None, cancel=None):
        """Trusted controller only. A fake worker never establishes passed tests."""
        self._ensure_plan()
        current = self.project._current()
        stage = _stage_package(current["manifest"], self.plan)
        source_digest = package_digest(stage)
        if len(list(self.receipts.iterdir())) >= _MAX_RECEIPTS:
            raise PackageError("Test evidence limit reached before any execution")
        actual_worker = DockerWorker() if worker is None else worker
        is_trusted = type(actual_worker) is DockerWorker
        try:
            result = actual_worker.run(stage, cancel=cancel)
        except Exception:
            # No trace or exception string may leak to a future browser UI.
            result = None
        current_after = self.project._current()["revision"]
        if current_after != current["revision"]:
            status = "stale_revision"
        elif not is_trusted:
            status = "test_double_unverified"
        elif _is_true_test_result(result, source_digest, stage["tests"]):
            status = "passed"
        elif (isinstance(result, dict) and result.get("backend") == "docker"
              and result.get("digest") == source_digest and result.get("executed") is True):
            status = "failed"
        else:
            status = "blocked"
        cases = result.get("tests") if is_trusted and isinstance(result, dict) else None
        sanitized = []
        if isinstance(cases, list):
            for i, case in enumerate(cases[:10]):
                if not isinstance(case, dict):
                    continue
                sanitized.append({"index": i, "passed": case.get("passed") is True,
                                  "executed": case.get("executed") is True,
                                  "cleanup_ok": case.get("cleanup_ok") is True,
                                  "category": case.get("category") if case.get("category") in
                                  ("passed", "timeout", "output_limit", "cancelled", "resource_limit", "test_failure", "worker_error", "cleanup_failed")
                                  else "unrecognized"})
        image = result.get("image_id") if is_trusted and isinstance(result, dict) else None
        evidence = {"schema": _RECEIPT_SCHEMA, "receipt_id": uuid.uuid4().hex,
                    "project_id": self.project.project_id, "revision": current["revision"],
                    "plan_digest": self.plan_digest, "tested_package_digest": source_digest,
                    "status": status, "executed": is_trusted and isinstance(result, dict)
                    and result.get("executed") is True, "passed": status == "passed",
                    "cleanup_ok": is_trusted and isinstance(result, dict)
                    and result.get("cleanup_ok") is True,
                    "backend": "docker" if is_trusted else "test_double",
                    "image_id": image if isinstance(image, str) and re.fullmatch(r"sha256:[a-f0-9]{64}", image) else None,
                    "test_count": len(stage["tests"]), "cases": sanitized,
                    "verification": "unverified", "approved": False, "release_allowed": False}
        evidence["evidence_digest"] = hashlib.sha256(_json_bytes(evidence)).hexdigest()
        _create_exclusive(self.receipts / (evidence["receipt_id"] + ".json"), evidence)
        return dict(evidence)

    def evidence_for_current(self, receipt_id):
        """Display evidence as current only for the exact current source and plan."""
        self._ensure_plan()
        if not isinstance(receipt_id, str) or not _RECEIPT_RE.fullmatch(receipt_id):
            raise PackageError("Invalid test receipt identifier")
        data = _read_record(self.receipts / (receipt_id + ".json"))
        if (not isinstance(data, dict) or set(data) != {
                "schema", "receipt_id", "project_id", "revision", "plan_digest", "tested_package_digest",
                "status", "executed", "passed", "cleanup_ok", "backend", "image_id", "test_count",
                "cases", "verification", "approved", "release_allowed", "evidence_digest"}
                or data.get("schema") != _RECEIPT_SCHEMA or data.get("receipt_id") != receipt_id
                or data.get("project_id") != self.project.project_id
                or data.get("plan_digest") != self.plan_digest
                or data.get("verification") != "unverified"
                or data.get("approved") is not False or data.get("release_allowed") is not False
                or not isinstance(data.get("evidence_digest"), str)
                or not _DIGEST_RE.fullmatch(data["evidence_digest"])):
            raise PackageError("Test evidence fields are invalid")
        digest = hashlib.sha256(_json_bytes({k: v for k, v in data.items() if k != "evidence_digest"})).hexdigest()
        if digest != data["evidence_digest"]:
            raise PackageError("Test evidence integrity check failed")
        current = self.project._current()
        staged = _stage_package(current["manifest"], self.plan)
        is_current = (current["revision"] == data["revision"]
                      and package_digest(staged) == data["tested_package_digest"])
        return {**data, "current_revision": current["revision"], "is_current": is_current,
                "display_status": data["status"] if is_current else "stale_revision",
                "verification": "unverified", "approved": False, "release_allowed": False}
