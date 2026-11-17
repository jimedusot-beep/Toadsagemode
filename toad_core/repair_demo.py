"""Opt-in broken-calculator experiment for the existing restricted agent.

Production path: local Ollama + a verified restricted Docker worker.
Dependency injection exists exclusively for explicitly labelled CI rehearsals.
No shell tool, host execution fallback, installation or deploy action is used.
"""
from __future__ import annotations

import json
import uuid

from .controlled_agent import ControlledAgent
from .experiment_review import compare_candidates
from .repair import validate_repair
from .schema import package_digest

BROKEN_SOURCE = """def add(a, b):
    return a + b


def subtract(a, b):
    return a + b  # Intentionally wrong for the repair experiment


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
"""

FIXED_SOURCE = BROKEN_SOURCE.replace(
    "return a + b  # Intentionally wrong for the repair experiment",
    "return a - b",
)

FROZEN_TESTS = """import unittest
from calculator import add, subtract, multiply, divide


class CalculatorTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

    def test_subtract(self):
        self.assertEqual(subtract(7, 2), 5)
        self.assertEqual(subtract(-4, -3), -1)

    def test_multiply(self):
        self.assertEqual(multiply(-3, 4), -12)

    def test_divide(self):
        self.assertEqual(divide(9, 2), 4.5)

    def test_divide_by_zero(self):
        with self.assertRaises(ValueError):
            divide(1, 0)


if __name__ == "__main__":
    unittest.main()
"""


# Independent regression cases are not included in the agent's editable
# candidate. They are supplied only AFTER the proposed fix is frozen.
HOLDOUT_TESTS = """import unittest
from calculator import add, subtract, multiply, divide


class HiddenAcceptanceCases(unittest.TestCase):
    def test_subtraction_across_signs_and_zero(self):
        for a, b in [(0, 0), (17, 99), (-7, 5), (13, -11),
                     (1000, 100), (0.5, 0.75), (-2.5, -4.25)]:
            with self.subTest(a=a, b=b):
                self.assertEqual(subtract(a, b), a - b)

    def test_other_calculator_operations(self):
        self.assertEqual(add(-3, 9), 6)
        self.assertEqual(multiply(-0.5, 8), -4)
        self.assertEqual(divide(-9, 2), -4.5)
        with self.assertRaises(ValueError):
            divide(-12, 0)
"""


def fixture():
    """Only source under calculator.py is permitted to change."""
    return {
        "schema": "toad-ability-v2",
        "name": "toad-calculator-repair-lab",
        "version": "0.1.0",
        "description": "Deliberately broken standard-library calculator with frozen tests",
        "files": [
            {"path": "calculator.py", "content": BROKEN_SOURCE},
            {"path": "tests/test_calculator.py", "content": FROZEN_TESTS},
        ],
        "entrypoint": "calculator.py",
        "permissions": [],
        "dependencies": [],
        "tests": [{"kind": "unittest", "path": "tests"}],
    }


def receipt_summary(receipt):
    if not receipt:
        return None
    return {
        "id": receipt.get("id"),
        "candidate_id": receipt.get("candidate_id"),
        "digest": receipt.get("digest"),
        "backend": receipt.get("backend"),
        "image_id": receipt.get("image_id"),
        "executed": receipt.get("executed") is True,
        "passed": receipt.get("passed") is True,
        "cleanup_ok": receipt.get("cleanup_ok") is True,
        "blocked_reason": receipt.get("blocked_reason"),
        "test_categories": [t.get("category") for t in receipt.get("tests", [])],
    }


def strong_receipt(receipt, candidate, *, should_pass):
    """Check evidence for the exact source; a double can satisfy this in tests."""
    return bool(
        receipt and receipt.get("backend") == "docker"
        and receipt.get("candidate_id") == candidate["id"]
        and receipt.get("digest") == candidate["digest"]
        and receipt.get("executed") is True
        and receipt.get("cleanup_ok") is True
        and receipt.get("passed") is should_pass
        and len(receipt.get("tests", [])) == len(candidate["manifest"]["tests"])
        and all(t.get("executed") is True and t.get("cleanup_ok") is True
                for t in receipt["tests"])
    )


def run_experiment(engine, *, model=None, worker=None, trajectory_id=None):
    """Fail closed unless actual or explicitly doubled pre/post-test evidence exists.

    CI tests inject doubles; output then says rehearsal_passed, never live verified.
    With neither dependency injected, execution goes through local Docker/Ollama.
    """
    injected = model is not None or worker is not None
    mode = "test_double_rehearsal" if injected else "local_docker_ollama"
    identifier = trajectory_id or ("calculator-" + uuid.uuid4().hex[:16])
    report = {
        "schema": "toad-calculator-repair-experiment-v1",
        "trajectory_id": identifier,
        "evidence_mode": mode,
        "status": "blocked",
        "owner_review_required": True,
        "installation_performed": False,
        "deployment_performed": False,
        "baseline": None,
        "repair": None,
        "holdout": None,
        "reason": None,
    }
    original = engine.ingest_package(fixture(), source="trusted-broken-calculator-demo")
    report["original_candidate_id"] = original["id"]
    report["original_digest"] = original["digest"]
    baseline = engine.test(original["id"], worker=worker)
    report["baseline"] = receipt_summary(baseline)
    if not strong_receipt(baseline, original, should_pass=False) or not any(
        t.get("category") == "test_failure" and t.get("passed") is False
        for t in baseline.get("tests", [])
    ):
        report["reason"] = "The original defect was not proven by a real failed test; no repair attempted."
        return report

    goal = (
        "Repair the calculator candidate after its subtraction regression test failed. "
        "First read calculator.py and tests/test_calculator.py using read_file. "
        "Only propose an edit to calculator.py; never modify the frozen tests. "
        "Run test_candidate on the NEW candidate ID produced by propose_edit. "
        "Finish by naming that new candidate ID only after a passed test; "
        "otherwise explain the blocker. No shell commands or permission changes."
    )
    agent = ControlledAgent(engine, identifier, candidate_id=original["id"],
                            model=model, worker=worker)
    state = agent.run(goal)
    report["agent_status"] = state["status"]
    report["agent_actions"] = [a["tool"] for a in state["actions"]]
    report["trajectory_path"] = str(agent.path)
    if state["status"] != "awaiting_review" or state.get("verification") != "verified":
        report["reason"] = state.get("blocked_reason") or "Agent did not produce an evidence-backed review candidate."
        return report

    final_id = state.get("final_candidate_id")
    if final_id == original["id"]:
        report["reason"] = "Original failing revision cannot count as repaired."
        return report
    fixed = engine.get(final_id)
    receipt = engine.store.latest_receipt(final_id)
    report["repair"] = receipt_summary(receipt)
    if not strong_receipt(receipt, fixed, should_pass=True):
        report["reason"] = "The repaired candidate lacks bound passing test evidence."
        return report
    try:
        _, changed = validate_repair(original["manifest"], fixed["manifest"])
    except ValueError as exc:
        report["reason"] = "Repair violated the frozen-test or source-only contract: " + str(exc)
        return report
    if changed != ["calculator.py"]:
        report["reason"] = "Only calculator.py may change in this experiment."
        return report
    reports = [a["observation"] for a in state["actions"] if a["tool"] == "propose_edit"]
    if not reports or not any(x.get("candidate_id") == final_id for x in reports):
        report["reason"] = "No recorded source-edit proposal matched the final candidate."
        return report
    if not any(a["tool"] == "test_candidate" and
               a["observation"].get("passed") is True and
               a["observation"].get("executed") is True for a in state["actions"]):
        report["reason"] = "Agent did not directly observe a passing sandbox test."
        return report
    # Run independent holdout cases as a distinct package. The agent never
    # receives or edits this holdout source; it remains a second Docker check
    # of identical candidate source bytes with extra acceptance requirements.
    acceptance_manifest = {
        **fixed["manifest"],
        "name": "toad-calculator-independent-acceptance",
        "files": [*fixed["manifest"]["files"],
                  {"path": "tests/test_holdout.py", "content": HOLDOUT_TESTS}],
    }
    acceptance = engine.ingest_package(acceptance_manifest, source="trusted-calculator-holdout")
    holdout_receipt = engine.test(acceptance["id"], worker=worker)
    report["holdout"] = receipt_summary(holdout_receipt)
    report["holdout_candidate_id"] = acceptance["id"]
    if not strong_receipt(holdout_receipt, acceptance, should_pass=True):
        report["reason"] = "Independent holdout tests did not pass; not ready for owner approval."
        return report
    source_a = next(f["content"] for f in fixed["manifest"]["files"] if f["path"] == "calculator.py")
    source_b = next(f["content"] for f in acceptance["manifest"]["files"] if f["path"] == "calculator.py")
    if source_a != source_b:
        report["reason"] = "Independent holdout source differed from proposed repair."
        return report
    # Compare the baseline and repaired revision using the same typed,
    # read-only gates as the CLI. This is a second check of evidence, not a
    # replacement for the independent holdout above.
    comparison = compare_candidates(engine, original["id"], final_id)
    report["comparison"] = comparison
    if (comparison["status"] != "comparable"
            or comparison["assessment"] != "challenger_improved_test_outcome"):
        report["reason"] = "Candidate comparison failed or the repair did not improve the frozen test outcome."
        return report
    report["holdout_passed"] = True
    report["changed_paths"] = changed
    report["final_candidate_id"] = final_id
    report["final_digest"] = package_digest(fixed["manifest"])
    report["proposed_diff"] = next(x.get("diff", "") for x in reports if x.get("candidate_id") == final_id)
    report["tests_unchanged"] = original["manifest"]["tests"] == fixed["manifest"]["tests"]
    report["status"] = "rehearsal_passed" if injected else "ready_for_owner_review"
    report["reason"] = (
        "Only test doubles ran. This is NOT real Docker or model evidence."
        if injected else
        "Locally reported Docker/Ollama evidence requires independent owner review."
    )
    return report
