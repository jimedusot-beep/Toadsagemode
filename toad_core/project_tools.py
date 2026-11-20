"""Source-only, revisioned project tools for an explicitly authorized package.

This is not a host filesystem browser, shell, sandbox, or approval gateway.
It stores bounded, nonexecutable snapshots outside the repository checkout.
The trusted caller, never a model response, supplies ``allowed_project_ids``.
"""
from __future__ import annotations

import copy
from contextlib import contextmanager
import difflib
import hashlib
import json
import os
import re
import stat
import uuid
from pathlib import Path

from .schema import PackageError, MAX_FILE_BYTES, normalize_package, safe_path, strict_json

_REVISION_RE = re.compile(r"[0-9a-f]{64}\Z")
_PROJECT_RE = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")
_SECRET_RE = re.compile(
    r"(?:\.?env|secrets?|credentials?|passwords?|tokens?|access_token|api_key|apikey|private[_-]?key|id_rsa)(?:[._-]|$)",
    re.IGNORECASE,
)
_MAX_REVISIONS = 40
_MAX_DOCUMENT_BYTES = 600_000
_MAX_READ_BYTES = 16_000
_MAX_DIFF_BYTES = 30_000
# Avoid quadratic or excessive source comparison before touching persistent HEAD.
_MAX_DIFF_COMPARISONS = 1_000_000
_MAX_DIFF_LINES = 2_000


def _validate_source_path(path):
    safe_path(path)
    if any(_SECRET_RE.match(component) for component in path.split("/")):
        raise PackageError("SageCode refuses potentially secret-bearing source paths")
    return path


def _validate_manifest(package):
    normalized = normalize_package(package)
    for entry in normalized["files"]:
        _validate_source_path(entry["path"])
    return normalized


def _json_bytes(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PackageError("Invalid SageCode record") from exc


def _record_digest(record):
    return hashlib.sha256(_json_bytes({k: v for k, v in record.items() if k != "revision"})).hexdigest()


def _is_private_dir(path):
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise PackageError("SageCode storage directory is missing") from exc
    if not stat.S_ISDIR(metadata.st_mode) or path.is_symlink():
        raise PackageError("Unsafe SageCode storage directory")
    if os.name != "nt" and stat.S_IMODE(metadata.st_mode) & 0o077:
        raise PackageError("SageCode storage directory must be owner-only")


def _read_record(path):
    try:
        if path.is_symlink():
            raise PackageError("Symlink in SageCode storage")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > _MAX_DOCUMENT_BYTES:
                raise PackageError("Invalid or oversized SageCode record")
            raw = stream.read(_MAX_DOCUMENT_BYTES + 1)
        if len(raw) > _MAX_DOCUMENT_BYTES:
            raise PackageError("Oversized SageCode record")
        result = strict_json(raw)
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError) as exc:
        raise PackageError("SageCode record cannot be read or parsed") from exc
    if not isinstance(result, dict):
        raise PackageError("SageCode record must be an object")
    return result


def _create_exclusive(path, payload):
    data = _json_bytes(payload)
    if len(data) > _MAX_DOCUMENT_BYTES:
        raise PackageError("SageCode record exceeds size limit")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    created = False
    try:
        descriptor = os.open(path, flags, 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except (OSError, ValueError) as exc:
        # A short write or fsync failure must not leave a corrupt immutable
        # revision that later prevents a valid retry. Do not delete a record
        # if the exclusive open never succeeded (it belongs to someone else).
        if created:
            try:
                path.unlink()
            except OSError:
                pass
        raise PackageError("Could not create exclusive SageCode record") from exc


def _replace_head(path, payload):
    temporary = path.parent / (".head-" + uuid.uuid4().hex + ".tmp")
    try:
        _create_exclusive(temporary, payload)
        if path.is_symlink():
            raise PackageError("SageCode head is a symlink")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


@contextmanager
def _mutation_lock(project):
    """Fail-closed cross-process writer claim; stale claims require owner review.

    A normal release unlinks the lock. After a process crash the lock remains,
    and no automatic stale-lock recovery is attempted. The trusted operator
    must determine whether a previous mutation was interrupted before removal.
    This is designed for a local private filesystem, not a distributed store.
    """
    lock = project / ".sagecode-write.lock"
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock, flags, 0o600)
    except OSError as exc:
        raise PackageError("SageCode writer busy or interrupted; manual review required") from exc
    os.close(fd)
    try:
        yield
    finally:
        try:
            lock.unlink()
        except OSError as exc:
            raise PackageError("SageCode writer lock cleanup failed; manual review required") from exc


def _bounded_diff(path, before, after):
    """Prepare a review diff before mutation, with a bounded comparison cost."""
    previous = before.splitlines(keepends=True)
    proposed = after.splitlines(keepends=True)
    if (len(previous) > _MAX_DIFF_LINES or len(proposed) > _MAX_DIFF_LINES
            or len(previous) * len(proposed) > _MAX_DIFF_COMPARISONS):
        # An absent diff plus truncated=True means full before/after review is
        # mandatory. It NEVER means the edit was unchanged.
        return "", True
    changes = difflib.unified_diff(previous, proposed, fromfile="a/" + path, tofile="b/" + path)
    # A 250 kB source file can produce much more output than a review panel
    # should display; stop collecting once the cap is exceeded.
    output = bytearray()
    for fragment in changes:
        encoded = fragment.encode("utf-8")
        remaining = _MAX_DIFF_BYTES + 1 - len(output)
        if remaining <= 0:
            break
        output.extend(encoded[:remaining])
    return bytes(output[:_MAX_DIFF_BYTES]).decode("utf-8", errors="ignore"), len(output) > _MAX_DIFF_BYTES


class SageProjectTools:
    """One authorized project, stored as bounded immutable source snapshots.

    This object is for a trusted local orchestrator, not for direct public HTTP
    requests. No source is extracted or executed. There is no approval method.
    """

    def __init__(self, workspace, project_id, *, allowed_project_ids):
        if not isinstance(project_id, str) or not _PROJECT_RE.fullmatch(project_id):
            raise PackageError("Invalid SageCode project identifier")
        if not isinstance(allowed_project_ids, (set, frozenset)) or project_id not in allowed_project_ids:
            raise PackageError("Project not authorized by the trusted caller")
        supplied_workspace = Path(workspace).expanduser()
        if supplied_workspace.is_symlink():
            raise PackageError("Workspace root cannot be a symlink")
        self.project_id = project_id
        self.root = supplied_workspace.resolve() / "sagecode-v1"
        self.project = self.root / project_id
        self.revisions = self.project / "revisions"
        self._check_layout()
        meta = _read_record(self.project / "project.json")
        if set(meta) != {"schema", "project_id", "baseline"} or meta["schema"] != "sagecode-project-v1" or meta["project_id"] != project_id or not isinstance(meta["baseline"], str) or not _REVISION_RE.fullmatch(meta["baseline"]):
            raise PackageError("Invalid SageCode project metadata")
        self.baseline = meta["baseline"]
        self._current()  # verify baseline ancestry, head and source integrity

    @classmethod
    def create(cls, workspace, project_id, package, *, allowed_project_ids):
        if not isinstance(project_id, str) or not _PROJECT_RE.fullmatch(project_id):
            raise PackageError("Invalid SageCode project identifier")
        if not isinstance(allowed_project_ids, (set, frozenset)) or project_id not in allowed_project_ids:
            raise PackageError("Project not authorized by the trusted caller")
        normalized = _validate_manifest(package)
        base = Path(workspace).expanduser()
        if base.is_symlink():
            raise PackageError("Workspace root cannot be a symlink")
        root = base.resolve() / "sagecode-v1"
        if not root.exists():
            try:
                root.mkdir(mode=0o700, parents=True)
            except OSError as exc:
                raise PackageError("Cannot initialize SageCode storage") from exc
        _is_private_dir(root)
        project = root / project_id
        try:
            project.mkdir(mode=0o700)
        except OSError as exc:
            raise PackageError("SageCode project already exists or cannot be created") from exc
        revisions = project / "revisions"
        revisions.mkdir(mode=0o700)
        base_record = {"schema": "sagecode-revision-v1", "project_id": project_id,
                       "parent": None, "manifest": normalized}
        base_record["revision"] = _record_digest(base_record)
        _create_exclusive(revisions / (base_record["revision"] + ".json"), base_record)
        _create_exclusive(project / "project.json", {"schema": "sagecode-project-v1",
                                                        "project_id": project_id,
                                                        "baseline": base_record["revision"]})
        _create_exclusive(project / "head.json", {"revision": base_record["revision"]})
        return cls(workspace, project_id, allowed_project_ids=allowed_project_ids)

    def _check_layout(self):
        for directory in (self.root, self.project, self.revisions):
            _is_private_dir(directory)

    def _read_revision(self, revision):
        if not isinstance(revision, str) or not _REVISION_RE.fullmatch(revision):
            raise PackageError("Invalid revision identifier")
        record = _read_record(self.revisions / (revision + ".json"))
        if set(record) != {"schema", "project_id", "parent", "manifest", "revision"} or record["schema"] != "sagecode-revision-v1" or record["project_id"] != self.project_id or record["revision"] != revision or _record_digest(record) != revision:
            raise PackageError("SageCode revision integrity check failed")
        if record["parent"] is not None and (not isinstance(record["parent"], str) or not _REVISION_RE.fullmatch(record["parent"])):
            raise PackageError("Invalid SageCode parent revision")
        if _validate_manifest(record["manifest"]) != record["manifest"]:
            raise PackageError("Noncanonical SageCode revision source")
        return record

    def _validated_revision(self, revision):
        visited = set()
        current = revision
        while current is not None:
            if current in visited or len(visited) >= _MAX_REVISIONS:
                raise PackageError("Invalid SageCode revision ancestry")
            visited.add(current)
            record = self._read_revision(current)
            if record["parent"] is None:
                if current != self.baseline:
                    raise PackageError("Revision does not descend from this project baseline")
                return self._read_revision(revision)
            current = record["parent"]
        raise PackageError("Revision has no baseline")

    def _current(self):
        self._check_layout()
        head = _read_record(self.project / "head.json")
        if set(head) != {"revision"}:
            raise PackageError("Invalid SageCode HEAD")
        return self._validated_revision(head["revision"])

    def _check_expected(self, expected_revision):
        current = self._current()
        if not isinstance(expected_revision, str) or expected_revision != current["revision"]:
            raise PackageError("Stale or missing expected revision; no changes made")
        return current

    def status(self):
        record = self._current()
        return {"schema": "sagecode-project-status-v1", "project_id": self.project_id,
                "revision": record["revision"], "baseline_revision": self.baseline,
                "verification": "unverified", "review_status": "pending_review",
                "executed": False, "approved": False, "release_allowed": False,
                "test_evidence": None}

    def list_tree(self):
        record = self._current()
        items = {}
        for file in record["manifest"]["files"]:
            name = file["path"]
            for i, part in enumerate(name.split("/")[:-1]):
                path = "/".join(name.split("/")[:i+1])
                items[path] = {"path": path, "kind": "directory"}
            items[name] = {"path": name, "kind": "file", "bytes": len(file["content"].encode("utf-8")),
                           "sha256": hashlib.sha256(file["content"].encode("utf-8")).hexdigest()}
        return {"project_id": self.project_id, "revision": record["revision"],
                "entries": sorted(items.values(), key=lambda x: (x["path"].casefold(), x["kind"]))}

    def _file(self, record, path):
        _validate_source_path(path)
        for file in record["manifest"]["files"]:
            if file["path"] == path:
                return file
        raise PackageError("File not declared in the authorized project")

    def read_file(self, path, *, start_line=1, max_lines=100):
        if type(start_line) is not int or type(max_lines) is not int or start_line < 1 or not 1 <= max_lines <= 200:
            raise PackageError("Invalid SageCode read bounds")
        record = self._current()
        file = self._file(record, path)
        all_lines = file["content"].splitlines(keepends=True)
        if start_line > max(1, len(all_lines)):
            raise PackageError("Start line is outside the source")
        selected = all_lines[start_line-1:start_line-1+max_lines]
        raw = "".join(selected).encode("utf-8")
        content = raw[:_MAX_READ_BYTES].decode("utf-8", errors="ignore")
        return {"project_id": self.project_id, "revision": record["revision"],
                "path": path, "start_line": start_line, "total_lines": len(all_lines),
                "content": content, "truncated": len(raw) > _MAX_READ_BYTES or start_line-1+max_lines < len(all_lines),
                "sha256": hashlib.sha256(file["content"].encode("utf-8")).hexdigest()}

    def search(self, term, *, limit=50):
        if not isinstance(term, str) or not term.strip() or any(ord(c) < 32 for c in term):
            raise PackageError("Invalid SageCode search term")
        try:
            term_size = len(term.encode("utf-8"))
        except UnicodeError as exc:
            raise PackageError("Invalid SageCode search term") from exc
        if term_size > 100:
            raise PackageError("Invalid SageCode search term")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise PackageError("Invalid SageCode search limit")
        record = self._current()
        needle = term.casefold()
        matches = []
        for file in sorted(record["manifest"]["files"], key=lambda f: f["path"].casefold()):
            path = file["path"]
            if needle in path.casefold():
                matches.append({"path": path, "line": 0, "snippet": path[:200], "kind": "filename"})
            if len(matches) >= limit:
                break
            for number, line in enumerate(file["content"].splitlines(), start=1):
                if needle in line.casefold():
                    matches.append({"path": path, "line": number, "snippet": line[:200], "kind": "content"})
                    if len(matches) >= limit:
                        break
            if len(matches) >= limit:
                break
        return {"project_id": self.project_id, "revision": record["revision"],
                "term": term, "matches": matches, "limited": len(matches) == limit}

    def propose_edit(self, path, content, *, expected_revision):
        if not isinstance(content, str) or "\x00" in content:
            raise PackageError("Invalid or oversized SageCode edit")
        try:
            content_size = len(content.encode("utf-8"))
        except UnicodeError as exc:
            raise PackageError("Invalid or oversized SageCode edit") from exc
        if content_size > MAX_FILE_BYTES:
            raise PackageError("Invalid or oversized SageCode edit")
        self._check_layout()
        with _mutation_lock(self.project):
            current = self._check_expected(expected_revision)
            before = self._file(current, path)["content"]
            if before == content:
                return {"project_id": self.project_id, "revision": current["revision"],
                        "unchanged": True, "diff": "", "truncated": False, "verification": "unverified"}
            # Generate review evidence before writing any revision or HEAD.
            # A failed/expensive diff must not commit a change without a response.
            try:
                diff, diff_truncated = _bounded_diff(path, before, content)
            except (RuntimeError, ValueError, UnicodeError, MemoryError) as exc:
                raise PackageError("SageCode diff preparation failed; no changes made") from exc
            new_manifest = copy.deepcopy(current["manifest"])
            for file in new_manifest["files"]:
                if file["path"] == path:
                    file["content"] = content
                    break
            new_manifest = _validate_manifest(new_manifest)
            new_record = {"schema": "sagecode-revision-v1", "project_id": self.project_id,
                          "parent": current["revision"], "manifest": new_manifest}
            new_record["revision"] = _record_digest(new_record)
            target_path = self.revisions / (new_record["revision"] + ".json")
            created_revision = False
            if target_path.exists() or target_path.is_symlink():
                # A restored snapshot can legitimately revisit a prior
                # immutable revision. Never reuse an invalid stored record.
                if self._read_revision(new_record["revision"]) != new_record:
                    raise PackageError("Conflicting SageCode revision record")
            else:
                if len(list(self.revisions.iterdir())) >= _MAX_REVISIONS:
                    raise PackageError("SageCode revision limit reached")
                _create_exclusive(target_path, new_record)
                created_revision = True
            try:
                _replace_head(self.project / "head.json", {"revision": new_record["revision"]})
            except Exception:
                # A failed HEAD move must not consume one of the bounded
                # immutable revision slots or leave a confusing orphan. Do
                # not remove an existing (reused) revision record.
                if created_revision:
                    try:
                        target_path.unlink()
                    except OSError:
                        pass
                raise
            return {"project_id": self.project_id, "revision": new_record["revision"],
                    "parent_revision": current["revision"], "unchanged": False,
                    "diff": diff, "truncated": diff_truncated, "verification": "unverified",
                    "review_status": "pending_review", "release_allowed": False}

    def restore(self, revision, *, expected_revision):
        self._check_layout()
        with _mutation_lock(self.project):
            current = self._check_expected(expected_revision)
            target = self._validated_revision(revision)
            if target["revision"] != current["revision"]:
                _replace_head(self.project / "head.json", {"revision": target["revision"]})
            return {"project_id": self.project_id, "revision": target["revision"],
                    "previous_revision": current["revision"], "restored": True,
                    "verification": "unverified", "review_status": "pending_review", "release_allowed": False}
