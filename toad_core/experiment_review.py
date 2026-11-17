"""Deterministic, read-only candidate comparison for owner-reviewed experiments.

Adapted *ideas* (not third-party code) from gitevolve's score-based experiments
(0BSD, https://github.com/mechakotik/gitevolve) and Agent Dialectic Resolver's
typed evidence and fail-closed gates (CC0,
https://github.com/spotrunner1/agent-dialectic-resolver).

This module does not call a model, run a candidate, mutate source, or approve
activation. Recorded lab receipts are *claims in a local database*, not
independent proof of physical container isolation: CI doubles can produce
receipt-shaped data. Real lab acceptance is a distinct operator task.
"""
from __future__ import annotations

import hashlib
import re

from .repair import validate_repair
from .schema import PackageError, json_bytes, package_digest

IMAGE_ID_RE = re.compile(r"sha256:[a-f0-9]{64}\Z")
LAB_POLICY_FIELDS = (
    "image", "timeout_seconds", "output_bytes", "memory_mb",
    "cpus", "pids", "disk_mb",
)


def _receipt_gates(record, receipt):
    """Pure checks for digest-bound stored records, never a safety certificate."""
    problems = []
    manifest = record["manifest"]
    digest = package_digest(manifest)
    tests = manifest["tests"]

    if record["digest"] != digest:
        problems.append("Candidate manifest digest mismatch")
    if manifest["permissions"] or manifest["dependencies"]:
        problems.append("Nonempty permissions/dependencies are not comparable")
    if not tests:
        problems.append("No immutable structured test specification")
    if not isinstance(receipt, dict):
        return {"valid": False, "problems": problems + ["No stored local test receipt"],
                "score": None, "receipt_id": None, "image_id": None,
                "policy": None, "passed": None}
    if receipt.get("candidate_id") != record["id"] or receipt.get("digest") != digest:
        problems.append("Receipt does not match candidate identity and source digest")
    if receipt.get("backend") != "docker":
        problems.append("Receipt backend is not the restricted Docker worker")
    if receipt.get("executed") is not True or receipt.get("cleanup_ok") is not True:
        problems.append("Execution or container cleanup not confirmed")
    image = receipt.get("image_id")
    if not isinstance(image, str) or IMAGE_ID_RE.fullmatch(image) is None:
        problems.append("Immutable lab image identifier missing")
    policy = receipt.get("policy")
    if (not isinstance(policy, dict)
            or any(key not in policy for key in LAB_POLICY_FIELDS)):
        problems.append("Complete test policy metadata missing")
    outcomes = receipt.get("tests")
    if not isinstance(outcomes, list) or not (1 <= len(outcomes) <= len(tests)):
        problems.append("Test count is missing or exceeds the frozen specification")
    else:
        for position, result in enumerate(outcomes):
            expected = tests[position]
            if (not isinstance(result, dict)
                    or result.get("index") != position
                    or result.get("kind") != expected["kind"]
                    or result.get("path") != expected["path"]
                    or result.get("executed") is not True
                    or result.get("cleanup_ok") is not True):
                problems.append("Test result metadata does not match its frozen specification")
                break
        completed = len(outcomes) == len(tests) and all(
            isinstance(item, dict) and item.get("passed") is True
            for item in outcomes
        )
        if receipt.get("passed") is True:
            if not completed or record.get("verification") != "verified":
                problems.append("Passing claim is incomplete or candidate not verified")
        elif receipt.get("passed") is False:
            # A genuine failing suite is valuable evidence; execution or lab
            # failures are NOT evidence of broken application behavior.
            if not any(isinstance(item, dict)
                       and item.get("passed") is False
                       and item.get("category") == "test_failure"
                       for item in outcomes):
                problems.append("Failed receipt lacks a meaningful failing test")
        else:
            problems.append("Receipt pass flag must be a boolean")
    valid = not problems
    return {
        "valid": valid,
        "problems": problems,
        "score": (int(receipt["passed"]) if valid else None),
        "passed": (receipt.get("passed") if valid else None),
        "receipt_id": receipt.get("id"),
        "image_id": image if isinstance(image, str) else None,
        "policy": policy if isinstance(policy, dict) else None,
    }


def compare_candidates(engine, baseline_id, challenger_id):
    """Compare frozen-test revisions from the private local catalog.

    Scores are deliberately binary: a complete passing test suite scores 1;
    an executed failing test scores 0. This is *not* a quality, speed, or
    general intelligence metric. A better score permits review, not adoption.
    The function only reads catalog data.
    """
    if baseline_id == challenger_id:
        raise PackageError("Select two different candidate revisions")

    baseline = engine.get(baseline_id)
    challenger = engine.get(challenger_id)
    before = _receipt_gates(baseline, engine.store.latest_receipt(baseline_id))
    after = _receipt_gates(challenger, engine.store.latest_receipt(challenger_id))
    gates = []

    def check(key, ok, explanation):
        gates.append({"gate": key, "passed": bool(ok),
                      "reason": None if ok else explanation})

    try:
        _, changed = validate_repair(baseline["manifest"], challenger["manifest"])
        contract_error = None
    except (PackageError, KeyError, TypeError, ValueError) as exc:
        changed = []
        contract_error = str(exc)
    check("frozen-repair-contract", contract_error is None,
          contract_error or "Source-only revision contract could not be established")
    check("baseline-receipt", before["valid"],
          "; ".join(before["problems"]) or "Baseline receipt invalid")
    check("challenger-receipt", after["valid"],
          "; ".join(after["problems"]) or "Challenger receipt invalid")
    same_image = bool(before["valid"] and after["valid"]
                      and before["image_id"] == after["image_id"])
    check("same-image", same_image,
          "Lab image changed or its immutable identifier is missing")
    same_policy = bool(before["valid"] and after["valid"]
                       and before["policy"] == after["policy"])
    check("same-policy", same_policy,
          "Lab resource policy changed or cannot be compared")

    comparable = all(g["passed"] for g in gates)
    b_score, c_score = before["score"], after["score"]
    if not comparable:
        assessment = "incomparable"
    elif c_score > b_score:
        assessment = "challenger_improved_test_outcome"
    elif c_score < b_score:
        assessment = "challenger_regressed"
    elif c_score == 1:
        assessment = "both_pass_no_quality_winner"
    else:
        assessment = "both_fail_no_winner"

    evidence = {
        "baseline": {"candidate_id": baseline_id, "digest": baseline["digest"],
                     "receipt_id": before["receipt_id"],
                     "binary_test_score": b_score},
        "challenger": {"candidate_id": challenger_id,
                       "digest": challenger["digest"],
                       "receipt_id": after["receipt_id"],
                       "binary_test_score": c_score},
        "gates": gates,
        "changed_paths": changed,
        "assessment": assessment,
    }
    fingerprint = hashlib.sha256(json_bytes(evidence)).hexdigest()
    return {
        "schema": "toad-candidate-comparison-v1",
        "status": "comparable" if comparable else "blocked",
        "assessment": assessment,
        "scores": {"baseline": b_score, "challenger": c_score},
        "changed_paths": changed,
        "gate_results": gates,
        "evidence": evidence,
        "evidence_sha256": fingerprint,
        "evidence_limitations": [
            "Catalog receipts can be produced by explicitly injected test doubles;",
            "Digest matching is not a signature or proof of Docker isolation.",
            "Binary test scores do not measure quality, performance or security.",
        ],
        "owner_review_required": True,
        "approved": False,
        "installed": False,
        "merged": False,
        "deployed": False,
    }
