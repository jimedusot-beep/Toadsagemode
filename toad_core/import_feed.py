"""Offline import of browser Ability Library JSON. This never executes content."""
import json
from pathlib import Path
from .library import add_record

MAX_IMPORT_BYTES = 2_000_000

def import_browser_library(source, destination):
    source = Path(source)
    with source.open("rb") as fh:
        raw = fh.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raise ValueError("Library export exceeds size limit")
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get("schema") != "toad-library-v1" or not isinstance(data.get("abilities"), list) or len(data["abilities"]) > 100:
        raise ValueError("Unsupported library format")
    normalized = []
    for item in data["abilities"]:
        if not isinstance(item, dict) or item.get("status") != "unverified" or item.get("installed") is not False:
            raise ValueError("Imported abilities must be unverified and not installed")
        name, body = item.get("name"), item.get("content")
        if not isinstance(name, str) or not isinstance(body, str) or len(body) > 250000:
            raise ValueError("Invalid record")
        import re
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", name):
            raise ValueError("Invalid name")
        normalized.append({"name": name, "version": "0.1.0", "description": item.get("description", "") if isinstance(item.get("description"), str) else "", "content": body, "kind": item.get("kind", "unknown")})
    dest = Path(destination)
    if dest.exists():
        raise ValueError("Destination exists; refuse to overwrite an existing library")
    dest.parent.mkdir(parents=True, exist_ok=True)
    catalog = {"schema": "toad-library-v1", "abilities": [
        {"name": x["name"], "version": x["version"], "description": x["description"], "kind": x["kind"], "source": "browser-import", "content": x["content"], "status": "unverified", "installed": False}
        for x in normalized
    ]}
    dest.write_text(json.dumps(catalog, indent=2) + "\n")
    return len(normalized)
