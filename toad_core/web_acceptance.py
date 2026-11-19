"""Immutable, independently supplied browser acceptance plans for AI app drafts.

This class fixes a goal and browser acceptance checks BEFORE a model call,
binds the quarantined source digest to that original plan, and permits only
the existing isolated Docker worker to attempt the checks. Plans and links
are review data, not evidence of deployment or secure execution.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from .schema import PackageError, json_bytes, strict_json
from .web_codegen import QuarantinedWebGenerator, MAX_REQUEST_BYTES
from .web_lab import WebKitDockerWorker, validate_checks

PLAN_SCHEMA = "toad-web-acceptance-plan-v1"
TRIAL_SCHEMA = "toad-web-acceptance-trial-v1"
ID = re.compile(r"[0-9a-f]{32}\Z")
LIMIT = 100


def _digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def _goal(value):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise PackageError("Web plan requires a nonempty app goal without NUL")
    try:
        amount = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise PackageError("Web plan goal must be valid UTF-8 text") from exc
    if amount > MAX_REQUEST_BYTES or any(ord(ch) < 32 and ch not in "\n\t" for ch in value):
        raise PackageError("Web plan goal exceeds safe size or contains control characters")
    return value.strip()


class FrozenWebAcceptance:
    def __init__(self, workspace, *, model=None, worker=None):
        self.workspace = Path(workspace)
        self.model = model
        self.worker = worker

    def _folder(self, folder, create=False):
        if self.workspace.is_symlink():
            raise PackageError("Workspace symlinks are forbidden")
        root = self.workspace / folder
        if root.is_symlink():
            raise PackageError("Acceptance plan folder symlinks are forbidden")
        if create:
            root.mkdir(parents=True, mode=0o700, exist_ok=True)
        return root

    def _new(self, folder, data):
        root = self._folder(folder, create=True)
        if sum(1 for _ in root.glob("*.json")) >= LIMIT:
            raise PackageError("Acceptance record folder is full")
        identifier = uuid.uuid4().hex
        data["id"] = identifier
        path = root / (identifier + ".json")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        return data

    def _read(self, folder, identifier, schema):
        if not isinstance(identifier, str) or not ID.fullmatch(identifier):
            raise PackageError("Invalid acceptance record ID")
        path = self._folder(folder) / (identifier + ".json")
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 12000:
            raise PackageError("Missing, linked or oversized acceptance record")
        data = strict_json(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != schema or data.get("id") != identifier:
            raise PackageError("Invalid acceptance record schema")
        return data

    def create_plan(self, goal, checks):
        """Operator-supplied expectations are fixed before ANY AI call."""
        clean = _goal(goal)
        frozen = validate_checks(checks)
        data = {
            "schema": PLAN_SCHEMA, "goal": clean, "checks": frozen,
            "checks_sha256": _digest(frozen),
            "goal_sha256": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
            "status": "frozen_before_generation",
            "model_wrote_checks": False,
            "executed": False,
            "release_allowed": False,
        }
        data["plan_sha256"] = _digest({key: value for key, value in data.items() if key != "plan_sha256"})
        result = self._new("web-acceptance-plans", data)
        return {"plan_id": result["id"], "status": result["status"],
                "checks_sha256": result["checks_sha256"], "plan_sha256": result["plan_sha256"],
                "model_wrote_checks": False, "executed": False}

    def plan(self, identifier):
        record = self._read("web-acceptance-plans", identifier, PLAN_SCHEMA)
        expected_keys = {
            "id", "schema", "goal", "checks", "checks_sha256", "goal_sha256",
            "status", "model_wrote_checks", "executed", "release_allowed", "plan_sha256",
        }
        if set(record) != expected_keys:
            raise PackageError("Unexpected acceptance-plan fields")
        goal = _goal(record["goal"])
        checked = validate_checks(record["checks"])
        if goal != record["goal"] or checked != record["checks"]:
            raise PackageError("Acceptance-plan contents were normalized or changed")
        if record.get("status") != "frozen_before_generation" or record.get("model_wrote_checks") is not False:
            raise PackageError("Frozen acceptance-plan authority changed")
        if record.get("executed") is not False or record.get("release_allowed") is not False:
            raise PackageError("Frozen acceptance-plan execution or release flags changed")
        if record["checks_sha256"] != _digest(checked) or record["goal_sha256"] != hashlib.sha256(goal.encode("utf-8")).hexdigest():
            raise PackageError("Acceptance-plan source digests mismatch")
        content = {key: value for key, value in record.items() if key not in ("plan_sha256", "id")}
        if record["plan_sha256"] != _digest(content):
            raise PackageError("Frozen acceptance-plan digest mismatch")
        return record

    def draft(self, plan_id):
        """An existing plan is checked BEFORE the model can write source."""
        plan = self.plan(plan_id)
        # The model receives the project goal, not the independent tests.
        generator = QuarantinedWebGenerator(self.workspace, model=self.model)
        source = generator.propose(plan["goal"])
        link = {
            "schema": TRIAL_SCHEMA,
            "plan_id": plan_id,
            "plan_sha256": plan["plan_sha256"],
            "checks_sha256": plan["checks_sha256"],
            "source_draft_id": source["id"],
            "source_sha256": source["draft_sha256"],
            "status": "quarantined_awaiting_independent_test",
            "executed": False,
            "tested": False,
            "deployed": False,
            "release_allowed": False,
        }
        link["trial_sha256"] = _digest(link)
        record = self._new("web-acceptance-trials", link)
        return {"trial_id": record["id"], "plan_id": plan_id,
                "source_draft_id": source["id"], "source_sha256": source["draft_sha256"],
                "checks_sha256": plan["checks_sha256"],
                "status": record["status"], "executed": False, "release_allowed": False}

    def trial(self, identifier):
        record = self._read("web-acceptance-trials", identifier, TRIAL_SCHEMA)
        expected_keys = {
            "id", "schema", "plan_id", "plan_sha256", "checks_sha256",
            "source_draft_id", "source_sha256", "status", "executed",
            "tested", "deployed", "release_allowed", "trial_sha256",
        }
        if set(record) != expected_keys:
            raise PackageError("Unexpected acceptance-trial fields")
        expected_hash = _digest({key: value for key, value in record.items()
                                 if key not in ("trial_sha256", "id")})
        if record.get("trial_sha256") != expected_hash:
            raise PackageError("Acceptance trial was modified")
        if record.get("status") != "quarantined_awaiting_independent_test":
            raise PackageError("Trial status may not authorize release")
        if any(record.get(flag) is not False for flag in ("executed", "tested", "deployed", "release_allowed")):
            raise PackageError("Trial authority flags cannot be changed")
        plan = self.plan(record["plan_id"])
        if plan["plan_sha256"] != record["plan_sha256"] or plan["checks_sha256"] != record["checks_sha256"]:
            raise PackageError("Acceptance trial no longer matches frozen plan")
        source = QuarantinedWebGenerator(self.workspace).review(record["source_draft_id"])
        if source["draft_sha256"] != record["source_sha256"]:
            raise PackageError("Acceptance trial no longer matches candidate source")
        return record

    def test(self, trial_id, *, run=False):
        link = self.trial(trial_id)
        plan = self.plan(link["plan_id"])
        dry = {
            "schema": "toad-web-frozen-test-report-v1",
            "trial_id": trial_id, "plan_id": link["plan_id"],
            "source_sha256": link["source_sha256"],
            "checks_sha256": link["checks_sha256"],
            "executed": False, "passed": False, "release_allowed": False,
            "status": "blocked_not_authorized", "receipt": None,
        }
        if run is not True:
            return dry
        # This reopens both hashed immutable records before passing code
        # to an explicitly opt-in, isolated, local Docker worker.
        draft = QuarantinedWebGenerator(self.workspace).show(link["source_draft_id"])["draft"]
        worker = self.worker if self.worker is not None else WebKitDockerWorker()
        result = worker.run_web_source(draft, plan["checks"])
        if result.get("source_sha256") != link["source_sha256"] or result.get("checks_sha256") != link["checks_sha256"]:
            raise PackageError("Isolated worker returned hashes that differ from frozen plan and source")
        return {
            **dry,
            "executed": result["executed"],
            "passed": bool(result["passed"]),
            "status": "isolated_test_passed_unreviewed" if result["passed"] else "isolated_test_failed_or_blocked",
            "receipt": result.get("receipt"),
            "cleanup_ok": result.get("cleanup_ok"),
            "blocked_reason": result.get("blocked_reason"),
            "image_id": result.get("image_id"),
        }
