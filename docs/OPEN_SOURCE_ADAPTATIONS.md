# Research and adaptation register — coding agents

Review date: 2026-11-17. This is a design/provenance inventory, **not** an
assertion that a dependency has been installed or a source project forked.

## Original unrestricted-code candidates: what is actually worth integrating

| Upstream | License (repository LICENSE checked) | Useful pattern | Our integration decision |
| --- | --- | --- | --- |
| [99991/MinimalAgent](https://github.com/99991/MinimalAgent) | Unlicense | Explicit request/tool-call/result loop, tool output appended as context | **Study only**: Toad already has a bounded five-action agent and has adapted a separate MIT-licensed mini-SWE-agent loop. Do not copy MinimalAgent's unrestricted `bash`, remote model default, or unbounded `while True`. |
| [luna-system/ada](https://github.com/luna-system/ada) | CC0 1.0 | Local retrieval, remembering relevant lessons, memory consolidation | **Later**: adapt relevance and provenance ideas to existing SQLite + skill retrieval; no Ada server/ChromaDB/model-weights installation. Ada's README targets Python 3.13+; Toad targets 3.11+. |
| [spotrunner1/agent-dialectic-resolver](https://github.com/spotrunner1/agent-dialectic-resolver) | CC0 1.0 | Typed evidence, independent objections, deterministic hard gates, receipts | **Implement small Python gate**: `experiment_review.py` checks preserved test contracts, digest-bound receipts and comparable worker conditions. No TypeScript resolver copied or installed. Its generic confidence scores must not override test failures. |
| [mechakotik/gitevolve](https://github.com/mechakotik/gitevolve) | 0BSD | Multiple code revisions with a fixed evaluator, score history, feedback | **Implement small read-only comparison**: compare two known catalog versions by binary frozen-test outcome and show evidence. No evolutionary mutation loop or Go installation. Upstream warns uncommitted and ignored files may be destroyed when evolving a repository: never run it against H.E.R.B.I.E./Toad core. |

All four URLs and LICENSE files were checked independently. License at the
repository root does not automatically cover third-party dependencies, model
weights, documentation downloads, images or externally imported feeds.
Record exact source paths, version/commit, author, license and changes when
**actually vendoring** source. This feature is original Python adapted from
documented ideas; it does not vendor these four source files.

The other seven candidates in the master recap (SQLite, miniaudio, dr_wav,
minimp3, stb_image, stb_truetype, stb_image_write) are mostly audio/image/
font facilities for **H.E.R.B.I.E.**. SQLite is already used through Python's
standard library by Toad's private catalog. Downloading extra C libraries
does not help the present bounded Python repair goal.

## New: read-only candidate comparison

The deterministic comparator follows two principles:

1. **From gitevolve** — measure the same behavior under the same conditions.
   For now the only score is **1** for a completely passed frozen test suite
   or **0** for an executed test failure. It is not a performance benchmark
   or general-quality grade. Unmeasured criteria cannot contribute.
2. **From Agent Dialectic Resolver** — typed, fail-closed rules decide if
   evidence is comparable. Model prose or high model confidence does not
   resolve a failed rule.

Required gates:

- Same candidate name/version, entrypoint, dependencies, permissions,
  compatibility, identical file paths and immutable tests/test files; only
  source-file contents may differ.
- Each candidate has a stored test receipt tied to its exact package digest,
  with Docker worker, execution evidence, test index/kind/path, cleanup,
  immutable image ID and explicit resource-policy metadata.
- Baseline and challenger used the **same image ID and resource policy**.
  A worker timeout, missing receipt, missing/changed image, incomplete
  passing suite, or missing cleanup blocks comparison.

These checks inspect **existing local database records only**. They never
invoke a model, execute source, install a candidate, change the registry,
alter git state, merge or deploy. The result is always owner-review-only.

### CLI

In a trusted checkout with private catalog records, run:

```sh
python -m toad_core experiments compare BASELINE_CANDIDATE_ID CHALLENGER_CANDIDATE_ID
```

Or for the isolated test catalog:

```sh
python -m toad_core --workspace /private/toad-calculator-lab experiments compare BASELINE_ID CHALLENGER_ID
```

The output includes `gate_results`, `scores`, `changed_paths`,
`assessment`, a digest of the comparison inputs, and explicit
`approved=false`, `installed=false`, `merged=false`, `deployed=false`.

Possible assessments:
- `challenger_improved_test_outcome` — the baseline failed, new source passed
  its frozen suite. **Suggest owner review only**, not adoption.
- `challenger_regressed` — the baseline passed, new source failed.
- `both_pass_no_quality_winner` — both pass; there is no measured winner.
- `both_fail_no_winner` — both fail.
- `incomparable` — at least one evidence gate failed.

The tool treats receipt-shaped **CI test doubles** as ordinary catalog
receipts: it **cannot cryptographically prove** that real Docker execution
occurred. This is a known boundary of the current store interface. Only the
separate real lab smoke test, real-model run, source review and operator-
verified receipts support a live acceptance claim. The SHA256 of the report
is an integrity comparison token, **not a signature**.

### How this fits the calculator experiment

The existing broken-calculator experiment must first:
- Establish a failing baseline from the restricted worker.
- Have the bounded agent produce a new candidate with untouched tests.
- Receive a passing restricted worker receipt.
- Run the independent holdout suite on the exact repaired source.
- **Then** require this deterministic baseline/challenger comparison before
  `ready_for_owner_review` is reported.

No source changes are automatically absorbed into the active Ability Library.
The final decision remains with the human project director.

## Next candidate imports (not yet implemented)

1. **Evidence provenance tiers**: separate verified local-worker evidence,
   borrowed/replayed records, CI doubles, inference and unsupported claims
   so even forged receipt-shaped data cannot be described as a live test.
2. **Local lesson selection**: Ada-style relevance and consolidation using
   SQLite FTS5 and explicit reviewed lesson provenance.
3. **Multiple approved experiment variations**: gitevolve-style history of
   candidate revisions plus a *separate trusted frozen evaluator*; forbid
   mutations to core, user checkout, evaluator or tests.
4. **Owner checkpoint decisions**: typed accept/revise/reject decisions
   stored alongside evidence with rollback reference; still no auto-merge.

### Source links
- MinimalAgent: https://github.com/99991/MinimalAgent
- Ada: https://github.com/luna-system/ada
- Agent Dialectic Resolver: https://github.com/spotrunner1/agent-dialectic-resolver
- gitevolve: https://github.com/mechakotik/gitevolve
- Toad existing bounds: `docs/LAB.md`, `docs/MISSIONS.md`,
  `docs/BROKEN_CALCULATOR_DEMO.md`, `toad_core/controlled_agent.py`.
