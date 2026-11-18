# Optional iPad-first development lab using GitHub Codespaces

**Status:** configuration proposed, not provisioned or verified on a live
Codespace. The owner must approve creating any Codespace and monitor usage.
This is a **temporary development laboratory**, not an always-on AI server
or a public deployment endpoint.

Toad Sage accepts generated Python candidates only in the restricted
`DockerWorker` from [LAB.md](LAB.md). GitHub Actions uses explicit
model/worker doubles for CI; **do not run `tools/lab_smoke.py --run` in
GitHub Actions**. These containment tests are for a reviewed interactive
Codespace (or a trusted dedicated Linux lab) only.

## Why Codespaces first?

- Browser-based VS Code works from an iPad and is tied to the existing
  Toad Sage GitHub repository.
- The optional `.devcontainer/devcontainer.json` adds **Docker-in-Docker**
  with a Linux Python 3.12 environment. The Docker daemon must still pass
  Toad's independent cgroup v2, seccomp, limits and cleanup checks.
- No VPS subscription or laptop is inherently required for the first
  interactive experiment.
- It is **not free without limits**: check your actual GitHub account's
  included compute/storage quota and budget before creating the Codespace.
  GitHub Free personal accounts currently document **120 core-hours and
  15 GB-month storage**, but this is a plan reference, not a claim about
  this user's balance. A 2-core environment consumes roughly 2 core-hours
  per running hour. Stopped Codespaces can still use storage.
- An idle Codespace can stop; it is **not a persistent job runner**.
  Backup the private catalog separately and do not store secrets in it.

Important: Docker-in-Docker requires a powerful container privilege
boundary. The Codespace operator's Docker socket is trusted infrastructure.
**Never mount or forward that socket to Toad's untrusted candidate
containers.** Avoid feeding untrusted code until the full containment
smoke tests pass. A Codespace itself is not a secure malware-analysis VM.

## Step A — Owner-controlled creation from the iPad

1. Open [Toad Sage on GitHub](https://github.com/jimedusot-beep/Toadsagemode).
2. Review the [development container configuration](../.devcontainer/devcontainer.json).
   For the first smoke trial, select the reviewed feature branch
   `feature/opt-in-codespaces-lab-20261118` (until its PR merges).
3. Choose **Code → Codespaces → Create codespace on selected branch**.
   GitHub must be logged in as an account with access to the repository.
4. Choose the smallest appropriate machine to control usage. If creation
   fails, is disabled, or requests payment, stop and review account
   quotas. Do **not** silently authorize a new charge or upgraded machine.
5. In Codespaces settings, set an appropriate idle timeout and check
   [budgets](https://github.com/settings/billing/budgets). Avoid
   enabling paid overage to run an experiment.
6. The browser VS Code terminal is a *trusted operator console*. Do
   not give the generated AI source general shell privileges.

No automatic `postCreateCommand` is configured. Creating the Codespace
pulls the approved Python base and Docker-in-Docker feature; it does not
automatically download a model or run submitted code. No port is
pre-forwarded; other ports are set to ignore auto-forwarding. If a port is
manually forwarded, **keep visibility Private** and do not forward
Docker's socket or Ollama port 11434.

## Step B — Metadata-only preflight (no candidate execution)

From the repository root in the Codespace's terminal:

```sh
python --version
python -m toad_core doctor
docker version
docker info --format '{{json .SecurityOptions}}'
docker info --format '{{.CgroupVersion}}'
```

A successful Docker CLI command is not sufficient to demonstrate secure
container operation. Docker-in-Docker may fail the cgroup and security
requirements; **that is an expected possible blocking outcome**.

Review Docker service status and the actual image before continuing.
Docker may be unavailable in a Codespace despite this configuration.
Do not bypass `DockerWorker._probe` to make a failing host look ready.

## Step C — Build only the trusted Toad laboratory image

Only after the preflight and within the approved operator console:

```sh
docker build -t toad-sage-lab:1 lab
python -m toad_core lab status
```

Building this trusted Dockerfile may fetch the official Python base image.
The worker prohibits pulling dependencies on behalf of a candidate.
Do not run `docker system prune` or delete unrelated images/containers.

## Step D — Actual containment test (opt-in, *not* CI)

After inspecting [lab_smoke.py](../tools/lab_smoke.py):

```sh
python tools/lab_smoke.py --run
```

Nine probes must all return `restriction_observed=true` and the final
`live_verified=true`: harmless execution, host-file isolation, root
read-only, blocked networking, timeout, output limit, memory, writable
disk and process count. Also confirm cleanup and immutable image IDs.
If any probe fails, stop. Do not run the autonomous agent or install
abilities on that lab.

Keep full reports in a *private* location; redact paths, tokens and
personal data before posting results to GitHub. No live tests have been
run by this PR.

## Step E — Optional local coding model, only after lab passes

Toad Sage requires an actual Ollama endpoint on loopback
`127.0.0.1:11434`. No model or tool installer is executed by default.

1. Inspect the [official Ollama Linux installation instructions](https://docs.ollama.com/linux).
   Download and inspect scripts/packages before running them; choose
   a method compatible with the Codespace OS. An `ollama serve` process
   should listen **only on loopback** and never be forwarded publicly.
2. Choose the existing default test model
   [`qwen2.5-coder:1.5b`](https://ollama.com/library/qwen2.5-coder:1.5b).
   Its download is about 986 MB, with additional runtime memory required.
   Its ability to follow strict JSON tool calls within a 30-second
   Toad deadline has **not** been established.
3. After you approve the download, in an interactive trusted terminal:

```sh
ollama pull qwen2.5-coder:1.5b
ollama list
python -m toad_core doctor --probe
```

If Ollama is not running, use its supported service or `ollama serve`
in a separate trusted Codespaces terminal. Do not change
`TOAD_OLLAMA_URL` to a remote host or use a `:cloud` model: the local
adapter intentionally refuses non-loopback URLs.

## Step F — Real broken-code repair acceptance

Only if Steps B–E pass *on the same host*:

```sh
python tools/broken_calculator_demo.py
python tools/broken_calculator_demo.py --run
```

The real runner reruns the containment probes **first**, then asks the
configured live model to propose a bounded repair and checks the original
tests plus independent holdout suite. Expected successful status:
`ready_for_owner_review`, never `installed` or `deployed`.

A failed inference, model timeout, weak patch, missing cleanup, Docker
denial or unsafe host is **blocked**, not success. Capture the exact
source/diff, digests, receipts and the reviewer decision. No automatic
merge/activation occurs.

## Stop and recovery

Stop or delete the Codespace when you finish to conserve compute and
storage. Keep private backups outside the Codespace if the data matters.
This is a *disposable* environment; it is unsuitable for a scheduled
always-on autonomous agent. A dedicated VM could be evaluated later
if persistent jobs become a real requirement.

**Step 1 still needs independent owner action:**
[Issue #9 — enforce GitHub `main` branch ruleset](https://github.com/jimedusot-beep/Toadsagemode/issues/9).
This Codespaces PR does not bypass or complete that issue.

References:
- [GitHub Codespaces creation](https://docs.github.com/en/codespaces/developing-in-a-codespace/creating-a-codespace-for-a-repository)
- [GitHub Codespaces included usage](https://docs.github.com/en/codespaces/troubleshooting/troubleshooting-included-usage)
- [GitHub Codespaces security and forwarded ports](https://docs.github.com/en/codespaces/reference/security-in-github-codespaces)
- [Dev Containers Docker-in-Docker feature](https://github.com/devcontainers/features/tree/main/src/docker-in-docker)
- [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/)
