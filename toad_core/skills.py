"""Nonexecuting skill packages inspired by agentskills/agentskills and Goose recipes.

Stores instructions and metadata as untrusted, quarantined data. This does
not authorize executing scripts or importing plugins. No third-party code
from those repositories is included in this module.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path

KINDS = ("knowledge", "workflow", "executable")
SKILL_MAX = 120_000


def parse_skill(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > SKILL_MAX:
        raise ValueError("SKILL.md must be UTF-8 text within 120 KB")
    # Deliberately a small subset of YAML, not an unsafe YAML interpreter.
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md requires frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1 or end > 4096:
        raise ValueError("SKILL.md frontmatter is malformed or oversized")
    fields = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not re.fullmatch(r"[a-z_]+: [^\r\n]+", line):
            raise ValueError("Only flat string metadata is supported")
        key, value = line.split(": ", 1)
        if key in fields:
            raise ValueError("Duplicate metadata field")
        if len(value) > 500:
            raise ValueError("Metadata too long")
        fields[key] = value.strip().strip('"')
    name, description = fields.get("name"), fields.get("description")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}", name or ""):
        raise ValueError("Invalid skill name")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("Skill needs a description")
    return {"name": name, "description": description, "body": text[end + 5:]}


class SkillCatalog:
    """Portable local JSON catalog; never loads or executes submitted instructions."""

    def __init__(self, workspace):
        self.folder = Path(workspace).expanduser().resolve() / "skills"
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.folder / "catalog.json"
        if self.path.is_symlink():
            raise ValueError("Skill catalog cannot be a symlink")

    def _read(self):
        if not self.path.exists():
            return {"schema": "toad-skills-v1", "skills": []}
        data = json.loads(self.path.read_text("utf-8"))
        if data.get("schema") != "toad-skills-v1" or not isinstance(data.get("skills"), list):
            raise ValueError("Unsupported skill catalog")
        return data

    def register(self, text, *, kind="knowledge", permissions=None, compatibility=None):
        if kind not in KINDS:
            raise ValueError("Invalid skill kind")
        if not isinstance(permissions, list) or any(not isinstance(p, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{0,79}", p) for p in permissions):
            raise ValueError("Permissions must be explicitly listed; use [] for none")
        if not isinstance(compatibility, dict) or any(not isinstance(k, str) or not isinstance(v, str) or len(v)>200 for k,v in compatibility.items()):
            raise ValueError("Compatibility must be a dictionary of short strings")
        parsed = parse_skill(text)
        data = self._read()
        if len(data["skills"]) >= 100:
            raise ValueError("Skill limit reached")
        digest = hashlib.sha256(text.encode()).hexdigest()
        if any(s["digest"] == digest for s in data["skills"]):
            raise ValueError("Already imported")
        item = {"schema": "toad-skill-v1", "name": parsed["name"], "description": parsed["description"],
                "kind": kind, "digest": digest, "body": parsed["body"],
                "declared_permissions": permissions, "granted_permissions": [], "compatibility": compatibility,
                "status": "quarantined", "executed": False, "installed": False}
        data["skills"].append(item)
        self._write(data)
        return {k:v for k,v in item.items() if k != "body"}

    def _write(self, data):
        payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
        if len(payload.encode("utf-8")) > 2_000_000:
            raise ValueError("Skill catalog too large")
        tmp = self.folder / "catalog.tmp"
        if tmp.is_symlink():
            raise ValueError("Unsafe skill catalog staging path")
        fd = os.open(tmp, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def search(self, query="", kind=None):
        if kind is not None and kind not in KINDS:
            raise ValueError("Invalid kind")
        results=[]
        for item in self._read()["skills"]:
            if kind and item["kind"]!=kind:
                continue
            if query.casefold() not in (item["name"]+" "+item["description"]+" "+item["body"]).casefold():
                continue
            results.append({k:v for k,v in item.items() if k!="body"})
        return results
