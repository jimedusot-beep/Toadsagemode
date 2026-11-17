# Toad Sage browser-app builder: first accepted app

Status: proposed design; browser-app approach and task-tracker demonstration selected by the user. Implementation awaits approval of this contract.

## Intent and outcome

Extend the existing Toadsagemode engine so a trusted operator can request one small browser app, have a real configured model generate its files, run independent acceptance checks in a restricted worker, attempt bounded repairs, and receive source plus evidence for human review.

First supported target: a task tracker. This is a bounded first app-building capability, not a general autonomous developer, mobile native app builder or proof that arbitrary requests work.

The operator works from an iPad. Development and execution must be possible on an authorized remote development host; an Acer or ZBook is not required. The current workspace has Python/Node but no Docker/Ollama. Building/testing trusted engine code here is distinct from proving a real model-plus-worker run.

## Existing foundations to preserve

Pinned starting revision: 0f4ee5e4210dd57735d37f15b17c73e324ab4c7e in jimedusot-beep/Toadsagemode.

Reuse MissionEngine's SQLite persistence, leases, budgets, checkpoints, source-only repairs and packaging wherever appropriate. Preserve existing Python missions and package/import semantics. ControlledAgent already adapts mini-SWE-agent with its MIT notice; do not install or replace it with MinimalAgent.

Keep the public Pages inbox nonexecuting. Keep the private bridge limited to intake and status. No network mission-execution route is part of this change.

## Approaches considered

1. Existing Python mission demonstration: least engine change, but does not produce a browser app convenient for iPad use.
2. Extend bounded missions for static HTML/CSS/JavaScript: selected approach; reuses the engine while adding a browser test worker.
3. Full-stack app generator with packages, deployment and database provisioning: deferred; adds credentials, installation hooks, costs and a much larger execution surface.

Builder choices proposed here: dependency-free static output, a fixed task-tracker acceptance profile, a separately provisioned browser image, and the existing configured Ollama adapter. No new paid provider, hosting subscription or public service.

## First app behavior

The generated app uses local HTML/CSS/JavaScript. No CDNs, fonts, package installation, external APIs, service workers or backend.

- A labelled task input and Add button accept a nonblank task.
- Whitespace-only input shows a helpful validation message without adding a task.
- Each task has a labelled completion checkbox and Delete button.
- Marking one task complete changes only that task.
- Deleting one task removes only that task.
- Task text is displayed as text, including angle brackets and script-like strings.
- Active/completed state survives a reload on the same origin in the same browser profile.
- Unavailable or corrupt browser storage shows an honest message; input remains usable in a clearly temporary mode.
- No personal or health data is needed; acceptance uses synthetic tasks.
- Touch controls and layout work at 390 x 844 and 820 x 1180 viewport sizes without horizontal overflow.

Persisting on one browser/origin does not imply cross-device synchronization, a backup, or durable storage under private browsing. Actual Safari/iPad acceptance remains separate from desktop viewport checks.

Use accessible roles/names as the acceptance interface: textbox "New task", button "Add task", each task represented as a listitem containing its text, completion checkbox and "Delete task" button. Report validation/storage errors through an accessible status or alert. Visual style remains the model's choice within these constraints.

## Engine extension

A trusted mission option selects a registered target, initially python (existing default) or task-tracker-web-v1. A normal user goal is data and cannot introduce targets, workers, shell commands or policy.

The registered web target supplies its output contract, prompt requirements, frozen acceptance profile, worker class and bounded policy. Preserve legacy missions without a target as Python missions. Unknown targets block before generation. Python runners must refuse web target records instead of interpreting them under Python rules.

Retain bounded toad-ability-v2 manifests for generated source. Add one narrow structured test kind for a registered trusted browser profile; it has an exact allowed profile ID and the listed HTML entrypoint, never a command or candidate test-file path. Existing unknown test kinds continue to fail. Normalize and digest execution-relevant profile metadata, then freeze it and all paths during repair. Imported profile labels do not constitute permission to execute or verification.

Require exactly the target's registered acceptance spec for a web mission. The model generates application source, not acceptance code. It cannot omit checks, substitute a permissive profile, provide a receipt, or weaken test expectations. Keep inspection's distinction between observations and verified behavior; static scanning does not certify JavaScript safety.

Generate -> validate -> inspect -> restricted browser test -> optional source-only repair -> package for review. Failed model or test operations preserve candidates and checkpoint history. No successful test receipt means no completed verified build.

## Restricted browser worker

Add a separate trusted browser-worker image and runner; do not increase privileges or browser dependencies in the existing Python image. Image setup is explicit trusted operator work. It can download pinned browser/runtime dependencies during image provisioning, never during a mission.

Use a locally provisioned Docker daemon on the authorized execution host and resolve the browser image to an immutable ID. No automatic image pull, network, published port, host bind mount, credential, device or Docker socket inside the worker.

Run nonroot, read-only root, dropped capabilities, no-new-privileges, enforced seccomp/cgroup limits, bounded writable tmpfs, combined output limit, cancellation and forced cleanup. Retain Chromium's own sandbox; Playwright launch must explicitly enable it. Playwright documents a reviewed seccomp profile permitting the user namespaces Chromium needs. Pin that trusted browser-specific profile, bind its digest into setup/receipts, and keep the existing Python worker's default profile unchanged. If the browser cannot run under the actual container policy, block and resolve trusted setup rather than silently adding --no-sandbox or privileged flags.

Proposed upper bounds for this browser profile: 512 MiB memory+swap, 1 CPU, 128 PIDs, 128 MiB writable app/browser space plus bounded shared-memory tmpfs, 45 seconds per test run, 64 KiB returned output. Inspect actual created-container policy before transferring candidate bytes. Adjusting these defaults requires a trusted source change and containment retest, never a model proposal.

Transfer only validated bounded source over stdin. Inside the container, a trusted server serves only manifest-listed assets on container loopback. No traversal, directory listings or host files. The trusted browser harness is outside candidate source and unreachable through that asset server. Use a fresh browser context and fixed container-loopback origin per run.

The browser harness blocks non-app requests, popups, downloads and service workers, in addition to container-level disabled external networking. Exercise user-visible behavior rather than trusting app JavaScript assertions or a model success string.

A browser process and containers still share a kernel trust boundary. Before unfamiliar generated apps run, the actual worker host must pass containment probes covering denied external connections/host canary reads, quotas, timeout, cancellation and cleanup. Do not claim containment based only on mocked Docker arguments.

## Independent acceptance and repairs

Trusted task-tracker-v1 checks cover:
1. Add two distinct synthetic tasks and reject blank input.
2. Complete one task without changing the other.
3. Delete one task without removing the other.
4. Reload and confirm retained text and completion state.
5. Render script-like task text literally without creating executable markup.
6. Corrupt and deny storage in separate fresh contexts; confirm useful error and temporary operation.
7. Verify labelled controls, keyboard operation and the two viewport layouts.
8. Reject external resource use and unintended navigation; record browser/page failures.
9. Cancel or time out a deliberately hanging fixture; ensure no receipt claims success and cleanup occurs.

Use deliberately broken fixtures to prove the harness can detect failures. Test doubles can verify engine orchestration; they are explicitly labelled and cannot satisfy live demonstration acceptance.

Repairs receive bounded failed-check observations. The model can change source contents only; filenames, entrypoint, target/profile, budgets, permissions and dependencies remain frozen. A repeated candidate or exhausted budget blocks. Do not let the repair alter trusted harness or reference fixtures.

Proposed mission defaults: at most 4 model calls, 3 browser runs, 2 repairs, 300 total seconds, existing bounded phase count. Reserve calls/time before operations and preserve budgets across resume.

## Outputs and approval

An actually successful restricted run produces a source ZIP, machine-readable report, and readable project guide. Reports bind target/profile/harness revision, immutable worker image, candidate digest, executed checks, outcomes, resource policy, cleanup, model-call evidence and known limits.

Package status is "built and tested; awaiting human review". It does not mean installed, merged, deployed or approved. Retain the existing separate activation policy. No automatic merge, deployment, spending, repository cross-write or hardware operation.

A draft artifact may be exported for inspection when blocked, but is explicitly unverified and cannot occupy the verified-build output/status.

For the iPad, do not embed generated active HTML into the privileged Toad inbox or serve it under the private bridge origin. Review source/ZIP first. Any later interactive iPad preview uses a separate isolated origin and an explicit protected deployment decision. Opening a local ZIP/HTML is not assumed to provide a reliable Safari preview workflow.

## Verification and honest completion

Engine tests: target registration, legacy compatibility, strict manifest validation, profile tampering, repair freezes, budgets, resume/cancel, packaging/digest binding and blocked dependencies.

Worker tests: real trusted browser harness against controlled good/broken fixtures, plus worker policy/lifecycle tests. Running trusted fixtures during development is not the same as running untrusted model output on the host.

Live milestone requires a real configured model request, genuine restricted Docker browser receipt for that generated source, preserved report/ZIP, and human review. If the host lacks model or worker, stop with exact missing prerequisites and make no autonomous-build claim.

Actual iPad usability is a separate acceptance item after a protected preview path exists. No runtime provisioning, model download or deployment is implicitly included in approving implementation.

## Remaining operator decisions

None needed to implement this bounded design. Before live acceptance, an authorized host with the required model/worker must be selected and provisioned. Any paid cloud/model access or preview publication remains a separate decision.

## References

- [Playwright browser container and sandbox guidance](https://playwright.dev/docs/docker)
- [Docker enforced resource constraints](https://docs.docker.com/engine/containers/resource_constraints/)
- [Existing mission engine](https://github.com/jimedusot-beep/Toadsagemode/blob/0f4ee5e4210dd57735d37f15b17c73e324ab4c7e/toad_core/mission_engine.py)
- [Manifest validation](https://github.com/jimedusot-beep/Toadsagemode/blob/0f4ee5e4210dd57735d37f15b17c73e324ab4c7e/toad_core/schema.py)
- [Current worker and trust boundary](https://github.com/jimedusot-beep/Toadsagemode/blob/0f4ee5e4210dd57735d37f15b17c73e324ab4c7e/docs/LAB.md)
- [Existing phone bridge constraints](https://github.com/jimedusot-beep/Toadsagemode/blob/0f4ee5e4210dd57735d37f15b17c73e324ab4c7e/docs/PRIVATE-BRIDGE.md)

