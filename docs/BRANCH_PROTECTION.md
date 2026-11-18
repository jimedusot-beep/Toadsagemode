# Protecting the Toad Sage `main` branch

Owner setup and acceptance guide · November 17, 2026

The repository has a tested `merge-gate` job, but that job is **not
automatically enforced** unless a live GitHub repository ruleset requires it.

## Owner settings to apply

Go to [repository rulesets](https://github.com/jimedusot-beep/Toadsagemode/settings/rules)
and create a **New branch ruleset**:

| Setting | Value |
| --- | --- |
| Name | `Protect main — required CI and PRs` |
| Enforcement | **Active** |
| Target branches | **Default branch** (`main`) |
| Require a pull request before merging | **On** |
| Required approving reviews | **0** for current single-maintainer work; increase only when an independent reviewer is available |
| Require status checks before merging | **On** |
| Required check | **`merge-gate`** from **GitHub Actions** |
| Require branches up to date before merging | **On** |
| Restrict deletions | **On** |
| Block force pushes | **On** |
| Ruleset bypass permissions | **None** |

Do **not** require the GitHub Pages `deploy` job: it only runs for `main`
publication, not ordinary pull requests. Do not impose rules requiring
an unavailable second reviewer for this solo-maintainer repository.

## Existing check contract

The `merge-gate` job lives in
[validate.yml](../.github/workflows/validate.yml). It requires both:
- Python 3.11 and Python 3.12 CI matrix success.
- Mobile WebKit success.

It uses `if: always()` to refuse a false green result if any prerequisite
job was skipped, cancelled or failed. The check is called **`merge-gate`**,
not `merge_gate` and not `Publish Sage Toad Dashboard / deploy`.

Reference: [PR #21 successful run](https://github.com/jimedusot-beep/Toadsagemode/actions/runs/44203207520).

## Acceptance test

This documentation change intentionally starts as a harmless **test PR**.

1. Create/activate the above ruleset in GitHub Settings.
2. Refresh the test PR; confirm `merge-gate` is shown as **required**.
3. Verify that GitHub does not permit merging the PR while the required job
   is pending or failing. Do not intentionally break core tests to test this.
4. Let all jobs complete successfully and confirm ordinary merging is
   permitted **only after** the required check passes.
5. Verify the GitHub API `GET /repos/jimedusot-beep/Toadsagemode/branches/main`
   reports `protected: true`, and
   `GET /repos/jimedusot-beep/Toadsagemode/rulesets?includes_parents=true`
   contains an **active** ruleset targeting `main`.
6. Retain evidence in [Issue #9](https://github.com/jimedusot-beep/Toadsagemode/issues/9).
   Close it **only** when enforcement has been verified. Merge this docs PR
   after protection is active and CI is green.

**Recovery:** A typo in the required-check name can block all PR merges.
Use the GitHub Actions Checks section of a recent PR to identify the real
check name and correct the ruleset as an administrator. If real tests fail,
fix the tests or underlying problem instead of bypassing the rules.

This branch-protection gate only governs repository changes. It does
**not** authorize running unknown candidate code, local Docker access,
application deployment, H.E.R.B.I.E. hardware changes, or paid services.

## Primary GitHub documentation

- [Create repository rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository)
- [Rules available in a ruleset](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [Troubleshoot required checks](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks)
