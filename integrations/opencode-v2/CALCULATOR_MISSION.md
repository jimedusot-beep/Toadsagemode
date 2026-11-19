# Mission A — first real OpenCode calculator build

**Status: Requirements frozen before live inference; no AI app yet.**

Build a dependency-free browser calculator in a disposable project directory
with four files: `index.html`, `styles.css`, `app.mjs`, and
`calculator.mjs`. The pure JavaScript module must export
`calculate(operation, first, second)`. Permitted operations are `add`,
`subtract`, `multiply`, and `divide`. Division by zero throws
`RangeError`. The page must have labeled numeric inputs, keyboard-operable
buttons, visible feedback and clear error handling. No deployment, external
library installation, network calls, credentials or paid model fallback.

The complete frozen requirements and authoritative independent tests are
in [CALCULATOR_ACCEPTANCE.md](CALCULATOR_ACCEPTANCE.md) and
[`calculator.acceptance.test.mjs`](calculator.acceptance.test.mjs).

Keep reviewer acceptance tests **outside** the agent-writable project, and
never permit the agent to change them. Before inference a red result due to
missing app files is expected; after inference the same tests should pass.
Run independently from the reviewer checkout with `TOAD_CALCULATOR_DIR`
pointing to the agent-generated project, on a disposable isolated host.

Record actual OpenCode version, chosen free model identifier, user-approved
commands, response, source files, test stdout/stderr and status, a bounded
supervised repair with real red-to-green evidence, and owner review.
The tests do not fully validate keyboard usability; manual browser review
is also necessary.
