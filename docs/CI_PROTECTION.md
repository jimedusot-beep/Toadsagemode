# Required CI gate and main branch protection

The `.github/workflows/validate.yml` workflow tests Python 3.11, Python 3.12, browser data contracts, and Mobile WebKit. It now ends with a **real job** named `merge-gate`, which requires both the complete Python matrix and Mobile WebKit job to finish successfully.

The gate runs with `if: always()` so a failed, skipped, or cancelled upstream job does **not** cause the gate to silently be skipped. It fails unless both job results equal `success`. It cannot be satisfied by a PR description, comment, or manually reported result. No tests were removed or weakened.

## GitHub branch ruleset activation

An owner or admin must configure this in GitHub's repository settings. The connected GitHub app cannot edit the ruleset.

1. **First merge this dedicated CI-only PR** to `main` once all its checks pass, then verify the main Pages workflow deploy still passes. `main` is currently unprotected; this should be the last merge before activating protection.
2. Open **Settings → Rules → Rulesets → New branch ruleset**.
3. Name it **Protect main — CI before merge**, Enforcement **Active**, include **Default branch (main)**, bypass list **empty**.
4. Enable **Require a pull request before merging**, with **0 required approvals** for the solo maintainer. Enable **Require status checks to pass** and select the exact **`merge-gate`** check with the GitHub Actions source. Also enable **Require branches to be up to date before merging** (strict mode).
5. Enable **Restrict deletions** and **Block force pushes**. Leave **Restrict updates**, **Restrict creations**, required deployments, signed commits, and required Code Owners approvals disabled unless explicitly needed; some can make an owner-only repository unmergeable.
6. The Pages **`deploy`** job is main-only, so **do not require it** as a PR gate.
7. Verify a real PR produces `merge-gate` from the direct PR-triggered workflow and that GitHub blocks its merge while checks are pending or failed.

### How the existing workflows differ

The PR-triggered `validate.yml` job is named **`merge-gate`**. In the main-only `pages.yml` workflow, `validate.yml` is a *reusable workflow* called by the `validate` job, so GitHub will display the nested job as **`validate / merge-gate`**. This is expected. Require the direct PR check `merge-gate` for the branch ruleset. The Pages deployment's existing `needs: validate` also waits for the reusable workflow's gate.

The ruleset's strict branch policy may require updating older PR branches after the CI-only change merges. In particular, merge PR #7 (Agent Skills validator) first after updating/retesting, and only then retarget stacked PR #8 (offline skill discovery) to `main` and retest. **Do not merge #8 ahead of #7**.

## Fail-closed / recovery policy

If the gate is missing or fails, inspect [Actions](https://github.com/jimedusot-beep/Toadsagemode/actions), check upstream Python and WebKit logs, and fix CI or candidate code on a separate PR branch. Don't disable required checks or add bypass actors to make an untested change merge. The owner can use GitHub's protected repository ruleset settings to repair a misconfigured check name deliberately, preserving audit history.

No new runtime dependencies, model calls, candidate execution, or changes to public site assets are required.
