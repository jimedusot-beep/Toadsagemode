"""Explicit opt-in real calculator mission: no mocks and no host execution.

Usage: python tools/calculator_demo.py [--run]
Without --run prints readiness only. --run requires actual local Ollama
and restricted Docker lab; blocked prerequisites do not silently simulate.
"""
import argparse
import json
from pathlib import Path
from toad_core.readiness import readiness
from toad_core.engine import Engine
from toad_core.mission_engine import MissionEngine, MissionBudget

GOAL = ("Create a small Python standard-library-only calculator with add, subtract, multiply "
        "and divide functions. Handle division by zero with a clear ValueError. "
        "Write meaningful unittest tests for all four operations, zero division, and edge cases. "
        "Keep the code entirely offline and return a valid toad-ability-v2 manifest.")

def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--run", action="store_true", help="Actually call local Ollama and run restricted Docker tests")
    cli.add_argument("--workspace", help="Separate private local workspace")
    args = cli.parse_args()
    report = readiness(args.workspace, probe=True)
    print(json.dumps({"prerequisites": report["capabilities"], "checks": {k:v.get("status") for k,v in report["checks"].items()}}, indent=2))
    if not args.run:
        print("NO EXECUTION. To attempt a real demonstration after setup, add --run.")
        return 0
    if report["capabilities"]["missions"] != "ready":
        print("BLOCKED: Real Docker and Ollama prerequisites not ready. No mock fallback.")
        return 2
    engine = Engine(args.workspace)
    try:
        missions = MissionEngine(engine)
        mission = missions.create(GOAL, budget=MissionBudget(max_seconds=180, max_model_calls=6, max_test_runs=4, max_repairs=2))
        completed = missions.run(mission["id"], max_steps=35)
        print(json.dumps({"mission_id": mission["id"], "status": completed["status"],
                          "reason": completed.get("blocked_reason"), "artifacts": completed.get("artifacts", {}),
                          "last_test": completed.get("last_test", {})}, indent=2))
        if completed["status"] != "completed":
            return 3
        record = engine.get(completed["progress"]["candidate_id"])
        receipt = engine.store.latest_receipt(record["id"])
        if not receipt or not (receipt.get("passed") and receipt.get("executed") and receipt.get("backend")=="docker" and receipt.get("cleanup_ok")):
            raise RuntimeError("A completed result lacks real Docker evidence")
        for key in ("project_zip", "report", "guide"):
            if not Path(completed["artifacts"][key]).exists():
                raise RuntimeError("Mission output missing: " + key)
        print("PASS: real local model + restricted Docker test receipt + packaged artifacts.")
        return 0
    finally:
        engine.close()

if __name__=="__main__":
    raise SystemExit(main())
