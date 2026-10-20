"""Plan and record bounded missions; does not execute code."""
import json
from pathlib import Path

def create_mission(title, steps):
    if not isinstance(title, str) or not title.strip():
        raise ValueError("mission title required")
    if not isinstance(steps, list) or not steps or not all(isinstance(s, str) and s.strip() for s in steps):
        raise ValueError("nonempty steps required")
    return {"schema": "toad-mission-v1", "title": title.strip(), "status": "planned", "steps": [{"task": s.strip(), "status": "pending"} for s in steps]}

def save_mission(path, mission):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mission, indent=2) + "\n")
