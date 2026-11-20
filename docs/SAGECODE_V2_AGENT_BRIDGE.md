# SageCode V2 — bounded ControlledAgent project actions

**Status:** experimental, source-only, **not merged**, **not an HTTP API**, **not a sandbox**, **not an autonomous web-app execution or repair system**. This PR is stacked on the unmerged SageCode V1 PR #46. It changes backend code only, not Agent B's mobile Studio or browser files.

## What V2 adds

The existing `ControlledAgent` remains the only agent loop. A trusted Python controller can optionally inject a `SageProjectTools` instance through `project_tools=...` when starting a candidate-bound trajectory. The new `SageProjectActionAdapter` validates that the project is in the **same private workspace**, and its immutable **baseline manifest exactly matches** the declared candidate's manifest and digest. The binding (project ID, baseline revision, original candidate ID) is persisted with the trajectory and verified when reopening. Missing or different bindings fail closed.

Bound agents receive **exactly five additional source-only actions**: `project_status`, `project_tree`, `project_read`, `project_search`, and `project_propose_edit`. Each accepts only its own documented fields and uses the V1 limits. For edits, a matching `expected_revision` is mandatory; stale edits refuse to update the source pointer. Source-only observations explicitly say `executed:false`, `approved:false`, `verification:"unverified"`, and `release_allowed:false`.

Unbound agents **cannot** use project actions. The model cannot select a workspace, authorize another project, change policy, restore a revision, grant approvals, run a shell, install packages, contact a server, or execute code through these tools. `project_restore` deliberately remains an **operator-only** V1 Python operation. Project-bound `finish` always remains **unverified**, even if the original candidate has a Docker test receipt, because that receipt cannot establish correctness of a separately proposed project revision. The original candidate and installed abilities remain unchanged.

## Trusted local integration (not a browser endpoint)

```python
engine = Engine('/private/workspace')
try:
    candidate = engine.ingest_package(trusted_package)
    manifest = engine.get(candidate['id'])['manifest']
    project = SageProjectTools.create('/private/workspace', 'my-source-project', manifest,
                                      allowed_project_ids={'my-source-project'})
    agent = ControlledAgent(engine, 'review-run-1', candidate_id=candidate['id'],
                            project_tools=project)  # optional local Ollama; not invoked by constructor
    # agent.run('...') requests bounded project actions; source remains unverified.
finally:
    engine.close()
```

**Caution:** the caller, **not the model or browser**, determines `allowed_project_ids` and the private workspace. These capabilities are not exposed through public endpoints; browser-facing authorization remains a separate, independently reviewed owner gateway. Model output may contain source content and instructions, but cannot authorize file or execution privileges.

## Results and threats

- The adapter never executes or previews source. It does not replace the Docker sandbox or verify generated programs.
- Existing `ACTIONS` remain available to the original candidate-bound agent; no new global host filesystem access is introduced.
- Existing checkpoint logic prevents replay of an uncertain action after a crash; a restored bound agent must supply the same trusted project object.
- Per-trajectory model call and wall-clock limits remain intact.
- **Single-writer constraint remains:** V1's expected-revision check is not an interprocess atomic lock; do not run parallel agents against the same project until a genuine owner-authorized locking layer is designed and tested.
- The trusted workspace and stored trajectories are not safe from a malicious same-user host process. Hashes detect accidental/casual tampering but are not an authentication scheme.
- GitHub Actions Python regression tests prove API behavior only. They are not evidence of live Ollama inference, Docker containment, real iPad Safari, or deployed infrastructure.

## How Agent B should use this

Build only a fixture-driven source viewer and project tree against the V1 [`SAGECODE_V1_CONTRACT.md`](SAGECODE_V1_CONTRACT.md). V2 emits the same source status/tree/read/search/diff shapes, with the additional explicit flags `source_only`, `executed`, `approved`, `release_allowed`. A project-bound finished agent returns `project_id`, `project_revision`, `project_verification:"unverified"`, and `owner_review_required:true`. Do not create a browser API for project editing or enable an Approve button until Agent A has built an authenticated authorization boundary.

## Verification

- Local isolated adapter suite: `python -m unittest discover -s tests -p 'test_sagecode_actions.py' -v` (6 tests; uses a lightweight fixture for the existing Engine).
- Repository CI: `python -m unittest discover -s tests -v` (including the existing `ControlledAgent` tests and new V2 integration tests), then the current Mobile WebKit and fail-closed `merge-gate` checks. Report their exact outcomes; do not hide the known slow WebKit setup on main.

## Sources and reasoning

- Repository: [`controlled_agent.py`](../toad_core/controlled_agent.py), [`project_tools.py`](../toad_core/project_tools.py), [`schema.py`](../toad_core/schema.py), [`lab.py`](../toad_core/lab.py), and existing candidate tests.
- H.E.R.B.I.E. Master Knowledge Bank, pp. 4 (Margaret Hamilton: explicit fault handling), 7 (Rodney Brooks: independent safety layers), and 9 (Grace Hopper: stable abstractions and repeatable tests). These are design analogies, not copied implementations.
- OpenCode tool and permission model as a comparative behavior target, not a runtime: https://opencode.ai/docs/tools/ and https://opencode.ai/docs/permissions/ .
