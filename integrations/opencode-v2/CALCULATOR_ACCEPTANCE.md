# Frozen acceptance contract — Calculator Mission 001

**Status: agreed contract, set before any real OpenCode inference.**
Canonical task summary: [CALCULATOR_MISSION.md](CALCULATOR_MISSION.md).
This document adds edge cases and independent verification requirements.

## Approved mission

Build an original, dependency-free, keyboard-accessible, four-operation
calculator website in a disposable workspace. No network libraries,
secret reads, paid models or publishing.

Exactly four generated files (additional test files are optional):
- `index.html`: labeled numeric inputs, four operation buttons, a visible
  result/error area; links `styles.css` and a `type="module"` `app.mjs`.
- `styles.css`: readable, responsive, keyboard focus cues.
- `app.mjs`: browser event-handling code; imports `calculate` from `calculator.mjs`.
- `calculator.mjs`: pure module exporting
  `calculate(operation, first, second)` with no reliance on browser globals.

## API and results

1. Operations are EXACTLY `add`, `subtract`, `multiply`, `divide`.
2. Both numeric operands must be finite JavaScript numbers; reject NaN,
   infinity, strings, undefined and null with `TypeError`.
3. `calculate("add", 7, 5) === 12`.
4. `calculate("subtract", 7, 5) === 2`.
5. `calculate("multiply", 7, 5) === 35`.
6. `calculate("divide", 7, 2) === 3.5`.
7. Negative numbers and decimals work.
8. Divide by zero throws `RangeError`.
9. Unknown operation throws `RangeError`.
10. `index.html` uses external module script and CSS; no inline event
    handlers, `eval`, CDN, telemetry, network dependency or publish action.
11. UI should display errors clearly and not expose unescaped input as HTML.

The **authoritative independent test suite** is
`calculator.acceptance.test.mjs` (with a dot). It lives OUTSIDE the
agent's workspace, and must not be modified by the agent. A separate
`calculator-acceptance.test.mjs` (hyphen, earlier proposal) may also exist
in the review branch; DO NOT copy it to the project or use it for certification.
Only the dotted test suite implements this full contract.

Use the reviewer checkout, on the same disposable isolated test host:

```sh
TOAD_CALCULATOR_DIR=/absolute/path/to/project \
  node --test integrations/opencode-v2/calculator.acceptance.test.mjs
```

The test imports untrusted generated JavaScript. Running Node tests on a
host with sensitive files is unsafe; an OpenCode permission config does not
contain Node execution.

Record exact model ID, price status, CLI version, model response, generated
source, exit status/test stdout, file hashes, diff and manual UI review.
When tests fail, authorize at most two supervised repair attempts with the
same frozen tests. No passing simulated response or mock-only check counts.
