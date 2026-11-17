# Broken calculator — source-only agent repair experiment

This is the second Toad Sage acceptance checkpoint: demonstrate that the
**existing** controlled agent can investigate a deliberately broken Python
calculator, submit a source-only patch, test it in the local restricted Docker
worker and prepare an owner review record. There is no host-execution fallback.

**The public iPhone dashboard is an offline intake interface. It cannot start
this experiment.** The real run is a separate opt-in operation on a provisioned
execution host; it does not require a new or unrestricted agent framework.

## Exactly what is being tested

- Trusted fixture: `calculator.py` has an intentionally wrong `subtract(a, b)`
  implementation; `tests/test_calculator.py` covers addition, subtraction,
  multiplication, fractional division and division-by-zero handling.
- The initial `unittest` **must actually fail inside Docker** for the known bug.
  A syntax failure, blocked worker, timeout, cleanup failure or an already
  passing baseline does not count.
- The existing `ControlledAgent` may read only the fixture candidate, propose
  source-only edits via its disposable Git draft, request restricted Docker
  tests, and finish by identifying the tested *new* revision.
- The frozen test specifications and `tests/test_calculator.py` must remain
  unchanged. The final approved-for-review source change must be only
  `calculator.py`.
- A successful real run must have a failed baseline receipt and a passed
  final receipt with the exact matching source digests, Docker image identity,
  `executed=true`, `cleanup_ok=true`, and the agent's own test observation.
- After the agent reports a passing repair, a separately constructed
  **holdout unittest suite** checks additional inputs (signs, zero, fractions)
  in another restricted Docker run. The model never receives this holdout
  fixture as an editable candidate. The holdout package must use the exact
  same `calculator.py` source bytes and pass its own digest-bound receipt.
  Passing only the model-visible tests is insufficient.
- The final state is `ready_for_owner_review`, **not installed, merged, or
  deployed**. The owner must inspect the actual diff, tests and receipts.

A model can make an incorrect patch or finish early: those outcomes are reported
as **blocked**, not automatically retried with more privileges.

## Preflight (safe, no candidate execution)

From a trusted local clone, with Python 3.11+, Git, a **locally provisioned**
Ollama coding model and the separately built `toad-sage-lab:1` Docker image:

```sh
python tools/broken_calculator_demo.py
```

This checks metadata only. It does not ingest a candidate, run Docker tests,
generate code, or install a model.

## Optional real run — only on a trusted lab host

Before invoking the run, follow
[the Docker lab threat model and setup](LAB.md). The `--run` command
automatically performs the live nine-probe containment suite on the same host
and refuses the repair experiment if any probe fails. This suite **must not**
be added to shared GitHub Actions CI.

```sh
python tools/broken_calculator_demo.py --run
```

Optional isolated private storage:

```sh
python tools/broken_calculator_demo.py --run --workspace /private/toad-calculator-lab
```

The default private experiment catalog is a dedicated
`experiments/broken-calculator` subdirectory below Toad Sage's normal
user-data directory, separate from the main ability catalog. This command
does **not** install the repaired candidate, merge a branch, contact public
services or deploy a webpage.

When the real worker and model complete successfully, inspect:
- `experiment-reports/containment-*.json` — all nine real containment probes.
- `experiment-reports/repair-*.json` — baseline, final and independent
  holdout receipt summaries, candidate digests, changed paths, and proposal diff.
- `agent-trajectories/calculator-*.json` — agent action/observation audit trail.
- `catalog.sqlite3` — full original and proposed source, test specifications,
  and receipts. Use `python -m toad_core --workspace PATH library show ID`
  to view each candidate without executing it.

The report also includes `comparison` from the new deterministic
baseline/challenger comparator. That comparator requires matching frozen
tests, immutable image IDs and identical resource policies. Missing or
incomparable evidence blocks the final `ready_for_owner_review` result.
The `experiments compare` CLI can later inspect the same stored candidates
without executing them. See [source adaptation register](OPEN_SOURCE_ADAPTATIONS.md).

A separate operator should independently verify that the tests meaningfully
cover the requested behavior. A passing test suite does not prove that a
candidate is harmless or that the model has generally learned to repair code.

## Test evidence vs real evidence

The trusted unit tests in `tests/test_repair_demo.py` simulate the model and
Docker boundary with explicitly labelled test doubles. They test orchestration,
failure gates, frozen tests, digest differences and review-only state.

- `rehearsal_passed` = **test doubles** passed; no real candidate execution.
- `ready_for_owner_review` = local Docker/Ollama path *reported* success;
  independent review and its full receipts are still required.
- `blocked` = a prerequisite, failing-baseline proof, model action, restricted
  test, source-only gate or receipt check was missing.

No GitHub CI result alone can establish successful local sandbox isolation or
real model-assisted repair on the final machine. Keep those gates distinct.

Relevant code: `toad_core/controlled_agent.py`,
`toad_core/repair_demo.py`, `toad_core/repair.py`,
`tools/broken_calculator_demo.py`, `tools/lab_smoke.py`.
Related tracking: issues #9 and #11.
