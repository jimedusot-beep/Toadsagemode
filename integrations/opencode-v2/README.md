# Toad Sage × OpenCode V2 — supervised calculator pilot

**State:** Draft PR #35; no agent inference, real calculator build, OS-level containment, or paid/free billing result is verified yet. Do not merge or deploy automatically.

## System design

Toad Sage (owner approvals, mission history) → frozen specification → OpenCode V2 in disposable cloud VM → candidate files → independent Node tests → reviewable evidence → separate draft PR. OpenCode never receives H.E.R.B.I.E. robot controls, production credentials, or unrestricted deployment rights.

Toad Sage retains mission planning, SQLite memory, and final review. OpenCode is only the external code-writing engine. An isolated testing worker and SDK adapter remain future work.

## Exact first-run process from an iPad

1. Open [Toadsagemode PR #35](https://github.com/jimedusot-beep/Toadsagemode/pull/35) and its branch `integration/opencode-v2-starter-20261119`. In GitHub, choose **Code → Codespaces** and create a small disposable Codespace on this branch. Verify monthly included usage and do not enable paid overages. This creates a cloud Linux workspace, not a process on the iPad.
2. In its terminal, from the repository root, install the **pinned** OpenCode version. This installs a native executable and should run only on the disposable host:

   ```sh
   npm install -g @opencode/cli@2.3.2
   ```

3. Validate the exact reviewed config offline, execute the local Python regression tests, and check the actual installed binary:

   ```sh
   python3 tools/opencode_v2_starter.py --validate-config
   python3 -m unittest discover -s tests -p 'test_opencode_v2_starter.py' -v
   python3 tools/opencode_v2_starter.py --check
   ```

`--validate-config` does **not** execute OpenCode. `--check` **does** run `opencode --version` and requires the exact version in `integrations/opencode-v2/version.txt` (currently 2.3.2). Passing local unit tests does not prove runtime policy enforcement.

4. Launch the **interactive** V2 application:

   ```sh
   python3 tools/opencode_v2_starter.py --launch --expected-version 2.3.2 --model opencode/deepseek-v4.1-flash-free
   ```

The starter creates an empty project, a fresh HOME with scrubbed environment variables, and a private `opencode --standalone` service. It preloads the frozen `CALCULATOR_MISSION.md` and `calculator-acceptance.test.mjs`. The project is disposable but is **not an OS sandbox**; approved shell commands still carry host-user privileges.

5. Before sending any prompt, confirm OpenCode visibly selected `opencode/deepseek-v4.1-flash-free`. Official catalog currently lists this as free for a limited time, but free status can change. **Stay signed out of Console** and do not add provider API keys or payment methods. The configuration defaults to one free model and narrows providers, but cannot guarantee $0 if you manually switch to another model. Stop if free model is unavailable.

6. Ask OpenCode to implement the preloaded mission. Do not modify the frozen acceptance test. Approve one comprehensible command/edit request at a time, never a standing blanket approval. When source files exist, run independently in the experiment folder:

   ```sh
   node --test calculator-acceptance.test.mjs
   ```

Record the command, model and version, full stdout/stderr, exit code and generated diff. Preserve a failing test and then one supervised repair with a passing retest. Manually check keyboard interaction and invalid-input messages in the browser. The frozen test intentionally fails when `calculator.mjs` does not yet exist.

7. Exit OpenCode (Ctrl+C or normal exit), inspect logs and generated source, and only then decide whether to copy results into a feature branch for review. Delete the Codespace from https://github.com/codespaces after collecting evidence; its compute usage stops and storage eventually stops accruing after deletion.

## Boundaries and evidence gates

- **Permissions:** ordered V2 rules ask for shell/edit and deny unauthorized external paths and selected sensitive/destructive operations. Hard policies deny unrelated providers, integrations, plugins, MCP, web search and out-of-project access. Built-in shell checks remain best-effort and can be bypassed through commands the human approves; security requires OS isolation.
- **Version:** exact 2.3.2 pin, checked using the actual CLI before launch; do not install `latest` as an uncontrolled runtime.
- **Price:** the signed-out free model is the default and provider selection is restricted, but real no-charge proof requires an actual successful free model session and account/billing verification. Never submit private project data.
- **Test evidence:** repository Python regression tests verify the starter, not actual OpenCode. Its new GitHub workflow runs only offline checks. An agent-generated calculator, a real failed test, a real correction and a passing test are still unverified.
- **Frozen inputs:** mission and test are copied into the temporary workspace as read-only audit cues; the script hashes them after the agent exits and fails if modified. Read-only permissions and hashes cannot prevent same-UID command execution.
- **No automatic release:** GitHub PR creation, merging, deployments, production secrets and robot movement are outside the coding agent's first pilot.

## Official references

- [OpenCode install](https://opencode.ai/docs/) and [CLI standalone mode](https://opencode.ai/docs/cli/)
- [V2 permission order](https://opencode.ai/docs/permissions/) and [hard policies](https://opencode.ai/docs/policies/)
- [Free-model catalog and privacy terms](https://opencode.ai/docs/console/models/)
- [SDK for later Toad Sage adapter](https://opencode.ai/docs/build/sdk/)
- [Codespaces included usage](https://docs.github.com/en/codespaces/troubleshooting/troubleshooting-included-usage)

## Reconciliation note (2026-11-19)

The frozen calculator contract uses **calculate(operation, first, second)**
with four required generated files: index.html, styles.css, app.mjs and
calculator.mjs. The independent dotted test suite has been corrected to match.
Mock fixture tests are not evidence that OpenCode generated an app. The
launcher requires exact `--expected-version` and `--model` arguments and has
no live model result yet. Do not merge or deploy without runtime evidence.
