"""Explicit opt-in: real local Docker smoke + Ollama calculator repair review.

No imported code runs on the host. The approved Docker lab is the only worker.
The public iPhone dashboard cannot invoke this script.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from toad_core.engine import Engine, default_workspace
from toad_core.readiness import readiness
from toad_core.repair_demo import run_experiment
from tools.lab_smoke import run_probes


def save_report(workspace, prefix, data):
    root = Path(workspace) / "experiment-reports"
    if root.is_symlink():
        raise ValueError("Refusing symlinked experiment reports directory")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / (prefix + ".json")
    if path.is_symlink():
        raise ValueError("Refusing symlinked report")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return str(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Opt-in local broken calculator agent exercise")
    parser.add_argument("--run", action="store_true",
                        help="Run containment probes, then real local Ollama and Docker if ready")
    parser.add_argument("--workspace", help="Private isolated catalog directory for this experiment")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace).expanduser() if args.workspace else default_workspace() / "experiments" / "broken-calculator"
    report = readiness(workspace, probe=True)
    if not args.run:
        print(json.dumps({"execution_performed": False,
                          "next": "Review docs/BROKEN_CALCULATOR_DEMO.md and run with --run after provisioning.",
                          "readiness": report["capabilities"]}, indent=2))
        return 0
    if report["capabilities"]["missions"] != "ready":
        print(json.dumps({"status": "blocked", "execution_performed": False,
                          "reason": "A local Docker lab and Ollama model are required; no fallback.",
                          "readiness": report["capabilities"]}, indent=2))
        return 2
    # The opt-in real run refuses to continue unless the live containment
    # smoke suite passes on this same execution host.
    smoke = run_probes()
    run_tag = uuid.uuid4().hex[:16]
    smoke_path = save_report(workspace, "containment-" + run_tag, smoke)
    if smoke.get("live_verified") is not True:
        print(json.dumps({"status": "blocked", "reason": "Live containment smoke failed",
                          "smoke_report": smoke_path}, indent=2))
        return 2
    engine = Engine(workspace)
    try:
        result = run_experiment(engine)
        result["containment_smoke_report"] = smoke_path
        result["evidence_mode"] = "local_docker_ollama"
        report_path = save_report(workspace, "repair-" + run_tag, result)
        print(json.dumps({"status": result["status"],
                          "baseline": result["baseline"],
                          "repair": result["repair"],
                          "reason": result["reason"],
                          "experiment_report": report_path,
                          "containment_smoke_report": smoke_path,
                          "owner_review_required": True}, indent=2))
        return 0 if result["status"] == "ready_for_owner_review" else 3
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
