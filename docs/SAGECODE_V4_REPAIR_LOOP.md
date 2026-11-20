# SageCode V4 — Controlled diagnosis and repair

**Status:** experimental, trusted Python backend only. Proposed as a **draft PR stacked on V3 PR #52 → V2 PR #49 → V1 PR #46**. Not merged, not deployed, not an iPad-facing API and not proof of real autonomous repair on a live local AI/Docker host.

## Why this is the next milestone

V1 supplies private, source-only file/revision tools. V2 exposes five strictly bounded source tools to the existing `ControlledAgent`. V3 freezes independent Python acceptance tests and binds test records to an exact source revision. **V4 joins those pieces into a conditional repair loop without placing a test/approval capability in the model's action list.**

The owner/controller must explicitly call `SageRepairCoordinator.run(...)`. The project-bound model remains permitted only to `project_status`, `project_tree`, `project_read`, `project_search`, `project_propose_edit`, and `finish`. An AI response cannot invoke the independent test worker, edit frozen checks, restore history, approve, publish, or request a host shell.

## Implementation and state transitions

`toad_core/project_repair.py` exports `SageRepairCoordinator(engine, candidate_id, test_gate, *, model=None, max_repairs=2)`. The constructor verifies exact `Engine` and `SageProjectTestGate` types, uses the existing `SageProjectActionAdapter` to verify the authorized candidate/project/immutable baseline, and revalidates the frozen test plan.

The trusted controller supplies a **non-reused session ID** and a short, bounded goal:

1. **Claim a private one-use session** under `workspace/sagecode-v4/<project_id>/`. Exclusive creation prevents the same ID from silently replaying after an interrupted or completed run. The 40-session cap is deliberate. An incomplete claim requires manual investigation; it is not automatically deleted or retried.
2. **Run independently frozen tests** through V3 `SageProjectTestGate.run_current()`. This delegates executable source only to the existing restricted local Linux `DockerWorker`. If Docker is unavailable, a receipt is stale, cleanup failed, or results come from a test double, the coordinator **stops before querying the model**.
3. If tests **already pass**, return `already_passing_review_required` without a model call. If an actual executed Docker run fails with a `test_failure` category (and no resource/time/cleanup failures), create a fresh, trusted project-bound `ControlledAgent` trajectory.
4. Give the model the user goal, project revision, test-plan digest, and **sanitized failure categories**, but never the independently frozen test source, raw container stderr, host filesystem paths, or credentials.
5. Allow at most **six bounded model actions** in each attempt and **one source edit** before retesting. The model can request only the source actions already permitted by V2. The trusted controller records a `finish` observation marking review required; it does not approve the change.
6. Run **the same** frozen acceptance plan against the new source revision, verify the exact returned V3 evidence record and source identity, then stop on passed, stale, blocked, cancelled or unrepairable. At most **two repairs**, 180 seconds overall (cooperatively checked between operations), and three independent test runs (initial + two retests). No automatic test changes, git commits, merges, publication or rollback.

### Report shape (illustrative; not a verified receipt)

```json
{
  "schema": "sagecode-repair-report-v1",
  "project_id": "example-project",
  "candidate_id": "<trusted candidate ID>",
  "plan_digest": "<frozen plan SHA-256>",
  "initial_revision": "<original draft revision SHA-256>",
  "final_revision": "<current draft revision SHA-256>",
  "status": "test_unavailable_or_unrepairable",
  "attempts": [],
  "initial_test": null,
  "final_test": null,
  "verification": "unverified",
  "approved": false,
  "release_allowed": false,
  "owner_review_required": true
}
```

Possible statuses: `already_passing_review_required`, `tests_passed_review_required`, `repair_budget_exhausted`, `test_unavailable_or_unrepairable`, `stale_test_evidence`, `no_repair_proposed`, `agent_blocked`, `cancelled`, `cancelled_or_budget_exhausted`, `inconsistent_revision_blocked`.

**A passing test never means approved or generally correct.** Unit tests that patch `DockerWorker.run` with a simulated successful response verify orchestration logic only; they are **not evidence** that Docker ran or a local model fixed the problem. Even real passed tests require owner review and a separately approved release policy.

## Trusted local integration (example, not a browser API)

```python
from toad_core.engine import Engine
from toad_core.project_tools import SageProjectTools
from toad_core.project_testing import SageProjectTestGate
from toad_core.project_repair import SageRepairCoordinator

engine = Engine("/private/workspace")
try:
    candidate = engine.ingest_package(trusted_source_package)
    manifest = engine.get(candidate["id"])["manifest"]
    project = SageProjectTools.create(
        engine.store.workspace, "my-project", manifest,
        allowed_project_ids={"my-project"},  # trusted controller, never model/browser
    )
    gate = SageProjectTestGate.create(project, trusted_frozen_plan)
    # Requires the trusted host's pre-provisioned Docker lab. The default model
    # remains the existing local Ollama adapter, with no paid fallback.
    coordinator = SageRepairCoordinator(engine, candidate["id"], gate, max_repairs=2)
    report = coordinator.run("Fix the addition bug", session_id="example-run-01")
    assert report["approved"] is False
finally:
    engine.close()
```

## Threat model and important limitations

- Only one trusted writer/controller should mutate a project at a time. A session claim prevents duplicate IDs but is **not** a distributed transaction protecting against unrelated concurrent writes. Source revision checks and V3 stale receipts fail closed, and an owner must review interrupted runs.
- The 180-second budget is **cooperative**, checked between calls; it cannot forcibly cancel a blocked local model request or Docker call. The underlying `ControlledAgent` and `DockerWorker` apply their own limits. Trusted controller cancellation is checked between actions and before tests.
- V3's test receipt records only sanitized categories, **not raw stderr or detailed assertion traces**. V4 diagnoses only as far as these categories and the owner goal allow. Stronger debugging will require a separately reviewed, bounded diagnostics protocol. Do not claim OpenCode-level debugging quality based on these unit tests.
- Fake, patched worker results in unit tests can resemble Docker responses. They are **never real execution evidence**. V4 does not introduce a public verification endpoint, signatures, or same-user host compromise protection.
- Source revision digests are not GitHub commit hashes. They refer only to private JSON snapshots. Edits remain drafts; they do **not** modify installed software or the live source checkout.
- No full-featured JavaScript/browser app runner here. Existing isolated web-worker experiments are in separate, unmerged PR #28/#29; this change exercises the V3 Python tests only.
- Trajectory and session source should not be sent to external provider APIs by the controller; local Ollama only unless separately reviewed by owner.
- Maximum attempts (2), model actions per attempt (6), and accepted failure categories (`test_failure`) are deliberate. Resource, timeout, cleanup and worker errors **cannot** be interpreted as an ordinary code defect.

## Independent acceptance and handoff

1. Run `python -m unittest discover -s tests -p 'test_project_repair.py' -v` (unit tests patch worker results; no generated source execution).
2. Require full GitHub CI Python 3.11 and 3.12, Mobile WebKit, and unchanged fail-closed merge gate on the exact head. Existing CI has a known Playwright Ubuntu package-install timeout; draft PR #43 fixes the setup separately and must not be merged implicitly.
3. On a trusted owner-controlled Linux Docker host, run the real lab containment smoke checks, then the same frozen failing/passing fixtures **without monkeypatching** and record actual image ID and cleanup receipts. Run with a genuine locally available model, measure model actions/latency, and distinguish model-failure from worker-failure rates.
4. Agent B may display the **report JSON shape as a clearly labeled fixture**. It must not expose `run()` as an unauthenticated browser endpoint, render source-generated JavaScript in the trusted Studio, or turn `tests_passed_review_required` into an approval badge.
5. Independent Agent B review and owner decision required before merge/deploy.

## Sources and reasoning

- Repository code: `toad_core/controlled_agent.py`, `toad_core/sagecode_actions.py` (V2), `toad_core/project_tools.py` (V1), `toad_core/project_testing.py` (V3), `toad_core/lab.py` and `docs/LAB.md`.
- H.E.R.B.I.E. Master Knowledge Bank (research reference edition, 12 October 2026): p. 4 Margaret Hamilton (explicit safe/fault states); pp. 7–8 Rodney Brooks (separate independent safeguards); p. 9 Grace Hopper (abstraction and reproducible debugging). These are design analogies rather than claims about SageCode's historical ancestry.
- OpenCode, comparative tool and permissions model: https://opencode.ai/docs/tools/ and https://opencode.ai/docs/permissions/ .
- Docker security and rootless guidance: https://docs.docker.com/engine/security/ and https://docs.docker.com/engine/security/rootless/ .
