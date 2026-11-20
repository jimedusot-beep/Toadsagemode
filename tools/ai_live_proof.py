"""Opt-in REAL Ollama → frozen checks → inert AI source proof for an iPad cloud host.

Default: metadata only; never installs/models/downloads/executes candidate code.
--probe: one LOCAL Ollama /api/tags request, not generation.
--run: one genuine local Ollama generation via existing immutable plan and
quarantine pipelines, only with TOAD_ALLOW_REAL_OLLAMA_PROOF=YES.

CI must NEVER run --run and MUST NOT confuse test doubles with live proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from toad_core.engine import default_workspace
from toad_core.models import ModelConfig, OllamaAdapter
from toad_core.schema import PackageError
from toad_core.web_acceptance import FrozenWebAcceptance
from toad_core.web_codegen import QuarantinedWebGenerator

SCHEMA = "toad-local-ollama-live-proof-v1"
GOAL = (
    "Build an original, offline Flashcard Practice web page. "
    "Show a question and a button with id 'flip' that reveals an answer "
    "in an element with id 'answer'. Add a clear, mobile-friendly layout. "
    "Use only three source files: index.html, styles.css and app.js. "
    "Do not use external libraries, remote requests, accounts or secrets."
)
# Fixed by the trusted operator BEFORE inference and never sent to the model.
CHECKS = (
    {"kind": "title", "expected": "Flashcard Practice"},
    {"kind": "click_text", "selector": "#flip",
     "target": "#answer", "contains": "Answer"},
)


def _allowed() -> bool:
    # This proof is ZERO PAID API and never attempts a remote model service.
    return (
        os.environ.get("TOAD_MODEL_PROVIDER", "ollama") == "ollama"
        and os.environ.get("TOAD_ALLOW_PAID_AI") != "YES"
    )


def cold_status() -> dict:
    """No network, model invocation, filesystem writes or credentials."""
    if _allowed():
        cfg = ModelConfig.from_environment()
        selected = cfg.model
        destination = "loopback_only"
    else:
        selected = None
        destination = "blocked_nonlocal_or_paid_provider"
    return {
        "schema": SCHEMA,
        "status": "not_run",
        "paid_ai_permitted": False,
        "provider": os.environ.get("TOAD_MODEL_PROVIDER", "ollama"),
        "model": selected,
        "model_endpoint": destination,
        "model_connection_verified": False,
        "model_response_received": False,
        "candidate_executed": False,
        "browser_tested": False,
        "deployed": False,
        "release_allowed": False,
    }


def model_probe() -> dict:
    """Actual non-generating Ollama model listing on configured loopback."""
    if not _allowed():
        return {
            **cold_status(),
            "status": "blocked_paid_or_remote_provider",
            "probe_performed": False,
            "available": False,
        }
    adapter = OllamaAdapter(ModelConfig.from_environment())
    found = adapter.availability()  # Actual /api/tags HTTP request, not a mock.
    return {
        **cold_status(),
        "status": "model_available_not_inferred" if found["available"] else "model_unavailable",
        "probe_performed": True,
        "available": bool(found["available"]),
        "reason": None if found["available"] else
        "Ollama service or the selected model is not available on this host",
    }


def _workspace(path: Path | None) -> Path:
    root = Path(path if path is not None else default_workspace()).expanduser()
    if root.is_symlink():
        raise PackageError("Private workspace must not be a symlink")
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    if os.name == "posix" and root.stat().st_mode & 0o077:
        raise PackageError("Private workspace permissions must exclude group and others")
    return root


def _save_receipt(workspace: Path, receipt: dict) -> Path:
    folder = workspace / "live-ai-proofs"
    if folder.is_symlink():
        raise PackageError("Live proof folder must not be a symlink")
    folder.mkdir(mode=0o700, exist_ok=True)
    if os.name == "posix" and folder.stat().st_mode & 0o077:
        raise PackageError("Live proof folder must be owner-only")
    path = folder / (receipt["proof_id"] + ".json")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return path


def run_live(workspace: Path | None = None) -> dict:
    """No injectable model, worker, or success override in this live entrypoint."""
    if not _allowed():
        raise PackageError("Only the local loopback Ollama provider is permitted; paid AI is disabled")
    if os.environ.get("TOAD_ALLOW_REAL_OLLAMA_PROOF") != "YES":
        raise PackageError("Live inference requires TOAD_ALLOW_REAL_OLLAMA_PROOF=YES")
    cfg = ModelConfig.from_environment()
    adapter = OllamaAdapter(cfg)
    found = adapter.availability()
    if found["available"] is not True:
        raise PackageError(
            "No configured Ollama model was found on this host; "
            "no inference or proof was performed"
        )
    root = _workspace(workspace)
    frozen = FrozenWebAcceptance(root)
    # A frozen plan is written and validated BEFORE any generation call.
    plan = frozen.create_plan(GOAL, list(CHECKS))
    verified_plan = frozen.plan(plan["plan_id"])
    if verified_plan["model_wrote_checks"] is not False:
        raise PackageError("Acceptance checks must be independent of the model")

    started = time.monotonic()
    trial = frozen.draft(plan["plan_id"])  # One REAL Ollama /api/generate.
    elapsed_ms = int((time.monotonic() - started) * 1000)

    # Reopen all three private, SHA-256-bound data records after generation.
    verified_trial = frozen.trial(trial["trial_id"])
    candidate = QuarantinedWebGenerator(root).review(trial["source_draft_id"])
    dry = frozen.test(trial["trial_id"])  # Always no execution (no --run).
    if any((
        candidate["source"] != "loopback_ollama",
        candidate["status"] != "quarantined_unverified",
        candidate["draft_sha256"] != trial["source_sha256"],
        verified_trial["source_sha256"] != trial["source_sha256"],
        verified_trial["checks_sha256"] != verified_plan["checks_sha256"],
        candidate["executed"] is not False,
        candidate["tested"] is not False,
        candidate["deployed"] is not False,
        candidate["release_allowed"] is not False,
        dry["executed"] is not False,
        dry["passed"] is not False,
        dry["receipt"] is not None,
    )):
        raise PackageError("Model/source/frozen-test evidence disagrees; do not record a live proof")

    report = {
        "schema": SCHEMA,
        "proof_id": uuid.uuid4().hex,
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "evidence_class": "operator_host_self_report_not_independently_attested",
        "status": "live_ollama_manifest_received_quarantined_unverified",
        "provider": "loopback_ollama",
        "model": cfg.model,
        "model_registry_probe_performed": True,
        "model_registry_showed_selected_model": True,
        "real_model_request_path_used": True,
        "live_response_record_created": True,
        "generation_elapsed_ms": elapsed_ms,
        "goal_sha256": hashlib.sha256(GOAL.encode("utf-8")).hexdigest(),
        "acceptance_plan_id": plan["plan_id"],
        "acceptance_plan_sha256": verified_plan["plan_sha256"],
        "frozen_checks_sha256": verified_plan["checks_sha256"],
        "model_received_frozen_checks": False,
        "trial_id": trial["trial_id"],
        "source_draft_id": trial["source_draft_id"],
        "source_sha256": candidate["draft_sha256"],
        "source_file_sha256": candidate["file_sha256"],
        "risk_flags": candidate["risk_flags"],
        "source_validation": "bounded_manifest_and_private_sha256_only",
        "independent_docker_receipt": None,
        "candidate_executed": False,
        "browser_tested": False,
        "code_quality_verified": False,
        "deployed": False,
        "release_allowed": False,
        "owner_review_required": True,
    }
    receipt_path = _save_receipt(root, report)
    # Do not include model-authored source, secrets or any private paths.
    return {
        **report,
        "receipt_saved_privately": True,
        "receipt_file_name": receipt_path.name,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="One opt-in LOCAL Ollama source draft and private inert proof"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--probe", action="store_true",
                       help="Real local /api/tags probe; NO generation")
    group.add_argument("--run", action="store_true",
                       help="Requires TOAD_ALLOW_REAL_OLLAMA_PROOF=YES; never executes app")
    parser.add_argument("--workspace", type=Path, default=None,
                        help="Private workspace outside the source checkout")
    args = parser.parse_args(argv)
    try:
        result = run_live(args.workspace) if args.run else (
            model_probe() if args.probe else cold_status()
        )
    except (PackageError, ValueError, OSError, RuntimeError):
        # Avoid leaking raw provider response text or private host details.
        print(json.dumps({
            "schema": SCHEMA,
            "status": "blocked_no_live_proof",
            "live_response_record_created": False,
            "candidate_executed": False,
            "deployed": False,
            "reason": "Prerequisite unavailable, model rejected or proof validation failed",
        }, indent=2))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.probe:
        return 0 if result["available"] else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
