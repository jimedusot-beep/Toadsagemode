"""Opt-in, independent local calculator build proof (no OpenCode or paid API).

Without --run, check readiness only. With --run, require real local Ollama,
restricted Docker containment probes, a generated project and an independently
supplied holdout unittest suite. A successful CLI run still needs owner review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from toad_core.engine import Engine
from toad_core.mission_engine import MissionEngine, MissionBudget
from toad_core.readiness import readiness
from toad_core.repair_demo import HOLDOUT_TESTS
from toad_core.schema import PackageError
from tools.lab_smoke import run_probes

GOAL = (
    "Create a small Python 3.11 standard-library-only calculator with a "
    "calculator.py module exporting add, subtract, multiply and divide functions. "
    "Handle division by zero with a clear ValueError. Write meaningful unittest "
    "tests for all four operations, zero division and edge cases. Keep all code "
    "offline and return a valid toad-ability-v2 manifest. Do not use external "
    "dependencies, OpenCode, or remote services."
)


def independent_holdout(engine, candidate_id, *, worker=None):
    """Run trusted tests against the model's unchanged source in the restricted lab.

    The optional worker is ONLY for explicitly labelled unit-test doubles.
    Live CLI use always passes worker=None and uses DockerWorker.
    """
    original = engine.get(candidate_id)
    prior = engine.store.latest_receipt(candidate_id)
    if (original["verification"] != "verified" or not prior
            or prior.get("candidate_id") != candidate_id
            or prior.get("digest") != original["digest"]
            or prior.get("backend") != "docker"
            or prior.get("executed") is not True
            or prior.get("passed") is not True
            or prior.get("cleanup_ok") is not True):
        raise RuntimeError("The generated candidate lacks its passing Docker receipt")

    source_files = [
        {"path": item["path"], "content": item["content"]}
        for item in original["manifest"]["files"]
        if not item["path"].startswith("tests/")
        and not item["path"].rsplit("/", 1)[-1].startswith("test_")
    ]
    modules = [item for item in source_files if item["path"] == "calculator.py"]
    if len(modules) != 1:
        raise RuntimeError("Generated project must contain a calculator.py module")
    if original["manifest"]["permissions"] or original["manifest"]["dependencies"]:
        raise RuntimeError("Holdout requires a permission-free, standard-library project")

    holdout_manifest = {
        "schema": "toad-ability-v2",
        "name": "independent-calculator-holdout",
        "version": "0.1.0",
        "description": "Trusted holdout tests for the unchanged generated calculator",
        "files": source_files + [
            {"path": "tests/test_calculator_holdout.py", "content": HOLDOUT_TESTS}
        ],
        "entrypoint": "calculator.py",
        "permissions": [],
        "dependencies": [],
        "tests": [{"kind": "unittest", "path": "tests"}],
    }
    holdout = engine.ingest_package(
        holdout_manifest, source="trusted-independent-calculator-holdout"
    )
    receipt = engine.test(holdout["id"], worker=worker)
    if (receipt.get("candidate_id") != holdout["id"]
            or receipt.get("digest") != holdout["digest"]
            or receipt.get("backend") != "docker"
            or receipt.get("executed") is not True
            or receipt.get("passed") is not True
            or receipt.get("cleanup_ok") is not True):
        raise RuntimeError("Independent calculator holdout did not pass in Docker")

    return {
        "status": "ready_for_owner_review",
        "original_candidate_id": candidate_id,
        "original_receipt_id": prior["id"],
        "holdout_candidate_id": holdout["id"],
        "holdout_receipt_id": receipt["id"],
        "source_sha256": hashlib.sha256(modules[0]["content"].encode("utf-8")).hexdigest(),
        "docker_image_id": receipt.get("image_id"),
        "owner_review_required": True,
        "installed": False,
        "deployed": False,
        "limitations": [
            "Tests are not a security or correctness guarantee.",
            "A local receipt must be independently reviewed on the actual host.",
        ],
    }


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--run", action="store_true",
                     help="Use real local Ollama and restricted Docker; no mocks")
    cli.add_argument("--workspace", help="Separate private local workspace")
    args = cli.parse_args()
    report = readiness(args.workspace, probe=True)
    print(json.dumps({
        "prerequisites": report["capabilities"],
        "checks": {k: v.get("status") for k, v in report["checks"].items()},
    }, indent=2))
    if not args.run:
        print("NO EXECUTION. To attempt a real demonstration after setup, add --run.")
        return 0
    if report["capabilities"]["missions"] != "ready":
        print("BLOCKED: Local Docker/Ollama prerequisites not ready. No mock fallback.")
        return 2

    containment = run_probes()
    if not containment.get("live_verified"):
        print("BLOCKED: Live Docker containment probes did not all pass.")
        return 2

    engine = Engine(args.workspace)
    try:
        missions = MissionEngine(engine)
        mission = missions.create(
            GOAL, budget=MissionBudget(
                max_seconds=180, max_model_calls=6, max_test_runs=4, max_repairs=2
            )
        )
        completed = missions.run(mission["id"], max_steps=35)
        print(json.dumps({
            "mission_id": mission["id"],
            "status": completed["status"],
            "reason": completed.get("blocked_reason"),
            "artifacts": completed.get("artifacts", {}),
            "repair_attempts": completed["usage"]["repairs"],
        }, indent=2))
        if completed["status"] != "completed":
            return 3
        for key in ("project_zip", "report", "guide"):
            if not Path(completed["artifacts"][key]).is_file():
                raise RuntimeError("Missing generated artifact: " + key)
        proof = independent_holdout(engine, completed["progress"]["candidate_id"])
        proof["mission_id"] = mission["id"]
        proof["repair_attempts"] = completed["usage"]["repairs"]
        path = Path(completed["artifacts"]["report"]).parent / "independent-proof.json"
        with path.open("x", encoding="utf-8") as output:
            json.dump(proof, output, indent=2)
            output.write("\n")
        print(json.dumps({"proof": proof, "proof_path": str(path)}, indent=2))
        print("PASS: local generation and two restricted Docker test suites; owner review required.")
        return 0
    except (PackageError, RuntimeError, OSError, KeyError) as exc:
        print("BLOCKED: " + str(exc))
        return 3
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
