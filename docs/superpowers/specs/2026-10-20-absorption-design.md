# Toad Sage absorption implementation design

The supplied mission is the design brief and authorizes autonomous implementation. Architectural work is split into independently testable browser, package, engine, lab and mission modules. Routine design and test decisions proceed without repeated approval. The final user message ends mid-sentence at “Make missions id”; implement durable identifiers and idempotent checkpoints as the conservative interpretation.

## Boundaries

Preserve the static GitHub Pages site, curriculum exports, empathy data and v1 import support. The browser is a private on-device inbox; it never uploads feeds or connects to an execution endpoint. A stdlib-only Python 3.11+ CLI manages a SQLite catalog outside the repository, exporting portable versioned JSON. An allowlisted static deployment excludes runtime data.

## Packages and statuses

Use toad-ability-v2 manifests with bounded text files, safe portable paths, explicit structured Python/unittest test specifications, dependencies and permissions. Keep unknown metadata in extensions; retain legacy originals. Migrate v1 feed, manifest and library data without accepting imported claims of testing or installation. Recorded events drive received, inspected, needs_review, ready_for_testing, testing, failed, verified, installed and archived. Structural checks and model answers cannot verify a package.

## Browser workflow

Paste or attach supported text/source files, optionally name the candidate, press Feed Toad once. Classify and save atomically, then show a confirmation and details. Include search, status/language filters, edits, archive/delete, selected/full backup export, additive import and corrupt-storage recovery. Preserve pasted input after errors, render untrusted data as text, and disclose unavailable storage and assets. Avoid a service-worker cache and version static assets.

## Local pipeline

Normalize input without executing it; inspect Python with ast, JSON with a strict parser, identify dependencies/OS hints, record observations separately from assumptions, and flag operations/secrets without certifying safety. ZIP intake is in-memory, bounded and rejects traversal, symlinks, collisions, encrypted entries and expansion bombs. URLs are preserved as unverified references; automatic remote retrieval is deferred. SQLite transactions support atomic ingestion, duplicate identity, bounded operation leases, logs and durable missions.

## Restricted laboratory and assimilation

No host execution fallback. A trusted local Docker worker uses a prebuilt local image resolved to an immutable ID, no network, no bind mounts, no credentials, read-only root, nonroot UID, dropped capabilities, default seccomp, no-new-privileges, bounded tmpfs, processes, CPU, memory, output and elapsed time. Transfer packages via bounded stdin, never shell commands or package hooks. Each configured test runs in a disposable container; cleanup runs after every outcome. Tests are evidence of configured behavior, not proof against malicious code. Live verification is blocked when Docker/required isolation is unavailable. Installation means a versioned sandbox-only registry, never importing a module into the host core. Activation requires a local receipt bound to the current digest and an empty permission grant; prior versions and rollback remain available.

## Model and missions

Ollama is optional and loopback-only by default, with bounded JSON responses and deterministic options. No paid API dependency and no model downloads. Model output is untrusted package data. Missions plan, find relevant catalog entries, generate candidates, inspect, test, attempt bounded source-only repairs, package results and report outcomes. Freeze tests and permissions during repairs. Reserve budgets before external calls, retain checkpoints and repair history, honor pause/cancel between bounded operations, and fail closed on unavailable Docker/Ollama. No installation is automatic.

## Validation

Run existing tests plus independent ingestion/path/ZIP/migration tests, cross-language export interoperability, SQLite/CLI integration, worker-boundary and failure tests, a local fake Ollama HTTP server, mission state/budget/repair tests, Node catalog tests and Playwright iPhone-sized Chromium/WebKit browser tests when available. Provide opt-in local containment probes; GitHub Actions runs trusted project tests only, never submitted candidates.
