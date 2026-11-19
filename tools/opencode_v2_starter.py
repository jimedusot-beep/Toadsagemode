"""Opt-in, reversible OpenCode V2 starter. No CLI installation or model call on --check."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "integrations" / "opencode-v2" / "opencode.jsonc"


def check() -> int:
    settings = json.loads(CONFIG.read_text(encoding="utf-8"))
    if not isinstance(settings.get("permissions"), list):
        raise RuntimeError("OpenCode V2 'permissions' array is missing")
    required = {
        ("shell", "*", "ask"),
        ("external_directory", "*", "deny"),
        ("shell", "git push *", "deny"),
    }
    actual = {
        (rule.get("action"), rule.get("resource"), rule.get("effect"))
        for rule in settings["permissions"]
    }
    if not required.issubset(actual):
        raise RuntimeError("OpenCode starter permission policy is incomplete")
    found = shutil.which("opencode")
    print("Configuration: valid JSON / expected V2 permissions present")
    print("OpenCode binary: " + (found if found else "not installed"))
    print("Status: configuration checked; no model run and no app test performed")
    return 0


def launch() -> int:
    check()
    executable = shutil.which("opencode")
    if executable is None:
        raise SystemExit(
            "OpenCode is not installed. On a dedicated development host, see "
            "https://opencode.ai/docs/ and install @opencode/cli."
        )
    # An isolated working folder is NOT a host security sandbox. Only run on
    # a trusted disposable VM/container without sensitive credentials.
    workspace = Path(tempfile.mkdtemp(prefix="toad-opencode-v2-")).resolve()
    (workspace / "opencode.jsonc").write_bytes(CONFIG.read_bytes())
    print(f"Disposable *project* folder: {workspace}", flush=True)
    print("This is NOT a sandbox. Agent shell commands still have host user privileges.", flush=True)
    print("Review every tool request. Do not allow deployments or access to other projects.", flush=True)
    print("Suggested first task: Build a simple calculator web app and run its tests.", flush=True)
    return subprocess.call([executable, "--standalone"], cwd=workspace)


def main() -> int:
    parser = argparse.ArgumentParser(description="Review OpenCode V2 preparation or launch an opt-in experiment")
    parser.add_argument("--check", action="store_true", help="Check config/binary; do not launch")
    parser.add_argument("--launch", action="store_true", help="Launch OpenCode in a new disposable project folder")
    args = parser.parse_args()
    if args.launch:
        return launch()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
