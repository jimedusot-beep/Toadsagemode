# Toad Sage — development and integration ledger

Updated: **2026-11-17** · Project: `jimedusot-beep/Toadsagemode`

This is an evidence inventory, not a claim of autonomous intelligence. Distinguish
code present on `main`, CI using **explicit worker/model test doubles**, and
acceptance using a real local Ollama + restricted Docker host.

## Integrated into `main`

All three originally stacked PRs were merged in their dependency order,
with a normal Git merge. The resulting files were independently fetched from
`main` after the final merge.

| PR | Feature | Result | Merge commit | Original PR-head CI |
| --- | --- | --- | --- | --- |
| [#17](https://github.com/jimedusot-beep/Toadsagemode/pull/17) | Agent `finish` -> `awaiting_review`; evidence-linked result; frozen approval gate | **Merged** | [`848f464d`](https://github.com/jimedusot-beep/Toadsagemode/commit/848f464d0b5134d9bae148230d9bc116881e9c79) | [green](https://github.com/jimedusot-beep/Toadsagemode/actions/runs/44130419373) |
| [#18](https://github.com/jimedusot-beep/Toadsagemode/pull/18) | Broken-calculator source-only agent repair rehearsal, independent holdout, opt-in local runner | **Merged** | [`99155c6b`](https://github.com/jimedusot-beep/Toadsagemode/commit/99155c6bcc8efe6fa570b04c8f9299cea0019651) | [green](https://github.com/jimedusot-beep/Toadsagemode/actions/runs/44132573508) |
| [#20](https://github.com/jimedusot-beep/Toadsagemode/pull/20) | Read-only, deterministic comparison of candidate revisions; integration with repair demo | **Merged** | [`1400612d`](https://github.com/jimedusot-beep/Toadsagemode/commit/1400612d124ec511f4ffe745f513962a4d56aee3) | [green](https://github.com/jimedusot-beep/Toadsagemode/actions/runs/44134818701) |

The final reviewed PR-head run for #20 passed **Python 3.11**, **Python 3.12**
(136 trusted Python tests), **Mobile WebKit**, and the combined **merge-gate**.
These tests exercise trusted application logic. Synthetic model/worker test
doubles do *not* prove a successful real-model repair or Docker containment.

**Important CI caveat:** `.github/workflows/validate.yml` deliberately
excludes pushes to `main`, so its green runs are *pre-merge PR validation*.
No fresh post-merge `main` validation run is claimed here. Confirm the
`merge-gate` is required by an active branch ruleset (issue #9).

## Existing foundations on `main`

- [x] Phone-friendly local Feed Toad inbox, backup/import and deduplication.
- [x] Local SQLite candidate catalog and project/mission history.
- [x] Restricted five-action `ControlledAgent` (no arbitrary shell tool).
- [x] Crash-safe trajectory persistence, source-only draft edits and bounded tests.
- [x] `finish` generates an owner-review proposal, not an automatic install/merge.
- [x] Deliberately broken calculator plus frozen and independent holdout tests.
- [x] Read-only revision comparator with test, receipt, digest and lab-policy gates.
- [x] Research register: `docs/OPEN_SOURCE_ADAPTATIONS.md`.

## Acceptance still outstanding

- [ ] Live Docker lab smoke tests on the intended execution host, with real
      isolation enforcement and cleanup receipts (issue #11).
- [ ] Real local model repairs intentionally broken code, followed by a
      passing restricted Docker receipt, independent holdout and reviewable diff.
- [ ] Review actual baseline/final candidate digests, container image ID,
      mutable workspace restrictions and owner approval.
- [ ] Verify and enforce active GitHub `main` ruleset requiring merge-gate
      (issue #9).
- [ ] Verify private iPhone access to the local engine; the public Pages inbox
      remains offline-only.
- [ ] Validate approved ability activation and rollback in the real lab.
- [ ] Add provenance-aware lesson retrieval and memory consolidation without
      installing Ada or importing third-party model weights.
- [ ] Demonstrate a real, small application generated and tested by Toad Sage,
      with separate project director approval.
- [ ] Explicitly authorize any deployment or activation independently of a
      code merge.

## Safe next command — metadata-only

From an independently trusted **local clone**, before running submitted code:

```sh
python tools/broken_calculator_demo.py
```

To attempt real execution, first provision the local model and the restricted
Docker image per [LAB.md](LAB.md), confirm the intended machine's security
controls, then explicitly use `--run`. The runner first requires the nine
local containment probes; it refuses to fall back to host execution.

The comparison command reads existing private catalog records without
executing source:

```sh
python -m toad_core experiments compare BASELINE_ID CHALLENGER_ID
```

See [Broken Calculator Demo](BROKEN_CALCULATOR_DEMO.md) and
[Open Source Adaptations](OPEN_SOURCE_ADAPTATIONS.md). Source licenses are
reviewed in the adaptation register, but no wholesale external coding agent
framework has been installed.

## Evidence terminology

- **Implemented** — source exists on `main`.
- **CI-tested** — test suite and immutable run ID are recorded.
- **Lab-verified** — a *real* restricted worker's behavior, image and cleanup
  have been independently checked on the intended host.
- **Owner-approved** — an explicit approval of the specified revision and
  evidence after review.
- **Deployed** — a separately authorized activation and device/browser
  acceptance record exist.

Nothing in the three merges activated imported code, gave the agent arbitrary
host permissions, deployed a web app, or proved autonomous game development.
