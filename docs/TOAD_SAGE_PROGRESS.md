# Toad Sage development ledger

Owner review ledger · 2026-11-17 · maintained alongside source

This file records what exists, what tests actually ran, and what remains blocked.
**A checked code change is not proof of real Docker containment or local inference.**
No one should merge, deploy, activate an imported ability, or grant host access
on the basis of model statements or this ledger alone.

## Current baseline (read from `main` before this draft)

- [x] Local-first browser absorption inbox and local SQLite catalog are implemented.
- [x] `toad_core/controlled_agent.py` contains a restricted five-action loop, not a shell agent.
- [x] `toad_core/mission_engine.py` supports bounded Python generation, repair, checkpoint and packaging workflows.
- [x] `.github/workflows/validate.yml` already defines a `merge-gate` check.
- [ ] Check that the `merge-gate` check is required by an **active main-branch ruleset** (issue #9).
- [ ] Run a real local restricted Docker smoke test and record containment evidence (issue #11).
- [ ] Complete a real Ollama + Docker calculator mission on a provisioned execution host (issue #11).
- [ ] Confirm human-reviewed sandbox activation and rollback with measured logs (issue #11).
- [ ] Demonstrate independent, meaningful tests of a broken project and bounded repairs using real worker evidence.
- [ ] Independently verify private iPhone-to-engine acceptance; the public Pages inbox remains offline-only.

## Draft checkpoint: agent finish evidence contract

Branch: `fix/agent-finish-review-evidence-20261117`

Change:
- A model `finish` action now ends in `awaiting_review`, **not** in `completed`.
- The result names the selected candidate, records whether a currently verified
  receipt is bound to its exact digest, and always flags owner review as required.
- A finish without tests is allowed as a *proposal*, but is explicitly unverified.
- A finish after multiple revisions must identify the exact candidate revision.
- Completed/blocked/review-pending traces refuse additional actions.
- Duplicate model prompt fields are removed.
- Regression coverage uses explicit worker **doubles**, never a real Docker claim.

Test evidence (first PR run: https://github.com/jimedusot-beep/Toadsagemode/actions/runs/44130050748):
- [x] GitHub CI Python 3.11 and Python 3.12 passed on PR #17 (118 Python tests on 3.12).
- [x] GitHub CI Mobile WebKit passed on PR #17.
- [x] The combined `merge-gate` passed on PR #17.
- [ ] Confirm CI remains green at the final branch head after this ledger-only update.
- [ ] Owner reviews patch and decides separately whether to merge.
- [ ] Real local Docker/Ollama acceptance remains **unverified** and must not be
      inferred from CI doubles.

## Next bounded demonstration

Use the existing `tools/calculator_demo.py` and documented lab setup,
not a second agent framework. Establish a real restricted Docker smoke receipt
first, then a real local model request, then a deliberately broken
**standard-library Python** project whose tests fail before a source-only
repair and pass afterward.

Retain original source, changed source/diff, frozen test definitions, container
image identifier, exact test outputs, digest, cleanup status, and owner decision.
Do not broaden tools, install dependencies, mount home directories, connect
hardware or expose Docker control to a web client.

## Draft checkpoint: deliberately broken calculator\n\nStacked review branch: `feature/reviewable-broken-calculator-demo-20261117` (depends on review of PR #17).\n\n- [x] Add trusted, intentionally broken calculator fixture with frozen unittest cases.\n- [x] Add a review-only source-repair exercise using the existing controlled agent.\n- [x] Add a real-run CLI which first requires the nine live Docker containment probes.\n- [x] Add fail-closed rehearsal tests using explicitly simulated model/worker responses.
- [x] Require independently run holdout tests that the agent cannot modify.\n- [ ] Record green CI Python, Mobile WebKit and merge-gate results for the stacked PR.\n- [ ] Run on an independently provisioned lab host with real Docker/Ollama receipts.\n- [ ] Review original/final candidate digests, changed source, immutable tests and container image ID.\n- [ ] Decide separately whether to merge either PR or activate any version.\n\n## Evidence legend

- **Implemented:** source code exists in the repository.
- **Unit-tested:** GitHub CI or locally executed tests are explicitly linked.
- **Lab-verified:** real restricted worker evidence, image ID and cleanup receipt exist.
- **Owner-approved:** a separate explicit human approval of the specific snapshot.
- **Deployed:** separately authorized rollout and device/browser acceptance were recorded.

References: `README.md`, `docs/LAB.md`, `docs/MISSIONS.md`,
`tests/test_agent_skills_git.py`, GitHub issues #9 and #11.
