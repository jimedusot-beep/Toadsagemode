# Mission A: First real calculator coding experiment

Status: FROZEN REQUIREMENTS ONLY. No OpenCode inference or app build is claimed.

Create a dependency-free browser calculator in a disposable workspace with four files: index.html, styles.css, app.mjs, and calculator.mjs. The JavaScript module must export calculate(operation, first, second). Allowed operations: add, subtract, multiply, divide. Division by zero must throw RangeError. The page should provide labeled inputs, keyboard-operable buttons, and clear error feedback for invalid entries. Do not deploy, publish, connect paid services, or edit the acceptance test.

The independent acceptance file calculator-acceptance.test.mjs is copied into the working directory BEFORE prompting the coding agent. Execute using: node --test calculator-acceptance.test.mjs. It will initially fail because calculator.mjs is missing; the red state is expected. Require a real code-generation pass and a later successful run.

Record actual OpenCode executable version, free model ID/provider, full model response, the generated source files, test command, exit status, stdout/stderr, source diff, a supervised repair attempt with red→green evidence, and human approval. Node tests alone are not evidence that a browser interface is accessible; manually inspect keyboard operation and error messages.
