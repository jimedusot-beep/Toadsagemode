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


_FRONTMATTER_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
_META_KEY = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}\Z")


def _plain_metadata_string(raw):
    """Parse a deliberately bounded YAML string subset; never construct objects."""
    if not raw or "\t" in raw or "\r" in raw:
        raise ValueError("Invalid skill metadata scalar")
    if raw.startswith('"'):
        try:
            value = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid double-quoted skill metadata") from exc
        if not isinstance(value, str):
            raise ValueError("Skill metadata must be a string")
    elif raw.startswith("'"):
        if len(raw) < 2 or not raw.endswith("'"):
            raise ValueError("Invalid single-quoted skill metadata")
        inner = raw[1:-1]
        if "'" in inner.replace("''", ""):
            raise ValueError("Invalid single-quoted skill metadata")
        value = inner.replace("''", "'")
    else:
        # Complex YAML values, tags, anchors, aliases and block scalars require
        # a separate, audited parser. Never guess their meaning.
        if raw.startswith(("!", "&", "*", "{", "[", "|", ">")) or ": " in raw or re.search(r"\s+#", raw):
            raise ValueError("Use a quoted string for complex YAML metadata")
        value = raw.strip()
    if not value.strip() or "\x00" in value or any(ord(c) < 32 and c not in "\t\n" for c in value):
        raise ValueError("Empty or control-character skill metadata")
    return value


def parse_skill(text):
    """Validate the nonexecuting, flat-string Agent Skills frontmatter subset.

    This is NOT a general YAML parser, a script loader, or a grant of tools.
    Folded/multiline YAML and resource folders are intentionally unsupported.
    """
    if not isinstance(text, str) or len(text.encode("utf-8")) > SKILL_MAX:
        raise ValueError("SKILL.md must be UTF-8 text within 120 KB")
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md requires frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1 or end > 4096:
        raise ValueError("SKILL.md frontmatter is malformed or oversized")
    fields, metadata, parent = {}, {}, None
    for line in text[4:end].splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("  "):
            if parent != "metadata":
                raise ValueError("Unexpected nested skill metadata")
            match = re.fullmatch(r"  ([A-Za-z][A-Za-z0-9_.-]{0,63}): (.+)", line)
            if not match:
                raise ValueError("Only flat string metadata entries are supported")
            key, raw = match.groups()
            if key in metadata:
                raise ValueError("Duplicate nested metadata key")
            if len(metadata) >= 32:
                raise ValueError("Too many metadata keys")
            value = _plain_metadata_string(raw)
            if len(value) > 500:
                raise ValueError("Nested metadata value too long")
            metadata[key] = value
            continue
        if line[:1].isspace() or "\t" in line:
            raise ValueError("Invalid YAML indentation in skill metadata")
        match = re.fullmatch(r"([a-z][a-z-]*):(?: (.*))?", line)
        if not match:
            raise ValueError("Only bounded string frontmatter is supported")
        key, raw = match.groups()
        if key not in _FRONTMATTER_FIELDS:
            raise ValueError("Unsupported frontmatter field: " + key)
        if key in fields:
            raise ValueError("Duplicate metadata field")
        if key == "metadata":
            if raw is not None:
                raise ValueError("Metadata must use indented string entries")
            fields[key] = True
            parent = "metadata"
            continue
        if raw is None:
            raise ValueError("Missing skill metadata string")
        fields[key] = _plain_metadata_string(raw)
        parent = None
    name, description = fields.get("name"), fields.get("description")
    if not name or len(name) > 64 or not _NAME.fullmatch(name):
        raise ValueError("Invalid Agent Skills name")
    if not description or len(description) > 1024:
        raise ValueError("Skill description must be 1–1024 characters")
    for key, maximum in (("license", 256), ("compatibility", 500), ("allowed-tools", 500)):
        if key in fields and len(fields[key]) > maximum:
            raise ValueError(key + " metadata too long")
    return {
        "name": name, "description": description, "body": text[end + 5:],
        "license": fields.get("license", ""),
        "source_compatibility": fields.get("compatibility", ""),
        "metadata": metadata,
        "declared_allowed_tools": fields.get("allowed-tools", ""),
    }


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
                "source_metadata": {"license": parsed["license"], "compatibility": parsed["source_compatibility"],
                                    "metadata": parsed["metadata"], "allowed-tools": parsed["declared_allowed_tools"]},
                "validation": "agent-skills-string-frontmatter-subset-v1",
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
