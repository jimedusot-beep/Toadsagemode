# Absorption Engine Implementation Plan

> For agentic workers: use superpowers:executing-plans for inline implementation; one whole-branch review follows.

**Goal:** Implement a reliable mobile inbox and portable local absorption engine.
**Architecture:** Versioned packages connect browser intake to a transactional Python catalog, an isolated worker, optional Ollama and durable missions.
**Tech Stack:** Python 3.11+ standard library, vanilla JavaScript, SQLite, Docker, optional Ollama; Node/Playwright for development tests.
**Spec:** docs/superpowers/specs/2026-10-20-absorption-design.md

## Global Constraints

- No candidate execution on the host or GitHub Actions.
- No browser feed uploads, paid APIs or automatic dependency installation.
- Preserve compatible v1 data and unknown metadata.
- Python 3.11+; no runtime pip dependencies.
- A passing structure check or model claim cannot mark a package verified.
- Never modify other repositories.

## Review Focus

- Storage quota or corrupt JSON must preserve input and permit recovery.
- Imported verified/installed claims cannot create local verification evidence.
- Cross-platform path aliases and ZIP expansion must fail safely.
- Cleanup/output/time/resource failures must never become passing test receipts.
- Repeated/resumed missions must retain budgets and honor cancellation.

### Task 1: Audit and reproducible failures
Files: docs/audit/2026-10-20-baseline.md, tests/browser/inbox.cjs, tests/test_validator.py.
- [x] Record baseline tests, workflow evidence and actual host capabilities.
- [x] Run browser scenarios for one-button saving, persistence, quota and bad storage; record failures.
- [x] Add direct validator size/permission regression tests and observe failure.

### Task 2: Mobile inbox and catalog
Files: index.html, web/catalog.js, web/ability-library.js, web/styles.css, tests/web/catalog.test.cjs, tests/browser/inbox.cjs.
Interfaces: Catalog.createCandidate(text, options), normalizeLibrary(data), mergeLibraries(old, incoming); browser v2 export feeds local engine.
- [x] Test classification, normalization, unknown fields, duplicate detection and imported trust downgrades first.
- [x] Implement pure data logic and one-button UI with error recovery, edits, filters, backups and text previews.
- [x] Verify with Node tests and browser scenarios; preserve curriculum export.

### Task 3: Packages and local engine
Files: toad_core/schema.py, ingestion.py, inspection.py, storage.py, engine.py, cli.py, __main__.py, pyproject.toml, tools/validate_feed.py, tests/test_packages.py, test_engine.py, test_cli.py.
Interfaces: normalize_package(data), ingest_text(text, filename=None), inspect_package(package), Engine(workspace).ingest/inspect/export; CLI python -m toad_core.
- [x] Write and run failing schema/path/ZIP/migration and CLI lifecycle tests.
- [x] Implement bounded, nonexecuting ingestion and analysis, digest-bound records, SQLite transactions, queued inspection and portable export.
- [x] Fix legacy catalog loss and importer metadata preservation; run Python suite and browser-to-Python interoperability.

### Task 4: Restricted lab and versioned activation
Files: toad_core/lab.py, installation.py, lab/Dockerfile, lab/runner.py, tests/test_lab.py, test_installation.py, tools/lab_smoke.py, docs/LAB.md.
Interfaces: DockerWorker.run(package) -> structured result; Engine.test(candidate_id); registry activation requires a successful local digest-bound receipt.
- [x] Test no-Docker blocking, fixed command policy, time/output limits, failure/cleanup and receipt binding first.
- [x] Implement resource policy, bounded process runner, no-mount input, disposable tests and fail-closed results.
- [x] Implement sandbox-only versioned registry and rollback; test tamper and privilege refusal.
- [x] Run mocked-boundary tests; run live probes only if an appropriate Docker host exists.

### Task 5: Ollama and autonomous mission foundations
Files: toad_core/models.py, mission_engine.py, repair.py, tests/test_models.py, test_missions.py, docs/MISSIONS.md.
Interfaces: OllamaAdapter.generate_json(prompt), MissionEngine.create/run/pause/resume/cancel; uses Engine and DockerWorker only.
- [x] Test bounded HTTP, unavailable server, malicious/malformed model output, budgets, checkpoints, repairs and cancellation first.
- [x] Implement optional local adapter and persistent mission stages with fixed tests/privileges across repair attempts.
- [x] Verify offline library operation and deterministic mock end-to-end missions; record live limitations.

### Task 6: Integration, CI and delivery
Files: .github/workflows/validate.yml, pages.yml, tools/build_site.py, README.md, SETUP-ACER.md, SETUP-CODESPACES.md, HOST-STATUS.md, SITE_STATUS.md, docs/audit/2026-10-20-results.md.
- [x] Add behavioral static-build allowlist checks; implement Pages validation dependency and browser coverage.
- [x] Run full Python/Node/browser/CLI checks and inspect the mobile layout.
- [x] Review the whole branch, fix material issues with regression tests, and document demonstrated behavior and blocked live tests.
- [x] Commit and push a feature branch and open a reviewable PR; keep production deployment intact.

Completion notes: local checks and browser scenarios passed; live Docker/Ollama checks returned explicit blocked/unavailable outcomes, so their successful execution remains unverified. See docs/audit/2026-10-20-results.md for evidence and the independent review fixes. The branch/PR delivery step is recorded in the pull request itself.
