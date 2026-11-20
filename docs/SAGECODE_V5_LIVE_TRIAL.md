# SageCode V5 — opt-in live local repair trial

**Status: proposed in a draft PR, not merged or deployed.** This is an **owner-invoked, trusted Python CLI**, not a website, not an AI action, and not proof that a real run has already succeeded. Its only purpose is to make a falsifiable, source-revision-bound end-to-end trial of the V1 → V4 SageCode stack possible on an approved local Docker/Ollama host.

## What this adds and why

The older `tools/broken_calculator_demo.py` exercises the earlier candidate agent, not the V1–V4 source-revisioned workflow. The V5 trial wires:

1. Existing metadata-only [readiness](../toad_core/readiness.py), requiring **both** an available restricted local Docker backend and the configured **loopback-only** Ollama model. Metadata readiness does **not** establish containment or model quality.
2. Existing, opt-in [lab containment smoke](../tools/lab_smoke.py), requiring every named probe (host-file isolation, read-only root, disabled networking, timeout, output, memory, disk, process bounds and harmless hello) to pass **before** any project source is staged.
3. A new, private project with one **intentionally incorrect addition** implementation. The user's real files and other projects are never read or modified by the trial.
4. V3's separately frozen `unittest` checks **created before model changes**. Four test methods cover positive, negative, zero and fractional addition. Frozen test source is not in the editable project.
5. V4's bounded controller: **at most two repair proposals, three independent Docker test attempts, six model actions per repair**, single-use session IDs and an existing cooperative 180-second wall budget. The model can only read, search, inspect and propose source revisions. The tests run only through V3's trusted Docker worker.
6. Local, owner-private JSON evidence, with the exact source revision, test plan digest and bounded repair report. **Any passing result still requires human review** and never installs or deploys code.

The tool never installs packages, downloads models/images, changes secrets, opens a public server, calls a paid model API, pushes to GitHub, or invokes robot hardware. The `--run` flag is an explicit opt-in, not permission for a model to choose an execution mode. The Docker daemon/host/worker/image and trusted controller remain critical trust dependencies.

## How to use on an approved host

The owner uses the iPad as a **remote client** to an approved host. The iPad itself is not assumed to run local Linux Docker or a coding model.

Requirements: Python >=3.11, Toadsagemode checkout containing this reviewed change and its V1–V4 dependencies, local Linux Docker satisfying [LAB.md](LAB.md), a trusted provisioned `toad-sage-lab:1` image, and Ollama with a locally installed model. The project defaults to `qwen2.5-coder:1.5b`, whose coding quality is **not** proven. A larger locally installed model may perform better but must fit the owner's host. Ollama URL validation restricts the endpoint to a credential-free loopback origin. Do not point it at an arbitrary remote/paid server.

```bash
# Safe default: only local catalog status; no test execution or AI inference.
python tools/sagecode_live_trial.py

# Bounded readiness metadata only: check Docker policy and Ollama model listing;
# no source executed and no model inference performed.
python tools/sagecode_live_trial.py --check

# After separately reviewing docs/LAB.md, explicitly opt in to the safe fixture.
# The script itself runs the full containment smoke first, then refuses on any failure.
python tools/sagecode_live_trial.py --run
```

Optional: `--workspace /path/to/private/folder` uses a dedicated owner-controlled workspace. Do not choose a shared/public directory or a checkout. It saves `sagecode-live-reports/containment-<id>.json` and `trial-<id>.json` with owner-only file permissions, together with the private source revisions, V3 evidence and V4 session records in that workspace. Reports are **not uploaded** anywhere. IDs are unique and files are never overwritten. An interruption requires manual inspection; the script does not silently resume an uncertain repair.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Default/check completed without running code, **or** opt-in trial produced `tests_passed_review_required`; inspect JSON `status` to distinguish |
| `2` | Blocked: missing prerequisites, failed containment, malformed workspace/evidence or another safe failure |
| `3` | Live trial ran but the bounded repair did not reach a passing review-only result |

Important: `--check` cannot certify actual containment. A run output saying `tests_passed_review_required` means *the configured trusted local path reported passing frozen tests*. It does **not** mean general correctness, hardened isolation certification, owner approval, Safari tests, remote autonomy or OpenCode parity. Compare the private Docker receipt's `image_id`, executed/cleanup flags, `plan_digest`, source revision and associated containment record before accepting the evidence.

## Agent B / Studio handoff

Render **inert** source text and the private report's sanitized statuses. A frontend fixture must keep its simulated status labeling; it must not invent an HTTP endpoint or expose `run()` directly to a browser. Never turn a test pass into an approval badge. Show `status`, repair count, `owner_review_required` and links to private local evidence only after authentication and review boundaries are independently implemented. Do not publish private absolute workspace paths in public UI, issues or logs.

## Test and threat constraints

- `tests/test_sagecode_live_trial.py` uses **monkeypatches** for readiness, containment and the coordinator. This verifies failure handling and wiring without calling Docker or a model. It **cannot establish live proof**. CI must keep browser/merge-gate tests; no skip or relaxation is necessary.
- We intentionally freeze simple calculator tests rather than letting the model choose its own success criteria. Some incorrect implementations may pass limited tests; passing here establishes only behavior covered by the frozen checks.
- The model receives a task description and may inspect source. Its repair intelligence has **not** been demonstrated with Ollama; treat unsuccessful or partial sessions as measurements, not as failures of the safety architecture.
- Container isolation is a reduced-risk environment, not a perfect boundary: the host kernel is shared. For untrusted real-world submissions use a dedicated machine or disposable VM and review Docker hardening.
- Docker cgroup/seccomp capability checks, no mounts/sockets, resource limits and cleanup are implemented in the existing `DockerWorker`; this CLI never reimplements or bypasses them.
- This trial is for **Python**, not arbitrary user-generated JavaScript or iPad Safari. Separate experimental WebKit test workers in unmerged PRs need independent review.
- No host was accessed and **no real Docker container or local model request was executed by the authoring/CI tests**. The explicit owner-run command is still required.

## Engineering reasoning and sources

- Repository: [`toad_core/project_tools.py`](../toad_core/project_tools.py) (V1), [`toad_core/controlled_agent.py`](../toad_core/controlled_agent.py) (V2), [`toad_core/project_testing.py`](../toad_core/project_testing.py) (V3), [`toad_core/project_repair.py`](../toad_core/project_repair.py) (V4), [`tools/lab_smoke.py`](../tools/lab_smoke.py), [`toad_core/models.py`](../toad_core/models.py).
- H.E.R.B.I.E. Master Knowledge Bank (research reference edition, October 12, 2026): **p. 4** Margaret Hamilton's state machine, fail-safe handling and deadlines; **pp. 7–8** Rodney Brooks's independent safeguards and local boundary reasoning; **p. 9** Grace Hopper's abstraction, reproducible debugging and testing. These motivate our system design; the design and results remain ours to verify experimentally.
- Docker's [security overview](https://docs.docker.com/engine/security/) and [rootless mode](https://docs.docker.com/engine/security/rootless/): Docker is a concrete test boundary, not perfect adversarial isolation.
- Ollama's [API documentation](https://docs.ollama.com/api): local model listing and request interface; the repository's adapter only permits loopback endpoints.
- [OpenCode tools](https://opencode.ai/docs/tools/) and [permissions](https://opencode.ai/docs/permissions/): capability comparison, **not** a required runtime or code dependency.
