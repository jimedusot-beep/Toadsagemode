"""Small bounded action loop, adapted from mini-SWE-agent's DefaultAgent.

MIT-licensed upstream: https://github.com/SWE-agent/mini-swe-agent
Copyright (c) 2025 Kilian A. Lieret and Carlos E. Jimenez.
Adapted run/step/query/execute-actions separation with tool allowlisting,
sandbox-only testing, and crash-safe trajectory persistence. See
third_party_licenses/mini-swe-agent-MIT.txt.

This is NOT a shell agent. Imported instructions never gain authority.
"""
from __future__ import annotations
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from .engine import Engine
from .git_drafts import GitDraft
from .models import OllamaAdapter, ModelError
from .repair import validate_repair
from .schema import PackageError, package_digest
from .sagecode_actions import PROJECT_ACTIONS, SageProjectActionAdapter

ACTIONS = ("read_file", "inspect_candidate", "propose_edit", "test_candidate", "finish")
MAX_STEPS = 12
MAX_SECONDS = 120
MAX_RESULT = 12000


def _json_bytes(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class ControlledAgent:
    """An experimental secondary agent loop; existing MissionEngine remains default."""

    def __init__(self, engine: Engine, identifier: str, *, candidate_id=None, model=None, worker=None, project_tools=None):
        if not identifier or not all(c.isalnum() or c in "-_" for c in identifier) or len(identifier) > 64:
            raise ValueError("Invalid trajectory identifier")
        self.engine = engine
        self.model = model or OllamaAdapter()
        self.worker = worker
        self.project_adapter = None
        self.path = engine.store.workspace / "agent-trajectories" / (identifier + ".json")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise PackageError("Trajectory cannot be a symlink")
        if self.path.exists():
            self.state = json.loads(self.path.read_text("utf-8"))
            if self.state.get("schema") != "toad-agent-trajectory-v1":
                raise PackageError("Unsupported trajectory format")
            if candidate_id is not None and candidate_id not in self.state.get("allowed_candidates", []):
                raise PackageError("Candidate ID is outside this trajectory")
            binding = self.state.get("sage_project_binding")
            if binding is not None:
                if not isinstance(binding, dict) or set(binding) != {"project_id", "baseline_revision", "candidate_id"}:
                    raise PackageError("Invalid project binding in agent trajectory")
                if project_tools is None:
                    raise PackageError("Project-bound trajectory requires trusted project tools to resume")
                if candidate_id is not None and candidate_id != binding["candidate_id"]:
                    raise PackageError("Cannot rebind project to a different candidate")
                self.project_adapter = SageProjectActionAdapter(engine, binding["candidate_id"], project_tools)
                if self.project_adapter.binding != binding:
                    raise PackageError("Trusted project binding changed")
            elif project_tools is not None:
                raise PackageError("Cannot attach source tools to an existing unbound agent trajectory")
        else:
            if not candidate_id:
                raise ValueError("New agent trajectory requires an explicit candidate ID")
            engine.get(candidate_id)
            if project_tools is not None:
                self.project_adapter = SageProjectActionAdapter(engine, candidate_id, project_tools)
            self.state = {"schema": "toad-agent-trajectory-v1", "id": identifier, "status": "ready", "actions": [],
                          "allowed_candidates": [candidate_id],
                          "model_calls": 0, "started_at": time.time(), "pending": None}
            if self.project_adapter is not None:
                self.state["sage_project_binding"] = dict(self.project_adapter.binding)
            self._save()

    def _save(self):
        content = _json_bytes(self.state)
        if len(content) > 1_000_000:
            raise PackageError("Agent trace limit reached")
        path = self.path.with_suffix(".tmp")
        if path.is_symlink():
            raise PackageError("Unsafe checkpoint path")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as writer:
            writer.write(content)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(path, self.path)

    def _allowed_actions(self):
        # A project-bound trajectory never mixes independent candidate tests
        # with source-only draft revisions. Legacy agents keep their tools.
        return PROJECT_ACTIONS + ("finish",) if self.project_adapter is not None else ACTIONS

    def _observation(self, tool, action):
        if tool in PROJECT_ACTIONS:
            if self.project_adapter is None:
                raise PackageError("SageCode project tools are not authorized for this agent")
            return self.project_adapter.execute(action)
        identifier = action.get("candidate_id")
        allowed = self.state.get("allowed_candidates", [])
        if tool == "finish":
            # A finished agent turn is a review proposal, not proof of a working
            # program. Tie any reported verification to this exact candidate.
            if identifier is None and len(allowed) == 1:
                identifier = allowed[0]
            if not isinstance(identifier, str) or identifier not in allowed:
                raise PackageError("Finish must identify one allowed candidate revision")
            candidate = self.engine.get(identifier)
            receipt = self.engine.store.latest_receipt(identifier)
            verified = bool(
                self.project_adapter is None
                and package_digest(candidate["manifest"]) == candidate["digest"]
                and candidate.get("verification") == "verified"
                and receipt is not None
                and receipt.get("candidate_id") == identifier
                and receipt.get("digest") == candidate["digest"]
                and receipt.get("passed") is True
                and receipt.get("executed") is True
                and receipt.get("backend") == "docker"
                and receipt.get("cleanup_ok") is True
            )
            result = {"finished": True, "candidate_id": identifier,
                      "verification": "verified" if verified else "unverified",
                      "receipt_id": receipt["id"] if verified else None,
                      "owner_review_required": True, "installed": False,
                      "message": str(action.get("message", ""))[:500]}
            if self.project_adapter is not None:
                source = self.project_adapter.status()
                result.update({"project_id": source["project_id"], "project_revision": source["revision"],
                               "project_verification": "unverified", "release_allowed": False})
            return result
        if not isinstance(identifier, str) or identifier not in allowed:
            raise PackageError("Candidate must belong to this trajectory")
        candidate = self.engine.get(identifier)
        if tool == "read_file":
            path = action.get("path")
            for file in candidate["manifest"]["files"]:
                if file["path"] == path:
                    return {"path": path, "content": file["content"][:MAX_RESULT], "truncated": len(file["content"]) > MAX_RESULT}
            raise PackageError("File not found in candidate package")
        if tool == "inspect_candidate":
            result = self.engine.inspect(identifier)
            return {"errors": result["errors"][:15], "warnings": result["warnings"][:15], "ready_for_testing": result["ready_for_testing"]}
        if tool == "propose_edit":
            path, content = action.get("path"), action.get("content")
            if not isinstance(path, str) or not isinstance(content, str) or len(content.encode("utf-8")) > 250000:
                raise PackageError("Invalid edit contents")
            original = candidate["manifest"]
            if not any(f["path"] == path for f in original["files"]):
                raise PackageError("Can only edit an existing candidate source file")
            draft = GitDraft(self.engine.store.workspace, original)
            try:
                revision = draft.edit(path, content)
                if revision["unchanged"]:
                    return {"unchanged": True, "candidate_id": identifier}
                proposed = json.loads(json.dumps(original))
                contents = {file["path"]: file["content"] for file in draft.snapshot()}
                for file in proposed["files"]:
                    file["content"] = contents[file["path"]]
            finally:
                draft.close()
            validated, changed = validate_repair(original, proposed)
            if not changed:
                return {"unchanged": True, "candidate_id": identifier}
            record = self.engine.ingest_package(validated, source="bounded-agent-edit")
            if record["id"] not in self.state["allowed_candidates"]:
                self.state["allowed_candidates"].append(record["id"])
            return {"candidate_id": record["id"], "changed_paths": changed, "diff": revision["diff"][:3000],
                    "git_revision": revision["revision"], "installed": False, "executed": False}
        if tool == "test_candidate":
            result = self.engine.test(identifier, self.worker)
            return {"passed": result.get("passed", False), "executed": result.get("executed", False),
                    "blocked_reason": result.get("blocked_reason"), "tests": [
                        {"passed": t.get("passed"), "category": t.get("category"), "stderr": str(t.get("stderr", ""))[:1000]}
                        for t in result.get("tests", [])]}
        raise PackageError("Unknown action")

    def execute_actions(self, message):
        """Only one explicit allowed action per model response; no arbitrary commands."""
        if self.state["status"] in ("awaiting_review", "completed", "blocked"):
            raise PackageError("Terminal trajectory cannot execute another action")
        if not isinstance(message, dict) or message.get("action") not in self._allowed_actions():
            raise PackageError("Agent model must return one allowlisted action")
        tool = message["action"]
        try:
            key = hashlib.sha256(_json_bytes(message)).hexdigest()
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            raise PackageError("Invalid agent action JSON") from exc
        if any(a.get("action_hash") == key for a in self.state["actions"]):
            raise PackageError("Repeated action refused; inspect the prior observation")
        self.state["pending"] = {"action_hash": key, "tool": tool}
        self._save()  # Crash while executing => do not replay an uncertain operation.
        observation = self._observation(tool, message)
        self.state["actions"].append({"action_hash": key, "tool": tool, "observation": observation, "at": time.time()})
        self.state["pending"] = None
        if tool == "finish":
            self.state["status"] = "awaiting_review"
            self.state["final_candidate_id"] = observation["candidate_id"]
            self.state["verification"] = observation["verification"]
        self._save()
        return observation

    def query(self, goal):
        """Ask the model for one restricted action; observations form its context."""
        if self.state["model_calls"] >= MAX_STEPS:
            raise PackageError("Model call limit reached")
        self.state["model_calls"] += 1
        self._save()
        project_context = None
        if self.project_adapter is not None:
            project = self.project_adapter.status()
            project_context = {"project_id": project["project_id"], "revision": project["revision"],
                               "source_only": True, "review_status": "pending_review",
                               "release_allowed": False}
        prompt = json.dumps({
            "goal": goal, "allowed_actions": self._allowed_actions(),
            "project_context": project_context,
            "instructions": ["Respond with one JSON object specifying exactly one allowlisted action.",
                             "No shell commands, host file paths, network access, tool installation or policy changes.",
                             "Finish must name the allowed candidate revision when edits created multiple revisions.",
                             "Finish means awaiting human review, not installation or deployment.",
                             "Existing tests, permissions, dependencies and protected core cannot be modified.",
                             "Observe results before proposing another action; finish if blocked.",
                             "Project actions, when available, are source-only proposals; never claim they were executed.",
                             "Project actions cannot restore drafts, approve changes, execute commands or grant permissions.",
                             "Project edit proposals require the current expected_revision; project IDs and roots are trusted bindings."],
            "allowed_candidate_ids": self.state.get("allowed_candidates", []),
            "observations": self.state["actions"][-5:],
        }, ensure_ascii=False)
        return self.model.generate_json(prompt, purpose="bounded candidate actions")

    def step(self, goal):
        """One model query followed by one restricted action; adapted from mini-SWE-agent."""
        return self.execute_actions(self.query(goal))

    def run(self, goal):
        """Bounded version of mini-SWE-agent's run/step/observation loop."""
        if self.state["pending"]:
            self.state["status"] = "blocked"
            self.state["blocked_reason"] = "Interrupted uncertain action; no automatic replay"
            self._save()
            return self.state
        if self.state["status"] in ("awaiting_review", "completed", "blocked"):
            return self.state
        began = time.monotonic()
        while self.state["model_calls"] < MAX_STEPS and time.monotonic() - began < MAX_SECONDS:
            try:
                self.step(goal)
                if self.state["status"] != "ready":
                    break
            except (PackageError, ModelError, ValueError, OSError, KeyError) as exc:
                self.state["status"] = "blocked"
                self.state["blocked_reason"] = str(exc)[:400]
                self._save()
                break
        if self.state["status"] == "ready":
            self.state["status"] = "blocked"
            self.state["blocked_reason"] = "Step or wall-time limit reached"
            self._save()
        return self.state
