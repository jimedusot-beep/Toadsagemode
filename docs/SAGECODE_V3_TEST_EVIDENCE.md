# SageCode V3 — frozen acceptance plan and revision-bound test evidence

**Status:** experimental Python backend module, proposed in a draft PR stacked on SageCode V2. **Not merged, not deployed, not a browser API, not an autonomous repair engine, and not proof of a successful live Docker test.**

## Purpose and provenance

V1 stores immutable candidate-source revisions (`toad_core/project_tools.py`). V2 lets the existing `ControlledAgent` inspect and propose changes within a strictly bound project; project-bound agents cannot invoke test/execute/approval commands. V3 adds the **separately trusted testing side**. It uses the repository's already constrained `DockerWorker` and independently frozen test definitions; it does **not** create another shell or agent.

- [Existing restricted Python lab](../toad_core/lab.py): locally provisioned Linux Docker, no host execution fallback, resource constraints, network isolation, root filesystem read-only, no privileged mounts, and cleanup checks.
- [Existing lab threat model](LAB.md): containers share the host kernel, not a perfect sandbox. A trusted Docker daemon, image, controller, and host remain required.
- [SageCode V1](SAGECODE_V1_CONTRACT.md) and [V2](SAGECODE_V2_AGENT_BRIDGE.md): source revisions and source-only agent actions.
- H.E.R.B.I.E. Master Knowledge Bank: PDF page 4 (Margaret Hamilton, explicit fault handling), page 7 (Rodney Brooks, independent lower-level safeguards), page 9 (Grace Hopper, repeatable regression tests), page 10 (Don Norman, visible status and honest error feedback). These are analogies for current software design, not claims about their historical implementations.
- Docker guidance: https://docs.docker.com/engine/security/ and https://docs.docker.com/engine/security/rootless/ .

## Trust boundary and precise meaning of evidence

A **trusted Python controller**, never an AI response or untrusted browser request, constructs a `SageProjectTestGate` after choosing a separately authored test plan. The gate must be created **at the project's initial source revision before any model-proposed edits**. A plan is written once in a private workspace and permanently tied to `project_id` and `baseline_revision` with a SHA-256 content digest.

Only two test kinds are supported:

1. `python`: a named existing project `.py` file plus an independently supplied exact expected stdout value. The tested source can change; the expected result cannot.
2. `unittest`: an independent, frozen set of `tests/*.py` source files in a separate namespace. These files are included only in the test package submitted to the worker; they are **never** inserted into the model-editable project manifest.

No shell commands, arbitrary dependency installs, network requests, browser/WebKit execution, HTTP endpoints, approval buttons, executable downloads, source checkout modification, Git push, or physical H.E.R.B.I.E. control are added.

The test gateway produces a canonical **staged package** combining the exact current source revision, frozen checks, and optionally immutable independent test files. It refuses declared permissions and external dependencies. Existing project tests are **replaced** by the frozen test plan, so model-supplied tests cannot determine the acceptance bar. The staged package receives its own `package_digest` and is linked to the original source revision and frozen plan digest.

Only an exact `DockerWorker` object can produce a `status: "passed"` result. Test doubles, regardless of their claims, yield `test_double_unverified`. A trusted worker result must bind the exact package digest, a valid image ID, actual execution, successful cleanup and every expected test index/kind/path. Failure or unavailable Docker remains `failed` / `blocked`. If the source HEAD moves while testing, the recorded outcome becomes `stale_revision`. **No result can automatically set project verification or release approval.** The `verification` value is always `unverified`, and both `approved` and `release_allowed` are always false.

SHA-256 record digests detect accidental tampering and wrong-revision reuse, but **do not authenticate against a compromised trusted controller, a malicious same-user process, or malicious host/daemon**. CI unit tests may patch `DockerWorker` to check result parsing; that is simulated test evidence, not proof that a Docker container actually ran.

## Trusted Python integration (illustrative only)

```python
from toad_core.project_testing import SageProjectTestGate

# project = trusted SageProjectTools instance created at baseline revision
plan = {
    "tests": [{"kind": "python", "path": "src/main.py", "expected_stdout": "2\n"}],
    "files": [],
}
gate = SageProjectTestGate.create(project, plan)  # before model edits

# Only from an explicitly authorized owner/controller action after draft edits:
receipt = gate.run_current()  # requires real provisioned DockerWorker
assert receipt["verification"] == "unverified"
assert receipt["release_allowed"] is False
view = gate.evidence_for_current(receipt["receipt_id"])
```

Do not call `gate.run_current()` from an AI tool or public handler. Model actions remain exactly five source-only operations plus `finish`. Testing is an **operator-side operation** in this version.

Example **data shape**, not an actual execution receipt:

```json
{
  "schema": "sagecode-test-evidence-v1",
  "receipt_id": "<32 hex characters>",
  "project_id": "my-project",
  "revision": "<source revision digest>",
  "plan_digest": "<frozen acceptance digest>",
  "tested_package_digest": "<canonical staged package digest>",
  "status": "blocked",
  "executed": false,
  "passed": false,
  "cleanup_ok": true,
  "backend": "docker",
  "image_id": null,
  "test_count": 1,
  "cases": [],
  "verification": "unverified",
  "approved": false,
  "release_allowed": false,
  "evidence_digest": "<record integrity digest>"
}
```

The `evidence_for_current` view adds `is_current`, `current_revision`, and `display_status` based on a fresh check against the project's current source and frozen plan. An old receipt becomes `stale_revision` after source changes. A trusted UI must not infer approval from `passed` and must not claim physical iPad Safari or live model testing.

## Verification and next steps

`python -m unittest tests.test_project_testing -v` or discovery with `python -m unittest discover -s tests -p 'test_project_testing.py' -v` tests the orchestration boundaries **without running generated source**. CI's full Python matrix is the integration proof for this module. A real Docker smoke run on an explicitly approved host is needed before stating that code actually executed with the expected isolation controls.

V4 (not in this PR) should add authenticated owner-triggered execution, real-world smoke-check records, safe cancellation, and a diagnostic/repair loop that cannot rewrite independent acceptance criteria. A separate JavaScript/WebKit worker remains experimental in unmerged PRs; V3 does not use it.

## Limits

- One trusted writer, maximum 40 immutable receipts per project; creation of a plan requires baseline HEAD.
- At most 10 checks and 10 test-support files; at most 64 kB per test file and 128 kB combined.
- Only existing source files are writable through V2; V3 adds no filesystem editing.
- No runtime Docker evidence was collected in this test environment; absent Docker correctly blocks.
- A digest-only receipt is **not a signature** or anti-forgery protection against host compromise.
- A passing acceptance plan checks only what that plan asserts; it does not mean all application behavior was validated.
