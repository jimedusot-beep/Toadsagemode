# Toad Sage × OpenCode V2 — opt-in integration starter

**Status:** review-only integration starter. These tracked files do not install OpenCode, provision a model, launch an agent, or prove it can build an app.

## Strategy

Use OpenCode V2 as the proven external coding engine first, without transplanting its source or changing `toad_core`. The current Toad Sage restricted Docker lab only supports bounded Python standard-library tests. Do not repurpose it as a general OpenCode runtime. Preserve the SQLite catalog, private bridge, owner-review gates, and existing test suite.

- OpenCode active upstream: https://github.com/anomalyco/opencode
- Official install: https://opencode.ai/docs/
- Official V2 permissions: https://opencode.ai/docs/permissions/
- CLI and automation: https://opencode.ai/docs/cli/

A **fork** is a copy linked to the upstream repository on GitHub. A **clone** puts a repository onto a machine. We don't need a fork for this first test: start with upstream OpenCode as a separate tool; fork later only when upstream modifications are needed.

## Review and first live test

1. Provision a dedicated, disposable Linux VM or cloud workspace with Node/npm and a private terminal. Keep secrets, robot credentials and all personal/project directories OFF this host. Do not publish an OpenCode HTTP endpoint. A folder and permissions are not an operating-system sandbox.
2. On that host, follow current official OpenCode V2 instructions. As of 2026-11-19 the official npm command is:
   ```bash
   npm install -g @opencode/cli
   ```
   This can execute a native-binary postinstall script; use a trusted disposable host.
3. Clone the **review branch** of `jimedusot-beep/Toadsagemode` to a trusted checkout solely to retrieve these files. In that checkout:
   ```bash
   python3 tools/opencode_v2_starter.py --check
   ```
   This checks only local configuration and presence of the binary; it does not execute OpenCode.
4. Verify `opencode --version` is V2 and review the `integrations/opencode-v2/opencode.jsonc` policy. For an opt-in interactive run:
   ```bash
   python3 tools/opencode_v2_starter.py --launch
   ```
   This creates a fresh temporary **project** directory and starts `opencode --standalone` there. The temporary directory isolates project files from the Toad Sage checkout **but does not isolate the agent from the host OS**. All shell commands and project edits are set to ask; external directory accesses via built-in path-aware tools are denied.
5. Connect an approved model from within OpenCode. An API/provider plan may still have quotas, cost and rate limits; running local model inference avoids provider-imposed daily message quotas but still requires enough compute.
6. Prompt: **“Build a small four-operation calculator web app. Add automated tests and run them. Explain any failures. Do not deploy or publish anything. Ask before executing commands.”**
7. Inspect actual generated source, test logs, and diffs; report the model used, provider, test commands, pass/fail evidence and any limits. Use a separate review before admitting any reusable code into `toad_core`.

## Safety / limitations

The default V2 permission policy grants broad access unless narrowed. Our configuration asks before shell commands, denies Git pushes, asks before project edits, denies access to outside directories through OpenCode's normal path-aware tools, and blocks direct `.env` access. **Shell commands still run with the host user's privileges**; built-in shell directory inference is best-effort, and the agent can execute networked programs with human permission. These controls are NOT a secure containment boundary. Use an isolated VM/container and never give it production keys.

`--launch` is deliberately interactive; no unattended background worker, no persistent remote bridge, no auto-deploy, and no automatic integration into H.E.R.B.I.E. or Herbie Games. A successful dry-run only demonstrates the config can be read. The first real app and tests must be run and reported on a real host.

## Future adapter after independent validation

Once one real project succeeds, write a separate narrow adapter between Toad Sage's mission queue and OpenCode (job ID, fresh worktree, explicit per-project grants, event log, timeout, process cancellation, evidence receipt, diff for owner approval). Retain per-mission budgets to bound loops; do not impose daily per-user caps. Review actual infrastructure costs and model availability.
