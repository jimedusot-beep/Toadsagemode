# Restricted testing laboratory

The lab has **no host execution fallback**. `python -m toad_core test ID` runs only structured Python tests in a separately provisioned local Linux Docker environment. JavaScript/HTML/CSS can be stored and inspected but cannot yet execute in this worker. There is no public execution endpoint.

## Threat model and trust

Trusted: the user, the installed Toad core, its SQLite database, Docker daemon/CLI, the lab Dockerfile/runner, the local lab image and kernel. Untrusted: all feeds, archives, candidate source, dependencies, model output, imported test claims and candidate output. Imported code cannot edit the core or security policy: the core, catalog and host directories are never mounted. Model instructions cannot alter the Docker arguments. The orchestrator needs permission to control the local Docker daemon; candidates never receive its socket.

Containers share the host kernel and are not perfectly secure. Use a dedicated machine or disposable VM for adversarial packages, keep Docker/kernel updated, and prefer a rootless Docker daemon with working cgroup v2 delegation. A host administrator or someone who can alter the trusted database/image is outside this boundary. A preexisting hostile same-user host process is also outside this model. This worker is a controlled starting point, not a production malware-analysis service.

## Enforced defaults

| Control | Default |
| --- | --- |
| Host | Local Linux Docker; cgroup v2 and default seccomp support required |
| Image | Locally built `toad-sage-lab:1`, resolved to an immutable image ID; `--pull=never` |
| Identity | UID/GID 65532; all Linux capabilities dropped; no-new-privileges |
| Network / IPC | `none` / `none`; no published ports |
| Filesystem | Read-only image; no bind mounts, credentials, Docker sockets, devices or personal files |
| Writable disk | `/work` tmpfs 32 MiB; `/tmp` tmpfs 8 MiB; noexec/nosuid/nodev |
| Memory / swap | 128 MiB memory; total memory+swap 128 MiB |
| CPU / processes | 0.5 CPU; 32 PIDs; bounded open descriptors and file sizes |
| Time | 10 seconds per test; at most 10 declared tests |
| Output | 64,000 bytes combined stdout/stderr; Docker logging disabled |
| Cleanup | Forced container removal in `finally`; failure prevents verification |

The worker checks Docker capability reporting, then independently inspects the created container before sending any source. Missing or mismatched controls block execution. The image can read its own system files and Python standard library; only writes outside `/work` and `/tmp` are denied. It cannot read the host's corresponding paths. `noexec` blocks native executables on tmpfs, while Python intentionally interprets candidate source there.

No dependencies are downloaded or installed. The initial lab refuses declared third-party dependencies, unresolved nonstdlib imports, permission grants, invalid syntax and missing structured tests. String shell commands in v1 packages remain metadata and never execute. A future dependency image must be provisioned by trusted setup, separately from candidates.

## Local setup

Install Docker according to its official documentation for your OS. Check the requirements on your actual computer; the Acer's hardware is not assumed. On Windows use Docker's Linux/WSL2 backend and run these commands from the checkout in the supported environment. Rootless Linux installations may set a trusted local `DOCKER_HOST=unix:///.../docker.sock`; TCP/SSH Docker endpoints are refused.

```sh
# Trusted project context only. This build may download its public base image.
docker build -t toad-sage-lab:1 lab
python -m toad_core lab status
# Run these known containment probes on your own provisioned lab, not in CI:
python tools/lab_smoke.py --run
```

The smoke check tests a harmless program, absence of a host canary, read-only root, disabled external networking, time/output/memory/disk/PID restrictions and cleanup. CPU/memory enforcement settings are inspected, not inferred from performance benchmarks. A nonzero check means **do not rely on that host's containment**. This development environment has no Docker executable, so no successful live run is claimed.

Normal cleanup cannot survive power loss or an abrupt host kill. After a crash inspect only Toad-labelled containers with `docker ps -a --filter label=org.toad-sage.lab=1`; remove a stale named container with `docker rm -f toad-lab-...` after checking no active mission owns it. No pruning of unrelated containers is performed.

## Verification and installation

A receipt records actual container execution, exact test specifications, bounded output, exit results, immutable image ID, resource policy, cleanup and the source digest. A Python stdout test must match its expected output exactly. A unittest test must discover at least one test and exit successfully. Tests supplied with malicious code can lie about their assertions; passing proves only that the configured tests passed in this lab, **not that code is safe or that tests adequately specify its purpose**. Review meaningful tests for real applications.

Only local receipts can enable `verified`. Backup receipts are untrusted data and never recreate authority. Activation uses `library install ID`: files go into versioned directories below the private workspace's `abilities/`, with an empty capability grant. `installed` means **available for reuse in a sandbox only**, not imported into the host interpreter. Previous versions remain available; `library rollback NAME` rechecks local evidence and installed contents. Changed files, expanded grants or missing receipts refuse activation.

References: [Docker resource constraints](https://docs.docker.com/engine/containers/resource_constraints/), [run options](https://docs.docker.com/reference/cli/docker/container/run/), [Docker security](https://docs.docker.com/engine/security/), [rootless mode](https://docs.docker.com/engine/security/rootless/), [default seccomp](https://docs.docker.com/engine/security/seccomp/).
