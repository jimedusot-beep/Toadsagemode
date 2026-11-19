# Frozen acceptance plans — Toad Sage custom app trials

The goal of this stage is **independent requirements**, written and fixed
before an AI model is allowed to draft web-app source. A model must not
grade its own code using tests it invented or edited after seeing the result.

## What this does

1. A trusted operator writes the app's goal and 1–8 short browser checks.
2. Toad Sage stores the goal and checks in a private, exclusively-created
   JSON record with SHA-256 digests. There is no edit/update command.
3. **Only after that** may the local Ollama adapter draft web source.
   The model receives the goal but **never receives the frozen checks**.
4. The model's HTML/CSS/JS stays in the existing JSON-only quarantine. A
   separate trial record binds the source digest and original test-plan digest.
5. A dry-run returns `executed:false`. An operator-approved `--run`
   sends the exact source and original checks to the isolated WebKit Docker
   worker, returning an execution receipt bound to both digests.
6. The trial record **does not become approved** after a pass. Source review,
   real sandbox security evidence, deployment approval and release are
   independent requirements.

## Example: fixed flashcard acceptance checks

The trusted operator writes `flashcard-checks.json` containing:

```json
[
  {"kind":"title","expected":"Flashcard Practice"},
  {"kind":"click_text","selector":"#flip","target":"#flip","contains":"Back"}
]
```

**Order matters.** Before AI generation:

```sh
# 1. Freeze human-authored goal + tests, before an AI model sees the goal.
python -m toad_core app freeze-tests "Make a flashcard page with a flip button" --checks flashcard-checks.json

# 2. Inspect the frozen plan. Save the plan ID returned above.
python -m toad_core app frozen-tests PLAN_ID

# 3. Ask a locally configured Ollama model to draft source ONLY against this plan.
python -m toad_core app draft-with-tests PLAN_ID

# 4. Inspect the newly created trial and its quarantined source separately.
python -m toad_core app web-trial TRIAL_ID
python -m toad_core app code-report DRAFT_ID
python -m toad_core app code-show DRAFT_ID

# 5. DRY RUN — source is NOT executed:
python -m toad_core app test-web-trial TRIAL_ID

# 6. ONLY on a disposable dedicated Linux VM after Docker security probes,
# and with explicit operator authorization, execute inside isolated WebKit:
python -m toad_core app test-web-trial TRIAL_ID --run
```

Neither Netlify nor the iPhone browser can run the local Ollama or Docker
worker. Do not confuse this branch's Python CLI commands with a deployed
mobile web service.

## Safety and limitations

- `app freeze-tests` reads a short operator-controlled regular JSON file,
  not code returned by the model. It validates the same four limited
  declarative check kinds as the WebKit worker; it accepts no JS snippets.
- The private plan is created first; `draft-with-tests` refuses a missing
  or tampered plan **before contacting the model**.
- A trial ties `plan_sha256`, `checks_sha256` and `source_sha256` to
  the exact quarantined source. A source, plan or trial modification is
  rejected before testing. Digests protect against accidental/uncoordinated
  changes, **not a privileged operator rewriting all records and hashes**.
  Strong evidence would require an external trusted audit log or signed
  attestation.
- The old `draft-code` / `browser-test --checks` commands remain
  available for **exploration only**. Use the frozen-trial workflow for
  test evidence. Neither path is production release authorization.
- Even a green isolated test does not verify security, accessibility,
  all requirements, or production readiness. A green CI run with Docker
  doubles does **not** establish a real container ran. The status remains
  `release_allowed:false`.
- The model's app code is never executed in GitHub Actions. The new
  test suite injects model and worker doubles, and checks that frozen
  tests predate any model call and cannot be changed after source generation.
- A real Ollama model, disposable VM, live browser smoke, independent
  holdout tests, bounded repair loop, review UI and owner-approved
  Netlify release are **still incomplete**.

## Acceptance evidence

GitHub workflow checks in `tests/test_web_acceptance.py` cover a positive
candidate, blocked dry run, refused faulty plan and source, swapped hashes,
negative worker receipt, forged trial metadata, rejected self-written
JavaScript tests, and CLI validation. These are contract tests **only**.

References:
- [Quarantined code format](WEB_CODE_QUARANTINE.md)
- [Isolated WebKit Docker worker](WEBKIT_LAB.md)
- [Ollama JSON adapter](../toad_core/models.py)
- [Playwright Docker documentation](https://playwright.dev/docs/docker)
