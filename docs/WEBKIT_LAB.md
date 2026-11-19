# Isolated AI WebKit acceptance worker — experimental, opt-in

## What this actually adds

This is a **different worker** from the existing Python-only Docker lab. The
new local Docker image has WebKit and a trusted Node.js/Playwright harness.
It can run a model-authored HTML/CSS/JavaScript draft **inside a disposable
browser container**, evaluate **independently supplied declarative checks**,
and return source/test hashes plus a bounded execution receipt.

It does not evaluate AI output on the host, in the Toad Sage Netlify website,
or in GitHub Actions. No preview URLs, public ports, web backend, automated
repairs, installation, or deployment are created by this worker.

**Current status:** code and policy tests in GitHub; real on-host Docker
containment and browser execution have **not yet been demonstrated**. A
CI-green policy test with fake Docker calls must not be described as live
sandbox certification. The local setup is optional and can fail closed.

## Trust and failure policy

- Trusted: Python worker, Node harness, approved Dockerfile/image, frozen
  user-authored acceptance checks, local Docker daemon/kernel. These
  components must not be writable by generated source.
- Untrusted: model-authored HTML/CSS/JS, its labels, browser log messages,
  preview output, generated network requests or claims of completion.
- No Docker host socket, source-tree bind mounts, credentials, extra Linux
  capabilities, new privileges, published ports or host networking enter
  candidate containers.
- Linux cgroup v2, enforceable resource limits, default seccomp, no mounts,
  read-only root filesystem, UID/GID 65532, 512-MiB memory/swap, 1 CPU,
  64 PIDs, tmpfs-limited /work (64 MiB) and /tmp (128 MiB), noexec/nosuid,
  bounded output and 30-second wall deadline. Immutable local image ID,
  `--pull=never`, Docker state inspection and forced cleanup.
- The trusted runner writes exactly **three** proposed files into the
  container's temporary /work directory and serves them only via its own
  loopback HTTP server. A strict CSP forbids external connections, inline
  scripts, framing and external images; the WebKit browser blocks any
  non-loopback-origin request. Docker's `--network=none` is an independent
  network restriction.
- Frozen acceptance checks permit `title`, `text`, `click_text`, or
  `fill_click_text` with short CSS selectors and expected strings. No
  arbitrary uploaded JavaScript tests, shell scripts, npm commands,
  package installs, model-supplied Docker flags or imports are accepted.
- Failure at *any* gate (host probe, image digest, container inspection,
  browser launch, test mismatch, crash, timeout, output bound, resource
  limits, malformed receipt or container cleanup) blocks success.
- Passing tests mean a **specific isolated execution** met its limited
  checks, **not** that the code is secure, production-ready, approved,
  or deployed. The output always says `release_allowed:false`.

### Why this is NOT a perfect security sandbox

Playwright's own documentation warns that its official Docker image is
for development/testing, not untrusted websites. Browser code can be
malicious; even with Docker restrictions a browser exploit or kernel bug
may break isolation. Therefore the **recommended live host is a dedicated,
disposable Linux VM**, with no private data or user credentials and no
privileged Docker daemon accessible to untrusted processes. Stop if a
hardening requirement cannot be met. We do not weaken Docker constraints
just to turn a red smoke test green.

The Playwright Docker base image supplies browsers/dependencies but **not
the Playwright npm package**. Our trusted Dockerfile installs a matching,
pinned `playwright@1.65.1` package. Build must be inspected and authorized
by the operator; candidate code never controls the Dockerfile.

References:
- [Official Playwright Docker security guidance](https://playwright.dev/docs/docker)
- [Official Playwright image versions](https://mcr.microsoft.com/product/playwright/tags)
- [Docker container resource controls](https://docs.docker.com/engine/containers/resource_constraints/)
- [Existing Toad Sage Python lab](LAB.md)

## Commands on an approved Linux Docker host (NOT on Netlify or in GitHub CI)

```sh
# Review the trusted Dockerfile and harness BEFORE the build.
docker build -t toad-sage-webkit-lab:1 web_lab

# Metadata only; does not execute candidate source.
python -m toad_core app web-lab-status

# Explicitly run fixed and safe smoke fixtures in a disposable container.
python tools/web_lab_smoke.py --run
```

**Expected:** `live_verified:true` with positive safe interaction passing
and negative deliberately wrong expectation failing. It must also report
cleanup success for both, immutable same image ID, and `executed:true`.
These are a **first sanity gate**, not a complete proof of containment.
Additional real security probes (network exfil, symlinks, filesystem,
process, disk and browser escape scenarios) are required before untrusted
web execution should be considered suitable beyond a dedicated VM.

### Independent acceptance checks

A trusted operator creates a separate short JSON file of expectations
before looking at or running AI-proposed source, for example:

```json
[
  {"kind":"title","expected":"Flashcard Practice"},
  {"kind":"click_text","selector":"#flip","target":"#flip","contains":"Back"}
]
```

The file must be from the operator, **not from the same AI model that
wrote the app**; otherwise Toad Sage could falsely pass weak self-written
tests. Model-generated source must already be stored in the private
`ai-web-drafts` quarantine.

```sh
# Read source and risk observations (no execution).
python -m toad_core app code-report DRAFT_ID
python -m toad_core app code-show DRAFT_ID

# Dry-run, no source execution. Reports how to explicitly authorize.
python -m toad_core app browser-test DRAFT_ID --checks /path/to/frozen-checks.json

# ONLY after security smoke probes and manual review of the candidate.
python -m toad_core app browser-test DRAFT_ID --checks /path/to/frozen-checks.json --run
```

The output embeds the source and frozen-check SHA-256 digests for
traceability and a closed-world WebKit receipt. A green run **does not**
mutate the stored draft's `quarantined_unverified` status: owner review,
restricted repair iterations, and an independent staging/release pipeline
are still separate milestones.

## CI evidence vs real evidence

`tests/test_web_lab.py` uses simulated Docker calls **only** to verify
the command policy, effective host configuration checks, receipt validation,
no-Docker refusal, malicious check rejection, cleanup behavior, CLI dry
run, and Node syntax. It does not start Docker or a browser.

The existing Mobile WebKit CI tests continue to execute **only fixed,
trusted task and notes templates**, never model-generated source. No
GitHub Actions job runs `tools/web_lab_smoke.py --run`.

Until a real disposable host passes the opt-in smoke and further
containment tests, treat this as a **tested execution interface**, not
a validated AI-powered app-development service.

## Next after first live proof

1. Add comprehensive live containment smoke probes for WebKit and
   external-access restrictions on a clean disposable VM.
2. Bind frozen acceptance checks to user requests before model generation.
3. Add repair attempts with source digests, independent holdout checks and
   bounded budgets; keep each candidate separate and reviewable.
4. Implement a read-only review UI, then owner-approved staging export
   and an explicitly approved Netlify preview; never silently deploy.
