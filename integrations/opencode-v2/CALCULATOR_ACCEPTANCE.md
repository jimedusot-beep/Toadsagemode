# Frozen acceptance contract — Calculator Mission 001

Status: **test contract frozen before the first live OpenCode model run**.
These are independent checks, not evidence the agent has succeeded.

## Approved mission

Build an original, dependency-free, accessible four-operation calculator web app
in an otherwise empty disposable project folder. No publishing, network libraries,
paid models, package installation, secrets, or changes to this acceptance contract.

Required output:
- `index.html`: numeric inputs, four operation controls, visible result/error region;
  link to `styles.css` and a module script `calculator.mjs`.
- `styles.css`: readable, responsive, keyboard-visible controls.
- `calculator.mjs`: export pure function `calculate(a, b, operator)`; also attach
  browser event handlers without relying on browser globals when imported by Node.

API contract:
1. Numeric `a` and `b` must both be finite numbers (reject NaN, Infinity and strings).
2. Operator is exactly `+`, `-`, `*`, or `/`.
3. `calculate(2, 3, "+") === 5`.
4. `calculate(8, 3, "-") === 5`.
5. `calculate(7, 6, "*") === 42`.
6. `calculate(12, 4, "/") === 3`.
7. Negative and decimal values work.
8. Division by zero throws `RangeError` (not Infinity or NaN).
9. Unknown operations throw `RangeError`.
10. Non-finite/non-number operands throw `TypeError`.
11. HTML must not use inline JavaScript or `eval`; UI must display errors, not crash.
12. No external resources, libraries, telemetry or publishing endpoints.

The independent test file is
`integrations/opencode-v2/calculator.acceptance.test.mjs`.
Run ONLY on the disposable host, from the reviewer checkout:

```sh
TOAD_CALCULATOR_DIR=/absolute/path/to/agent/project \
  node --test integrations/opencode-v2/calculator.acceptance.test.mjs
```

Security note: imported candidate JavaScript can execute arbitrary Node code even
during tests. A successful test run is **not proof of containment**. Keep the whole
reviewer test process inside an OS-isolated disposable host with no secrets.
Do not copy or allow edits to the original acceptance tests inside the agent folder.

## Evidence record

Record OpenCode binary version, model/provider and free-price check, commands,
test stdout/stderr and exit status, generated file hashes, source diff,
manual review findings, repair attempt count, charges checked and reviewer
approval. Do not mark this milestone complete without a real model response,
real generated source and executed independent test results.
