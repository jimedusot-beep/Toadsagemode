#!/usr/bin/env python3
"""Structural validation only. This program NEVER executes imported content."""
import json
import re
import sys
from pathlib import PurePosixPath

MAX_BYTES = 512_000
MAX_FILES = 40
NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
WARNINGS = [(re.compile(p, re.I), note) for p, note in [
    (r"\b(?:eval|exec|os\.system|subprocess\.)", "dynamic/host command execution"),
    (r"\b(?:shutil\.rmtree|os\.remove|unlink)\b", "file deletion"),
    (r"\b(?:requests\.|urllib\.|https?://)", "network access"),
    (r"\b(?:password|secret|api[_-]?key|private[_-]?key|token)\b", "potential secret"),
]]


def validate(data):
    errors, warnings = [], []
    if not isinstance(data, dict):
        return ["Expected a JSON object"], warnings
    if data.get("schema") != "toad-ability-v1":
        errors.append("Unsupported schema: expected toad-ability-v1")
    name = data.get("name")
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        errors.append("Invalid module name")
    if not isinstance(data.get("version"), str) or not re.fullmatch(r"\d+\.\d+\.\d+", data["version"]):
        errors.append("Version must be major.minor.patch")
    files = data.get("files")
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILES:
        return errors + ["files must be a list with 1 to 40 entries"], warnings
    paths = set()
    for i, item in enumerate(files):
        if not isinstance(item, dict):
            errors.append(f"File {i} must be an object")
            continue
        path, content = item.get("path"), item.get("content")
        if not isinstance(path, str) or not path or "\\" in path or "\x00" in path:
            errors.append(f"File {i}: invalid path")
            continue
        p = PurePosixPath(path)
        if p.is_absolute() or any(x in (".", "..") for x in path.split("/")) or ":" in path or str(p) != path:
            errors.append(f"File {i}: unsafe path")
        if path in paths:
            errors.append(f"File {i}: duplicate path")
        paths.add(path)
        if not isinstance(content, str):
            errors.append(f"File {i}: content must be a string")
        else:
            for rx, msg in WARNINGS:
                if rx.search(content):
                    warnings.append(f"{path}: {msg}")
    entry = data.get("entrypoint")
    if not isinstance(entry, str) or entry not in paths:
        errors.append("entrypoint must name a listed file")
    if not isinstance(data.get("permissions", []), list):
        errors.append("permissions must be a list")
    if not isinstance(data.get("tests", []), list):
        errors.append("tests must be a list")
    return errors, sorted(set(warnings))


def main():
    if len(sys.argv) != 2:
        print("Usage: python tools/validate_feed.py package.json")
        return 2
    try:
        with open(sys.argv[1], "rb") as file:
            raw = file.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Package exceeds 512KB limit")
        package = json.loads(raw)
        errors, warnings = validate(package)
        print(json.dumps({"valid_structure": not errors, "errors": errors, "warnings": warnings, "executed": False, "safe_to_run": "not_assessed"}, indent=2))
        return 1 if errors else 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(json.dumps({"valid_structure": False, "errors": [str(exc)], "executed": False}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
