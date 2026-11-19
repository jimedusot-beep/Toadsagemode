"""Fail-closed OpenCode V2 experiment launcher, NOT an OS security sandbox.

Static config checks are not runtime permission tests. No model calls on --check.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "integrations" / "opencode-v2" / "opencode.jsonc"
# An explicit snapshot: if any rule is removed, reordered or changed, preflight fails.
# Updating this baseline requires deliberate code review and a regression test update.
APPROVED_PERMISSIONS = [
    ("*", "*", "deny"),
    ("read", "*", "allow"),
    ("glob", "*", "allow"),
    ("grep", "*", "allow"),
    ("question", "*", "allow"),
    ("edit", "*", "ask"),
    ("shell", "*", "ask"),
    ("shell", "git push *", "deny"),
    ("shell", "sudo *", "deny"),
    ("shell", "rm -rf *", "deny"),
    ("external_directory", "*", "deny"),
    ("read", "*.env", "deny"),
    ("read", "*.env.*", "deny"),
    ("edit", "*.env", "deny"),
    ("edit", "*.env.*", "deny"),
]
APPROVED_POLICIES = [
    ("provider.use", "*", "deny"),
    ("provider.use", "opencode", "allow"),
    ("tool.use", "shell:git push *", "deny"),
    ("tool.use", "shell:sudo *", "deny"),
    ("tool.use", "shell:rm -rf *", "deny"),
    ("tool.use", "external_directory:*", "deny"),
    ("tool.use", "read:*.env", "deny"),
    ("tool.use", "read:*.env.*", "deny"),
    ("tool.use", "edit:*.env", "deny"),
    ("tool.use", "edit:*.env.*", "deny"),
    ("mcp.use", "*", "deny"),
    ("skill.use", "*", "deny"),
    ("plugin.use", "*", "deny"),
]
# These exact IDs were shown as free by OpenCode's official model catalog
# on 2026-11-19. Operator must check current price and data policies again.
FREE_MODEL_CANDIDATES = (
    "opencode/deepseek-v4.1-flash-free",
    "opencode/mimo-v2.6-flash-free",
)
VERSION_PATTERN = re.compile(r"^2\.(\d+)\.(\d+)(?:[-+][a-zA-Z0-9.-]+)?$")


def _strict_rules(data: object, field: str, expected: list[tuple[str, str, str]]) -> None:
    if not isinstance(data, dict) or not isinstance(data.get(field), list):
        raise ValueError(f"Missing {field} rule array")
    actual = []
    for rule in data[field]:
        if (not isinstance(rule, dict) or set(rule) != {"action", "resource", "effect"}
                or any(not isinstance(value, str) for value in rule.values())):
            raise ValueError(f"Unexpected {field} rule shape")
        actual.append((rule["action"], rule["resource"], rule["effect"]))
    if actual != expected:
        raise ValueError(f"{field} differs from the approved ordered fail-closed baseline")


def check_config(path: Path = CONFIG) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"$schema", "permissions", "policies"}:
        raise ValueError("Unexpected OpenCode config keys")
    if data["$schema"] != "https://opencode.ai/config.json":
        raise ValueError("Unexpected OpenCode config schema")
    _strict_rules(data, "permissions", APPROVED_PERMISSIONS)
    _strict_rules(data, "policies", APPROVED_POLICIES)


def installed_version(executable: str, expected: str) -> str:
    if not VERSION_PATTERN.fullmatch(expected):
        raise ValueError("--expected-version must be an exact 2.x.y release")
    minor, patch = map(int, VERSION_PATTERN.fullmatch(expected).groups())
    if (minor, patch) < (2, 2) or (minor == 2 and patch < 6):
        raise ValueError("OpenCode V2 >=2.2.6 is required for these policy controls")
    response = subprocess.run([executable, "--version"], capture_output=True, text=True,
                              check=True, timeout=15)
    observed = response.stdout.strip()
    # Official distributions may prefix the version with the executable name.
    parsed_version = observed.removeprefix("opencode ").strip()
    if parsed_version != expected:
        raise RuntimeError(f"OpenCode version mismatch: expected {expected}; found {observed!r}")
    return observed


def clean_environment(root: Path) -> dict[str, str]:
    # Whitelist instead of copying os.environ: no inherited API keys/tokens.
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
           "HOME": str(root / "home"),
           "XDG_CONFIG_HOME": str(root / "home" / ".config"),
           "XDG_DATA_HOME": str(root / "home" / ".local" / "share"),
           "XDG_CACHE_HOME": str(root / "home" / ".cache"),
           "XDG_STATE_HOME": str(root / "home" / ".local" / "state"),
           "TERM": os.environ.get("TERM", "xterm-256color"),
           "LANG": os.environ.get("LANG", "C.UTF-8")}
    for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        Path(env[key]).mkdir(parents=True, exist_ok=True, mode=0o700)
    return env


def launch(expected_version: str, model: str) -> int:
    check_config()
    if model not in FREE_MODEL_CANDIDATES:
        raise ValueError("Model not on the reviewed free-model candidate list")
    executable = shutil.which("opencode")
    if not executable:
        raise RuntimeError("OpenCode CLI missing; install a reviewed pinned @opencode/cli version")
    installed_version(executable, expected_version)
    root = Path(tempfile.mkdtemp(prefix="toad-opencode-v2-")).resolve()
    workspace = root / "app"
    workspace.mkdir(mode=0o700)
    (workspace / "opencode.jsonc").write_bytes(CONFIG.read_bytes())
    env = clean_environment(root)
    print(f"Fresh experiment workspace: {workspace}", flush=True)
    print(f"Verified CLI version: {expected_version}; selected candidate model: {model}", flush=True)
    print("NOT a host sandbox. Verify current $0 pricing and privacy terms before any model call.", flush=True)
    print("No robot files or credentials; approve individual shell and edit requests once only.", flush=True)
    # mini supports --model and --standalone per official CLI documentation.
    return subprocess.call([executable, "mini", "--standalone", "--model", model],
                           cwd=workspace, env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review or manually launch a disposable OpenCode V2 trial")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Static config check, no model call")
    group.add_argument("--launch", action="store_true", help="Interactive launch after pinned-version check")
    parser.add_argument("--expected-version", help="Exact installed version: 2.x.y (required on launch)")
    parser.add_argument("--model", choices=FREE_MODEL_CANDIDATES,
                        help="Explicit candidate-free model (required on launch)")
    args = parser.parse_args(argv)
    try:
        check_config()
        if not args.launch:
            executable = shutil.which("opencode")
            if args.expected_version:
                if not executable:
                    raise RuntimeError("OpenCode CLI missing for requested version check")
                installed_version(executable, args.expected_version)
            print("Configuration: approved ordered rules and hard-deny policies verified")
            print("OpenCode executable: " + (executable or "not installed"))
            print("No live model call or runtime permission test performed")
            return 0
        if not args.expected_version or not args.model:
            parser.error("--launch requires --expected-version and --model")
        return launch(args.expected_version, args.model)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        parser.exit(2, f"OpenCode preflight BLOCKED: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
