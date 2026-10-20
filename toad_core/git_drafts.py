"""Disposable Git history for generated candidate files (Aider-inspired workflow).

No checkout of untrusted repositories, no remote fetch, no hooks, no installed
candidate is changed. Git operates only in a freshly initialized private
workspace with an empty template and isolated user configuration.
"""
from __future__ import annotations
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from .schema import PackageError, normalize_package


class GitDraft:
    def __init__(self, workspace, package):
        self.package = normalize_package(package)
        self.parent = Path(workspace).resolve() / "drafts"
        self.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.folder = Path(tempfile.mkdtemp(prefix="toad-draft-", dir=self.parent))
        self.template = self.folder.parent / (self.folder.name + "-empty-template")
        self.template.mkdir(mode=0o700)
        self.git = shutil.which("git")
        if not self.git:
            raise PackageError("Git executable unavailable; no host-edit fallback")
        self.env = {"PATH": os.environ.get("PATH", ""), "HOME": str(self.folder), "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TEMPLATE_DIR": str(self.template),
                    "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1"}
        self.revisions = []
        self._run("init", "-q")
        for file in self.package["files"]:
            target = self._path(file["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(file["content"], encoding="utf-8")
        self._commit("Initial untrusted candidate snapshot")
        self.initial = self.revisions[0]

    def _run(self, *args):
        try:
            p = subprocess.run(
                [self.git, "-c", "core.hooksPath=" + os.devnull, "-c", "user.name=Toad Draft",
                 "-c", "user.email=toad-draft@localhost", *args],
                cwd=self.folder, env=self.env, capture_output=True, text=True, timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PackageError("Disposable Git operation failed") from exc
        if p.returncode:
            raise PackageError("Git operation failed: " + p.stderr[:500])
        return p.stdout.strip()

    def _path(self, name):
        if not any(f["path"] == name for f in self.package["files"]):
            raise PackageError("Path was not declared in candidate manifest")
        result = self.folder / name
        if not result.resolve().is_relative_to(self.folder):
            raise PackageError("Unsafe path")
        return result

    def _commit(self, message):
        self._run("add", "--", ".")
        self._run("commit", "-q", "-m", message)
        commit = self._run("rev-parse", "HEAD")
        self.revisions.append(commit)
        return commit

    def edit(self, name, content):
        if not isinstance(content, str) or len(content.encode("utf-8")) > 250000:
            raise PackageError("Invalid edit size")
        path = self._path(name)
        before = path.read_text("utf-8")
        if before == content:
            return {"unchanged": True, "revision": self.revisions[-1], "diff": ""}
        path.write_text(content, encoding="utf-8")
        diff = self._run("diff", "--no-ext-diff", "--", name)
        commit = self._commit("Update candidate file: " + name)
        return {"unchanged": False, "revision": commit, "diff": diff[:30000], "truncated": len(diff) > 30000}

    def rollback(self, revision):
        if revision not in self.revisions:
            raise PackageError("Revision was not created by this draft")
        # This is a disposable candidate repo, never the user's project checkout.
        self._run("reset", "--hard", revision)
        return {"revision": revision, "files": self.snapshot()}

    def snapshot(self):
        return [{"path": f["path"], "content": self._path(f["path"]).read_text("utf-8")}
                for f in self.package["files"]]

    def close(self):
        # Explicit cleanup only inside the workspace-created disposable folder.
        if self.folder.exists():
            shutil.rmtree(self.folder)
        if self.template.exists():
            self.template.rmdir()
