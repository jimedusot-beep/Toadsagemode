# Development ledger — absorption engine

Plan: docs/superpowers/plans/2026-10-20-absorption-engine.md
Baseline: f6e9d0939493cdbcd21d9c57b82e12ab38efc034

- Audit: baseline Python 9/9; JavaScript syntax passes; documented confirmed gaps and unverified phone/root deployment failures.
- Decision: implement inline in a fresh clone on codex/absorption-engine. The user explicitly authorized autonomous design, fixes and tests; no repeated design approval gates.
- Decision: interpret truncated final phrase as mission identifiers plus idempotent checkpoints; leave unknown additional requirements unclaimed.
- Decision: keep runtime data outside the repository and publish only allowlisted static assets.
- Integration: browser v2 exports and Python migrations share manifest/files/content semantics; imported trust claims always downgrade.
- Integration: worker receipts bind normalized manifests; mission repair preserves tests/permissions; activation stays sandbox-only.
- Task 1: complete. Confirmed direct validator size/permission acceptance and legacy catalog content loss with failing regression tests, then repaired them; exact historical phone failure remains unverified.
- Tasks 2/3: v2 browser catalog and UI implemented; Node 7/7 and Python 32/32 pass. CLI lifecycle tested through real subprocesses. WebKit download succeeded; required shared libraries are being prepared for actual browser checks.
- Decision: static report compatibility includes explicit assumptions; URLs are retained without automatic retrieval; legacy shell test strings are retained but disabled.
- Task 4: worker, structured receipts and versioned sandbox-only activation/rollback implemented; Python suite 46/46. Tests use Docker API/process boundary doubles. Live smoke command returns blocked (Docker executable unavailable), as required.
- Decision: require Linux cgroup v2 and positive enforcement reporting, inspect each created container, transfer only bounded stdin, and keep no host mounts. Unsupported hosts remain blocked.
- Decision: `installed` means sandbox-only registry activation with no host imports or expanded grants. Current and rollback versions cannot be deleted accidentally.
- Task 5: complete at the interface/orchestration level. Python suite 60/60; Ollama adapter exercised through a real local HTTP fixture; mission lifecycle, bounded source repair, frozen tests, budgets, checkpoint resume, blocked Docker/model and cancellation covered. Successful mission execution uses explicit doubles; live inference/containment are not claimed.
- Live CLI check: creating a calculator mission saved a real ID; run stopped at generation with an Ollama connection-refused reason, model_calls=1/test_runs=0. No success or package was fabricated.

- Independent whole-branch review completed against c9f7b7e; four Important findings reproduced: whole-operation Ollama deadline, abandoned mission time accounting, successful retest snapshot compatibility, and full-storage recovery. All received failing regressions before verification of fixes.
- Final: Ruling: regraded archive-member collision from Minor to Important — duplicate members silently discarded source despite the explicit preservation/path contract — cost if ignored: ambiguous packages and lost source. Fixed with archive-level collision checks and regression inputs.
- Final: fixed slow-trickle timeout — trusted transport runs in a bounded helper process; localhost HTTP fixture regression RED→GREEN. No candidate Python executes on the host.
- Final: fixed crash/reclaim time reset — reserve remaining time before work; an abandoned lease conservatively charges the reservation. Regression uses a trusted crash subprocess. Cost: a short unclean exit may consume the remaining mission allowance; source/checkpoints remain.
- Final: fixed retest/reinstall — snapshot's original local receipt and newest successful local receipt are both checked independently; unchanged versions can reactivate. Regression RED→GREEN.
- Final: fixed full-storage read lockout — read validity stays separate from failed probe writes; actual WebKit regression confirms export and smaller deletion recover space. Pre-fix snapshot times out waiting for export; repaired snapshot passes.
- Final: additional contract fixes — invalid manifest errors no longer swallowed, browser permissions/dependencies align with Python, larger v2 originals retained, and the legacy converter preserves source/version/unknown metadata. Node and Python regressions RED→GREEN.
- Final: Ruling on declined live containment/inference — unavailable Docker/Ollama remain blocked and unverified, as the user's mission permits; cost: actual host validation is still required.
- Final: Ruling on candidate-authored test assertions — test success is limited evidence of configured behavior, not a safety certification; sandbox-only grants remain empty. Cost: inadequate tests can miss logical/malicious behavior, so application-quality evaluation remains necessary.
- Deferred minors: none.

- PR follow-up: reproduced and repaired all three automated review findings before merge. POSIX workspace/database/sidecars are secured before SQLite opens (failure blocks opening); ZIP metadata no longer consumes the 40-source allowance; archive restore retains verified status only with a matching successful local Docker receipt and unchanged package digest. Seven regressions fail before the fixes and pass afterward; complete Python suite 73/73 and Node 10/10.

- Post-deployment follow-up: added offline `doctor` and explicit `doctor --probe` with separate library/testing/mission prerequisites, metadata-only dependency calls, fail-closed workspace errors and no containment claim. Reproduced a new export privacy defect under umask 000 and corrected exclusive backup creation to mode 0600; force exports retain atomic replacement. Actual host report: library ready, Docker/model blocked. Python 84/84 and Node 10/10 pass; real catalogs and HTTP metadata fixtures plus explicit Docker boundary doubles cover diagnostics.
- Readiness review: independent reviewer reproduced malformed Docker info causing an unstructured exception or false-ready security metadata. The parser now rejects non-object info and non-list/non-string security options. New regression failed for null/list/object cases before the repair and passes afterward; reviewer confirmed the finding resolved.

- Phone-only follow-up on codex/phone-drafts: WebKit reproduced unsent text loss on reload and stale tabs replacing another saved feed. Added tab-local bounded draft recovery, explicit draft download/import, attachment re-selection, no trust promotion, and cooperative Web Locks plus captured-base write guards. Storage events and exports refresh current data; pending metadata edits are preserved with an explicit copy/reload conflict message.
- Phone interruption regressions additionally caught pre-await library capture during backup import and implementation-stage unreadable-draft cleanup/metadata-render loss. Repairs now preserve intervening feeds, newer editor changes and raw unreadable drafts. Local checks: Python84/84, Node12/12 and eleven new actual WebKit phone scenarios plus the full existing inbox regression. Physical iPhone checks remain separate; no computer, model or execution connection was added to the public page.
