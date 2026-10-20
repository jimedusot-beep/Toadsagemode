"""Local ability catalog; cataloging is not installing or executing."""
import json
from pathlib import Path

def add_record(catalog_path, package, status="unverified"):
    if status not in ("unverified", "validated", "tested", "rejected"):
        raise ValueError("invalid status")
    catalog_path = Path(catalog_path)
    data = json.loads(catalog_path.read_text()) if catalog_path.exists() else {"schema": "toad-library-v1", "abilities": []}
    if data.get("schema") != "toad-library-v1" or not isinstance(data.get("abilities"), list):
        raise ValueError("unsupported catalog")
    item = {"name": package["name"], "version": package["version"], "description": package.get("description", ""), "status": status, "installed": False, "source": "manual_import"}
    data["abilities"] = [x for x in data["abilities"] if (x.get("name"), x.get("version")) != (item["name"], item["version"])]
    data["abilities"].append(item)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    temp = catalog_path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n")
    temp.replace(catalog_path)
    return item
