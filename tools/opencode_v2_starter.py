"""Reviewable, interactive OpenCode V2 experiment. Never executes during validation."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "integrations" / "opencode-v2" / "opencode.jsonc"
VERSION = ROOT / "integrations" / "opencode-v2" / "version.txt"
APPROVED_MODEL = "opencode/deepseek-v4.1-flash-free"

# Exact allow/ask policy: additions cannot silently expand authority.
PERMISSION_RULES = [
    ("*", "*", "deny"),
    ("read", "*", "allow"),
    ("glob", "*", "allow"),
    ("grep", "*", "allow"),
    ("question", "*", "allow"),
    ("shell", "*", "ask"),
    ("edit", "*", "ask"),
    ("read", "*.env", "deny"),
    ("read", "*.env.*", "deny"),
    ("edit", "*.env", "deny"),
    ("edit", "*.env.*", "deny"),
    ("edit", "*opencode.jsonc", "deny"),
    ("edit", "*opencode.json", "deny"),
    ("edit", "*.opencode/*", "deny"),
    ("shell", "git push *", "deny"),
    ("shell", "sudo *", "deny"),
    ("shell", "rm -rf *", "deny"),
    ("shell", "npm publish *", "deny"),
    ("external_directory", "*", "deny"),
    ("subagent", "*", "deny"),
    ("execute", "*", "deny"),
]
POLICY_RULES = [
    ("provider.use", "*", "deny"),
    ("provider.use", "opencode", "allow"),
    ("integration.connect", "*", "deny"),
    ("integration.use", "*", "deny"),
    ("integration.use", "opencode", "allow"),
    ("mcp.use", "*", "deny"),
    ("skill.use", "*", "deny"),
    ("plugin.use", "*", "deny"),
    ("websearch.use", "*", "deny"),
    ("tool.use", "external_directory:*", "deny"),
    ("tool.use", "read:*.env", "deny"),
    ("tool.use", "read:*.env.*", "deny"),
    ("tool.use", "edit:*.env", "deny"),
    ("tool.use", "edit:*.env.*", "deny"),
    ("tool.use", "edit:*opencode.jsonc", "deny"),
    ("tool.use", "edit:*opencode.json", "deny"),
    ("tool.use", "shell:git push *", "deny"),
    ("tool.use", "shell:sudo *", "deny"),
    ("tool.use", "shell:rm -rf *", "deny"),
    ("tool.use", "shell:npm publish *", "deny"),
]


def validate_config(path: Path = CONFIG) -> dict:
    """Fail closed on unknown keys, missing rules, changed order or unexpected grants."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"$schema", "model", "permissions", "policies"}:
        raise ValueError("Unexpected OpenCode settings; refusing to launch")
    if data["$schema"] != "https://opencode.ai/config.json":
        raise ValueError("Unexpected OpenCode schema")
    if data["model"] != APPROVED_MODEL:
        raise ValueError("Unapproved model; use the explicitly free test model only")
    for key, expected in (("permissions", PERMISSION_RULES), ("policies", POLICY_RULES)):
        rules = data[key]
        if not isinstance(rules, list):
            raise ValueError(f"{key} must be an ordered array")
        if any(not isinstance(r, dict) or set(r) != {"action", "resource", "effect"} for r in rules):
            raise ValueError(f"Invalid {key} entry")
        actual = [(r["action"], r["resource"], r["effect"]) for r in rules]
        if actual != expected:
            raise ValueError(f"{key} differs from reviewed fail-closed policy")
    return data


def pinned_version(path: Path = VERSION) -> str:
    pin = path.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"2\.\d+\.\d+", pin):
        raise ValueError("OpenCode version must be an exact V2 release")
    return pin


def verify_binary(pin: str, executable: str | None = None) -> str:
    executable = executable or shutil.which("opencode")
    if not executable:
        raise RuntimeError("OpenCode missing; install pinned @opencode/cli before --check")
    result = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, timeout=15, check=False
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    if result.returncode != 0 or not re.search(
        r"(?<![\d.])" + re.escape(pin) + r"(?![\w.-])", output
    ):
        raise RuntimeError(f"Expected OpenCode {pin}; executable returned: {output[:160]}")
    return executable


def isolated_environment(home: Path) -> dict[str, str]:
    """Never forward inherited API keys or repository credentials to the child."""
    env = {k: os.environ[k] for k in ("PATH", "TERM", "LANG", "LC_ALL", "TZ") if k in os.environ}
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["XDG_DATA_HOME"] = str(home / ".local" / "share")
    env["XDG_CACHE_HOME"] = str(home / ".cache")
    return env


def launch(executable: str) -> int:
    # An OS-level sandbox is REQUIRED for untrusted tasks; this is only a fresh
    # project and home. Use an otherwise empty disposable VM/Codespace.
    directory = Path(tempfile.mkdtemp(prefix="toad-opencode-v2-")).resolve()
    workspace = directory / "project"
    home = directory / "home"
    workspace.mkdir(mode=0o700)
    home.mkdir(mode=0o700)
    (workspace / "opencode.jsonc").write_bytes(CONFIG.read_bytes())
    # Freeze acceptance inputs before the first agent prompt. Read-only mode is
    # an audit cue, not protection against commands running as the same user.
    import hashlib
    frozen = {}
    for filename in ("CALCULATOR_MISSION.md", "calculator-acceptance.test.mjs"):
        src = ROOT / "integrations" / "opencode-v2" / filename
        dest = workspace / filename
        payload = src.read_bytes()
        dest.write_bytes(payload)
        dest.chmod(0o444)
        frozen[filename] = hashlib.sha256(payload).hexdigest()
    print("Frozen calculator test SHA256:", frozen["calculator-acceptance.test.mjs"], flush=True)
    print(f"Experiment directory: {directory}", flush=True)
    print("No host containment: run ONLY on a disposable host with no secrets.", flush=True)
    print("Approve each requested edit/shell command; choose a verified FREE model.", flush=True)
    print("Stop: Ctrl+C. Inspect source/test evidence, then delete this directory manually.", flush=True)
    code = subprocess.call([executable, "--standalone"], cwd=workspace, env=isolated_environment(home))
    altered = [name for name, expected in frozen.items()
               if not (workspace / name).is_file()
               or hashlib.sha256((workspace / name).read_bytes()).hexdigest() != expected]
    if altered:
        raise RuntimeError(f"Frozen acceptance inputs were modified: {altered}")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Opt-in OpenCode V2 readiness and launch")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--validate-config", action="store_true", help="Offline policy and version-pin check")
    group.add_argument("--check", action="store_true", help="Policy plus actual binary version check")
    group.add_argument("--launch", action="store_true", help="Launch private interactive OpenCode experiment")
    args = parser.parse_args(argv)
    try:
        validate_config()
        pin = pinned_version()
        if args.validate_config:
            print(f"Reviewed policy and version pin valid ({pin}); runtime NOT tested")
            return 0
        executable = verify_binary(pin)
        print(f"OpenCode executable verified: {executable} (version {pin})", flush=True)
        if args.launch:
            return launch(executable)
        print("No model call, execution task, or app acceptance test performed")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"OpenCode preflight BLOCKED: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
