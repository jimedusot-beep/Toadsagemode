# SageCode V3 — exact-revision restricted test gate (draft)

**Status:** trusted, private Python component; not an iPad API, not a model action, and not proof that any generated app has run. This draft must be reviewed before merging its parent pull requests.

## Purpose

V1 stores bounded project source revisions. V2 lets the existing `ControlledAgent` inspect and propose those revisions. V3 adds a **separate owner-side operation** that asks the existing restricted `DockerWorker` to test the exact source revision under a frozen test plan. This does **not** expose Docker or a shell to the language model.

## Owner-side Python integration (not a web endpoint)

```python
from toad_core.sagecode_revision_tests import SageRevisionTestGate

# A trusted controller created/opened the authorized `SageProjectTools` project.
# Its original manifest must include independently authored structured tests.
revision = project.status()["revision"]
gate = SageRevisionTestGate(project)  # default: existing restricted DockerWorker
report = gate.run(expected_revision=revision)
previous_report = gate.read_receipt(report["receipt_id"])
```

Do **not** expose this method as a `ControlledAgent` action, derive the `project` instance from browser/model-supplied paths, accept arbitrary shell commands, or pass an untrusted `worker` object. Test execution requires the existing local Docker worker and its fail-closed capability, resource, network, image and cleanup checks. When Docker is absent, `outcome` is `blocked`, **not** passed.

## Frozen acceptance boundary

The gate requires a nonempty test plan in the **original trusted baseline**. For a changed revision, it calls existing `validate_repair` logic to reject changes to test specs, test files and folders, permissions, dependencies, entrypoint, or the declared file set. This is defense in depth: a model can propose a change to a test file in V1, but it **cannot have that modified revision tested as valid** through this gate. Validation occurs **before** the worker is invoked.

The gate binds each record to:
- The preauthorized `project_id` and original `baseline_revision`.
- The exact immutable SageCode source revision (`revision`, a SHA-256 address of the stored revision record).
- The `package_digest` of the tested manifest.
- The SHA-256 digest of the original structured test plan.
- The worker mode, restricted Docker image ID (when available), per-test category/executed/passed/cleanup summary, and source-staleness state.

A test worker runs only on a **copy** of the validated manifest; no project source or approved checkout is installed or modified. After the worker returns, the gate refuses to issue a receipt if the project's current source revision changed during the run. The underlying source store is still explicitly single-writer, not an interprocess transaction; do not run parallel edits/tests against the same project without a separate lock.

## Receipt states and verification wording

The result is an immutable JSON record stored privately under `sagecode-v1/<project_id>/test-evidence/`, with owner-only directory/file permissions and an integrity digest. `read_receipt` revalidates that digest, the project revision, and the original test-plan digest. Historical receipts remain viewable but have `stale:true` when HEAD has moved. SHA-256 detects normal tampering; **it does not authenticate a malicious process with the same filesystem privileges**.

All receipts **always** say `verification:"unverified"`, `approved:false`, `owner_review_required:true`, `release_allowed:false` because a passing test does not confer release approval.

| `outcome` | Interpretation |
| --- | --- |
| `tests_passed` | The actual `DockerWorker` reported complete executed, passing, cleanup-confirmed tests matching the exact revision and frozen plan; **owner review still required**. |
| `tests_failed` | Some worker-executed test did not pass; inspect errors through the existing trusted worker, not through a model command parser. |
| `blocked` | The actual worker could not execute, e.g. local Docker unavailable or required isolation not confirmed. |
| `blocked_invalid_worker_evidence` | The worker returned a mismatched digest, test path/index, or invalid receipt data; it is not accepted. |
| `rehearsal_passed` | An injected test double reported success. **Not real code execution, not real test verification.** |

Do not display a green “validated app” state for `rehearsal_passed` or `blocked`. Test stdout/stderr and potentially sensitive host strings are **not stored** in the durable receipt; only bounded test summaries are retained.

## What V3 does not provide

- No code generation, autonomous repair, compiler, npm installation, browser preview, external paid API, remote executor, approval gateway or deployment.
- No independent holdout tests yet; the test plan is frozen by the trusted baseline but may still be incomplete. Add a separately authored holdout plan as its own reviewed milestone.
- No cross-process lock or signed attestation. A compromised same-user host can manipulate local data and the trusted worker; Docker is defense in depth and not a perfect sandbox.
- No evidence of Docker execution from Python CI, which uses test doubles and an explicit no-Docker failure case.
- The worker currently supports the existing bounded Python/unittest test-spec schema, not arbitrary web-app build commands. Do not claim JavaScript or iPad apps are automatically built or tested by this gate.

## Required tests and review

- Exact revision and stale request; frozen test files/specs, changed code allowed.
- Mismatched or fabricated result, incomplete tests, missing Docker, cleanup failure, storage tampering, HEAD changes during testing.
- Full Python 3.11/3.12 regression, Mobile WebKit, and the existing fail-closed merge-gate on the exact PR head. Browser job cancellation is **not** passing.
- Agent B may display historical receipts via **labeled fixtures** pending an authenticated owner-side adapter. **Do not invent a production HTTP endpoint or expose this test gate directly in the browser.**

## Engineering reasoning and references

- Existing Toad Sage [`DockerWorker`](../toad_core/lab.py), [`validate_repair`](../toad_core/repair.py), [`SageProjectTools`](../toad_core/project_tools.py), V1/V2 contracts, and accompanying tests.
- H.E.R.B.I.E. Master Knowledge Bank (research edition, 12 October 2026): Margaret Hamilton (PDF pp. 4–5, explicit safe failure states), Rodney Brooks (p. 7, independent lower-level safeguards), Grace Hopper (pp. 9–10, module interfaces and repeatable tests). These are analogical principles, not claims those contributors built this system.
- Docker security and resource boundaries: <https://docs.docker.com/engine/security/> and <https://docs.docker.com/engine/containers/resource_constraints/>.
- OpenCode tool/permission behavior as a **comparison** rather than reused code: <https://opencode.ai/docs/tools/> and <https://opencode.ai/docs/permissions/>.
