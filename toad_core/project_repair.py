"""Trusted orchestration of one or two bounded SageCode source repairs.

This is NOT an AI action, an execution API, or a release gate. Only the
independent V3 test gate runs code, using its existing fail-closed DockerWorker.
The project-bound ControlledAgent can only read/search/propose source changes.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .controlled_agent import ControlledAgent
from .engine import Engine
from .models import ModelError
from .project_testing import SageProjectTestGate
from .project_tools import _create_exclusive, _is_private_dir
from .sagecode_actions import SageProjectActionAdapter
from .schema import PackageError

_MAX_ATTEMPTS = 2
_MAX_STEPS_PER_ATTEMPT = 6
_MAX_WALL_SECONDS = 180
_SESSION_RE = re.compile(r"[a-z][a-z0-9_-]{1,39}\Z")
_REPAIRABLE_FAILURES = frozenset(("test_failure",))


class SageRepairCoordinator:
    """Trusted, one-shot controller; never instantiated from a model action.

    A successful test result remains UNVERIFIED and requires human review.
    No test worker or shell is passed to the model or the project agent.
    """

    def __init__(self, engine: Engine, candidate_id: str, test_gate: SageProjectTestGate,
                 *, model=None, max_repairs=2):
        if type(engine) is not Engine or type(test_gate) is not SageProjectTestGate:
            raise PackageError("Trusted SageCode engine and frozen test gate required")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise PackageError("An authorized candidate is required")
        if type(max_repairs) is not int or not 1 <= max_repairs <= _MAX_ATTEMPTS:
            raise PackageError("Repair attempts must be between 1 and 2")
        # V2 revalidates workspace, exact original manifest, and baseline binding.
        binding = SageProjectActionAdapter(engine, candidate_id, test_gate.project)
        test_gate._ensure_plan()
        self.engine = engine
        self.candidate_id = candidate_id
        self.gate = test_gate
        self.project = test_gate.project
        self.binding = binding.binding
        self.model = model  # None selects existing local-only OllamaAdapter in ControlledAgent.
        self.max_repairs = max_repairs

    def _view(self, raw, *, expected_revision=None):
        if not isinstance(raw, dict) or not isinstance(raw.get("receipt_id"), str):
            raise PackageError("Missing independent test evidence")
        result = self.gate.evidence_for_current(raw["receipt_id"])
        if (raw.get("evidence_digest") != result.get("evidence_digest")
                or result.get("project_id") != self.project.project_id
                or result.get("plan_digest") != self.gate.plan_digest
                or (expected_revision is not None and result.get("revision") != expected_revision)):
            raise PackageError("Test evidence does not match the authorized project and revision")
        return result

    @staticmethod
    def _summary(evidence):
        return {"receipt_id": evidence["receipt_id"], "revision": evidence["revision"],
                "plan_digest": evidence["plan_digest"],
                "display_status": evidence["display_status"], "is_current": evidence["is_current"],
                "passed": evidence["passed"] is True, "executed": evidence["executed"] is True,
                "backend": evidence["backend"],
                "cases": [{"index": x.get("index"), "category": x.get("category"),
                           "passed": x.get("passed") is True} for x in evidence.get("cases", [])[:10]]}

    @staticmethod
    def _classify(evidence):
        if not evidence.get("is_current") or evidence.get("display_status") == "stale_revision":
            return "stale"
        if evidence.get("display_status") == "passed" and evidence.get("passed") is True \
                and evidence.get("executed") is True and evidence.get("cleanup_ok") is True \
                and evidence.get("backend") == "docker":
            return "passed"
        if evidence.get("display_status") == "failed" and evidence.get("executed") is True \
                and evidence.get("backend") == "docker" and evidence.get("cleanup_ok") is True \
                and evidence.get("cases") and any(x.get("category") in _REPAIRABLE_FAILURES
                                                     for x in evidence["cases"]) \
                and all(x.get("category") in _REPAIRABLE_FAILURES | {"passed"} for x in evidence["cases"]):
            return "repairable"
        return "blocked"

    def run(self, goal: str, *, session_id: str, cancel=None):
        """Test current source, attempt bounded source edits, retest same frozen plan.

        One session identifier may be used only once. After a crash the existing
        agent's pending checkpoint prevents an uncertain action replay; this
        controller itself never resumes or silently rolls back source changes.
        """
        if not isinstance(session_id, str) or not _SESSION_RE.fullmatch(session_id):
            raise PackageError("Invalid repair session identifier")
        if not isinstance(goal, str) or not goal.strip():
            raise PackageError("Repair goal must be non-empty")
        try:
            goal_bytes = len(goal.encode("utf-8"))
        except UnicodeError as exc:
            raise PackageError("Invalid repair goal encoding") from exc
        if goal_bytes > 1000 or any(ord(ch) < 32 and ch not in "\n\t" for ch in goal):
            raise PackageError("Repair goal is oversized or malformed")
        if cancel is not None and not callable(cancel):
            raise PackageError("Invalid cancellation callback")
        # An existing trajectory signals prior or interrupted attempts. Do not
        # replay uncertain project edits on a repeated run of the same session.
        root = Path(self.engine.store.workspace) / "agent-trajectories"
        if root.exists() or root.is_symlink():
            _is_private_dir(root)
        for idx in range(self.max_repairs):
            if (root / f"sage-repair-{session_id}-{idx+1}.json").exists():
                raise PackageError("Repair session was already started; manual review required")
        self.gate._ensure_plan()
        first_revision = self.project.status()["revision"]
        # Atomic session claim: retries after a crash or concurrent invocations
        # never silently repeat an uncertain model edit / test execution.
        # Incomplete sessions require a separate human recovery procedure.
        sessions_root = self.project.root.parent / "sagecode-v4"
        sessions_root.mkdir(mode=0o700, exist_ok=True)
        _is_private_dir(sessions_root)
        project_sessions = sessions_root / self.project.project_id
        project_sessions.mkdir(mode=0o700, exist_ok=True)
        _is_private_dir(project_sessions)
        if len(list(project_sessions.iterdir())) >= 40:
            raise PackageError("SageCode repair session limit reached")
        session_file = project_sessions / (session_id + ".json")
        if session_file.exists() or session_file.is_symlink():
            raise PackageError("Repair session was already started; manual review required")
        _create_exclusive(session_file, {
            "schema": "sagecode-repair-session-v1", "session_id": session_id,
            "project_id": self.project.project_id, "candidate_id": self.candidate_id,
            "initial_revision": first_revision, "plan_digest": self.gate.plan_digest,
            "status": "started_review_required"})
        report = {"schema": "sagecode-repair-report-v1", "project_id": self.project.project_id,
                  "candidate_id": self.candidate_id, "plan_digest": self.gate.plan_digest,
                  "initial_revision": first_revision, "final_revision": first_revision,
                  "status": "blocked", "attempts": [], "initial_test": None, "final_test": None,
                  "verification": "unverified", "approved": False, "release_allowed": False,
                  "owner_review_required": True}
        start = time.monotonic()
        if cancel is not None and cancel():
            report["status"] = "cancelled"
            return report
        before = self._view(self.gate.run_current(cancel=cancel), expected_revision=first_revision)
        report["initial_test"] = self._summary(before)
        report["final_test"] = report["initial_test"]
        kind = self._classify(before)
        if kind == "passed":
            report["status"] = "already_passing_review_required"
            return report
        if kind != "repairable":
            report["final_revision"] = self.project.status()["revision"]
            report["status"] = "test_unavailable_or_unrepairable" if kind == "blocked" else "stale_test_evidence"
            return report
        for attempt_index in range(1, self.max_repairs + 1):
            if (cancel is not None and cancel()) or time.monotonic() - start >= _MAX_WALL_SECONDS:
                report["status"] = "cancelled_or_budget_exhausted"
                return report
            before_revision = self.project.status()["revision"]
            trajectory_id = f"sage-repair-{session_id}-{attempt_index}"
            agent = ControlledAgent(self.engine, trajectory_id,
                                    candidate_id=self.candidate_id,
                                    project_tools=self.project, model=self.model)
            # Only worker-generated, sanitized failure categories are included;
            # independent test files and the original Docker stderr stay hidden.
            diagnosis = {"goal": goal, "current_revision": before_revision,
                         "plan_digest": self.gate.plan_digest,
                         "failure_categories": [x["category"] for x in report["final_test"]["cases"]],
                         "instruction": "Inspect source using allowed project tools. Propose ONE edit that addresses the failure. Do not change tests, policy, or request execution."}
            step_count = 0
            proposed = None
            while step_count < _MAX_STEPS_PER_ATTEMPT and time.monotonic() - start < _MAX_WALL_SECONDS:
                if cancel is not None and cancel():
                    report["status"] = "cancelled"
                    return report
                try:
                    observed = agent.step(json.dumps(diagnosis, sort_keys=True))
                except (PackageError, ModelError, ValueError, OSError, KeyError, TypeError):
                    # We do not repeat this session after an uncertain edit.
                    report["status"] = "agent_blocked"
                    report["attempts"].append({"attempt": attempt_index, "trajectory_id": trajectory_id,
                                               "outcome": "action_blocked", "revision_before": before_revision,
                                               "revision_after": self.project.status()["revision"]})
                    return report
                step_count += 1
                action = agent.state["actions"][-1]["tool"]
                if action == "project_propose_edit" and not observed.get("unchanged"):
                    proposed = observed
                    break
                if action == "finish":
                    break
            current_revision = self.project.status()["revision"]
            if proposed is None:
                report["final_revision"] = current_revision
                if current_revision != before_revision:
                    report["status"] = "inconsistent_revision_blocked"
                    return report
                report["attempts"].append({"attempt": attempt_index, "trajectory_id": trajectory_id,
                                           "outcome": "no_edit", "revision_before": before_revision,
                                           "revision_after": current_revision, "steps": step_count})
                report["status"] = "no_repair_proposed"
                return report
            if current_revision == before_revision or proposed.get("revision") != current_revision:
                report["status"] = "inconsistent_revision_blocked"
                return report
            # Controller-owned, no model action can set final verification.
            agent.execute_actions({"action": "finish", "message": "Source proposal requires test and owner review"})
            report["attempts"].append({"attempt": attempt_index, "trajectory_id": trajectory_id,
                                       "outcome": "proposed_unverified", "revision_before": before_revision,
                                       "revision_after": current_revision, "steps": step_count,
                                       "diff": str(proposed.get("diff", ""))[:3000],
                                       "diff_truncated": bool(proposed.get("truncated"))})
            report["final_revision"] = current_revision
            if (cancel is not None and cancel()) or time.monotonic() - start >= _MAX_WALL_SECONDS:
                report["status"] = "cancelled_or_budget_exhausted"
                return report
            after = self._view(self.gate.run_current(cancel=cancel), expected_revision=current_revision)
            report["final_test"] = self._summary(after)
            state = self._classify(after)
            if state == "passed":
                report["status"] = "tests_passed_review_required"
                return report
            if state != "repairable":
                report["status"] = "test_unavailable_or_unrepairable" if state == "blocked" else "stale_test_evidence"
                return report
        report["status"] = "repair_budget_exhausted"
        return report
