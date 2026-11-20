"""Source-only action adapter for ControlledAgent's existing bounded loop.

The trusted controller injects a SageProjectTools instance. Untrusted model
messages may select only source-operations within that pre-authorized project;
they never provide project permissions, a workspace root, or an execution tool.
"""
from __future__ import annotations

from pathlib import Path

from .project_tools import SageProjectTools
from .schema import PackageError, package_digest

PROJECT_ACTIONS = (
    "project_status", "project_tree", "project_read", "project_search", "project_propose_edit"
)
_ALLOWED_KEYS = {
    "project_status": frozenset(("action",)),
    "project_tree": frozenset(("action",)),
    "project_read": frozenset(("action", "path", "start_line", "max_lines")),
    "project_search": frozenset(("action", "term", "limit")),
    "project_propose_edit": frozenset(("action", "path", "content", "expected_revision")),
}


class SageProjectActionAdapter:
    """Bind a project snapshot to an existing, trusted candidate trajectory.

    This is neither a general execution backend nor an approval gateway.
    The binding is created by trusted Python, not supplied by the model.
    """

    def __init__(self, engine, candidate_id, project):
        if not isinstance(project, SageProjectTools):
            raise PackageError("A trusted SageCode project object is required")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise PackageError("A source candidate binding is required")
        if project.root.parent != Path(engine.store.workspace).resolve():
            raise PackageError("Project and candidate must share the authorized workspace")
        candidate = engine.get(candidate_id)
        if package_digest(candidate["manifest"]) != candidate["digest"]:
            raise PackageError("Source candidate integrity check failed")
        if project._validated_revision(project.baseline)["manifest"] != candidate["manifest"]:
            raise PackageError("Project baseline must equal its bound source candidate")
        project.status()  # refuses tampered project HEAD, records, or unsafe directories
        self.project = project
        self.binding = {"project_id": project.project_id,
                        "baseline_revision": project.baseline, "candidate_id": candidate_id}

    def status(self):
        return self.project.status()

    def execute(self, action):
        if not isinstance(action, dict) or action.get("action") not in PROJECT_ACTIONS:
            raise PackageError("Unknown SageCode project action")
        tool = action["action"]
        if not set(action).issubset(_ALLOWED_KEYS[tool]):
            raise PackageError("Unapproved project-action parameters")
        if tool == "project_status":
            observation = self.project.status()
        elif tool == "project_tree":
            observation = self.project.list_tree()
        elif tool == "project_read":
            if "path" not in action:
                raise PackageError("Missing source path")
            observation = self.project.read_file(action["path"], start_line=action.get("start_line", 1),
                                                 max_lines=action.get("max_lines", 100))
        elif tool == "project_search":
            if "term" not in action:
                raise PackageError("Missing search term")
            observation = self.project.search(action["term"], limit=action.get("limit", 50))
        else:
            if not {"path", "content", "expected_revision"}.issubset(action):
                raise PackageError("Missing source proposal arguments")
            observation = self.project.propose_edit(action["path"], action["content"],
                                                     expected_revision=action["expected_revision"])
        # Explicitly forbid the adapter from making claims about execution or release.
        observation = dict(observation)
        observation.update({"source_only": True, "executed": False, "approved": False,
                            "verification": "unverified", "release_allowed": False})
        return observation
