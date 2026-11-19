# Toad Sage × OpenCode V2 — supervised experiment

**Status:** open draft PR; not merged, not deployed. This is a guarded launcher,
an offline test suite, a reproducible CLI smoke job, and a frozen first-app
contract. It does NOT show a real AI-generated application or active Toad Sage
mission adapter yet.

## Architecture

```text
Owner / iPad
     |
Toad Sage requirements and human approval (no code execution in public UI)
     |
Disposable OS-isolated development host, no production secrets
     |-- OpenCode V2.3.2 CLI in a private session
     |       |-- selected free model (must verify live)
     |       |-- edits and shell requests require review
     |       '-- generated app in isolated project directory
     |-- Independent frozen test runner (separate from agent workspace)
     '-- logs / source diff / review, then optional PR with approval
```

Toad Sage remains the product owner, planner and review/memory layer.
OpenCode is the external code-writing agent. The separate worker is
responsible for actual OS isolation. An isolated temporary folder and
OpenCode permissions are NOT a security sandbox.

## What is implemented in this branch

- `opencode.jsonc`: ordered V2 permissions with hard-deny policies,
  restricted to the OpenCode provider and anonymous integration. Denies
  external-directory tools, secret file access, configuration edits, push
  and publishing commands. Requires approval for shell and edits. All unknown
  tools are denied initially. The command policy is **not** a shell sandbox;
  variants of commands and approved arbitrary programs can still access the
  host. Strong host isolation is mandatory.
- `version.txt`: the reproducible OpenCode CLI version `2.3.2`.
- `tools/opencode_v2_starter.py`: exact local config verification, V2
  version probe, standalone interactive launcher, and an isolated HOME/XDG
  configuration. It does not install, make API calls or provision hosts.
- `tests/test_opencode_v2_starter.py`: offline regression checks; mocks
  do not prove live inference or security containment.
- `CALCULATOR_ACCEPTANCE.md` and
  `calculator.acceptance.test.mjs`: frozen calculator specifications
  and independent Node acceptance checks, written **before** inference.
- `.github/workflows/opencode-v2-starter.yml`: Python policy tests, Node
  syntax check and pinned OpenCode CLI installation/version smoke. No model
  prompt, no API key or deployment. Inspect CI runs for actual pass/fail.

## First interactive test from iPad in a *disposable* Codespace

1. Confirm GitHub Codespaces remaining free monthly allowance and spending
   settings; choose the smallest 2-core machine. Do not enable paid overages.
   Start a NEW Codespace from this PR's branch, not production. Codespaces
   is a development host, **not** proof of isolation from GitHub credentials;
   a truly strong adversarial code sandbox needs additional isolation.
2. Ensure no H.E.R.B.I.E. private files, GitHub tokens, robot credentials or
   paid-model keys are present. The launcher filters inherited environment
   keys for OpenCode but cannot sanitize the entire host.
3. In a terminal within the branch checkout, run:

   ```sh
   npm install -g @opencode/cli@2.3.2
   python3 tools/opencode_v2_starter.py --validate-config
   python3 tools/opencode_v2_starter.py --check
   ```

   These commands check the pinned binary and policy, not actual AI use.
   OpenCode's npm postinstall downloads/runs native code: only install in a
   disposable host.
4. On the same disposable host, launch interactively:

   ```sh
   python3 tools/opencode_v2_starter.py --launch
   ```

   The launcher prints a temporary `.../project` path. It creates an
   isolated OpenCode home to avoid inherited API accounts. Choose a model
   explicitly labeled **Free** in the currently displayed OpenCode model
   list. Prefer synthetic data. Do **not** connect a payment method or paid
   provider; disable auto-recharge and ensure no paid fallback.
5. Submit this approved prompt:

   > Build a dependency-free four-operation calculator website in this
   > empty project. Read the requirements I provide from CALCULATOR_ACCEPTANCE.
   > Create index.html, styles.css and calculator.mjs. Export the pure
   > calculate(a,b,operator) function. Ask before any shell command or
   > edit. Do not deploy, publish, install dependencies, use external
   > resources or change acceptance requirements.

   Supply the short requirements from `CALCULATOR_ACCEPTANCE.md` as plain
   text without giving the agent the separate test file or any external
   file access. Approve only commands you inspect.
6. Exit with Ctrl+C. Before copying any generated code into trusted
   projects, run the independent acceptance test in the same
   disposable host, replacing the placeholder with the launcher path:

   ```sh
   TOAD_CALCULATOR_DIR=/tmp/toad-opencode-v2-XXXXX/project \
      node --test integrations/opencode-v2/calculator.acceptance.test.mjs
   ```

   The test imports untrusted candidate code: do not run it on a personal
   computer or a host containing production credentials. Record the
   real exit code, captured output, file hashes and any failure details.
7. If it fails, provide failure evidence and authorize at most TWO
   supervised repair attempts. Rerun the exact same frozen tests.
   Do not alter the tests to accommodate the candidate.
8. Review source and test evidence; stop/delete the Codespace when finished
   (GitHub Codespaces page > your codespace > ... > Delete). This also avoids
   accumulating storage usage. Delete temporary source only after preserving
   whatever non-sensitive evidence you want to keep.

## Cost and privacy

Current official OpenCode documentation lists some limited-time free
models. Free availability can change and may depend on provider terms.
**$0 model use has not been measured or proven here.** The OpenCode provider
may also offer paid models. Never assume being connected to the provider
means every available model is free. Confirm model label, usage and bill
after any actual test.

The configuration allows signed-out OpenCode access but does not guarantee
that a specific free model is currently selectable. Do not add provider
credentials or payment methods to this experiment.

See:
- https://opencode.ai/docs/
- https://opencode.ai/docs/permissions/
- https://opencode.ai/docs/policies/
- https://opencode.ai/docs/cli/
- https://opencode.ai/docs/console/models
- https://docs.github.com/en/billing/reference/product-usage-included

## Evidence and stop conditions

| Evidence | Current status |
| --- | --- |
| PR with version-pinned and reviewed config | Changes proposed here |
| Python policy regression checks | New automated CI; inspect latest run |
| Real OpenCode executable version on GitHub runner | CI smoke planned; inspect run |
| Host isolation adequate for hostile code | Not validated |
| Free model authenticated/used | Not verified |
| Actual AI-created calculator | Not verified |
| Independent calculator tests passing | Not verified |
| Repair loop and runtime adapter | Not built |
| GitHub merge, publishing or Herbie hardware access | Deliberately disabled |

Never call a mocked response an AI model run. Never mark a job passed without
actual receipts. Do not merge or deploy this experiment until reviewed.
