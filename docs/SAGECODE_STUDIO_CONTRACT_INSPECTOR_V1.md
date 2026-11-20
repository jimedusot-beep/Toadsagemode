# SageCode Contract Inspector V1 — Agent B frontend handoff

**Status:** Draft, static, read-only, fixture-only. No SageCode HTTP service, live model generation, permission grant, external file access, code execution, Git merge, deployment, or real approval.

## What this adds

The existing Project Explorer links to `free-studio/sagecode-contract.html`, a separate iPad-friendly inspection page backed by `free-studio/sagecode-contract-fixture.json`. This is a **sample**, not a real `SageProjectTools` response.

The page displays the response shapes from Agent A's separate [SageCode Tools V1 PR #46](https://github.com/jimedusot-beep/Toadsagemode/pull/46): project status, manifest-derived directories and file entries, bounded source readers, filename/content search hits, and a pending proposed unified diff. All source and diffs use `textContent`. The page has **no apply, approve, edit, execute, deploy, checkout or host-access functionality**.

Every source remains explicitly marked **fixture**. Even a passing local SHA-256 check is described as `sample text consistency`, never as authenticated source, tested code or safe execution.

## Trust and provenance checks

- `free-studio/sagecode-contract-adapter.js` validates the exact example fields, project IDs, 64-character lowercase revision and file digests, revision matching across status/tree/reads/search, bounded declared source paths, file counts, byte lengths, 16-kB source views, line numbering, bounded search results, proposal ancestry and 30-kB diff text.
- SageCode V1 status must remain `verification: "unverified"`, `review_status: "pending_review"`, `executed: false`, `approved: false`, `release_allowed: false` and `test_evidence: null`. Attempts to inject green verified/approved outcomes are rejected before rendering.
- Complete sample source views must match manifest byte lengths and the SHA-256 digests recomputed using browser `crypto.subtle.digest('SHA-256', ...)`. A mismatch blocks the entire inspector.
- **Partial/truncated source cannot prove a whole-file digest.** It stays readable only as a flagged partial view and does not display a green verified status or pretend more source can be fetched.
- Unknown fields, directory/file inconsistencies, outside-tree search hits, stale/cross-project revisions, missing or corrupt fixtures, and unavailable SHA-256 block the view. An explicit Retry button allows recovery.
- Hash checks only compare fixture bytes with fixture metadata from the same origin. They are **not** authenticity, integrity against a compromised serving origin, proof that Agent A ran, sandbox verification or owner authorization.
- A SHA-256-looking revision string is only a sample identifier here. This UI **does not recompute/attest Agent A's immutable server revision format**. A separately authenticated controller must supply provenance before any real service integration.
- The diff is shown as inert text; even its complete state does not mean the proposed patch was tested or reviewed.

## Why a separate page

The earlier Explorer V1/V1.1/V1.2 uses an independent `toad-sage-explorer-fixture-v1` UI schema. Rather than silently changing those sample records into backend claims, this new page uses the distinct `sagecode-ui-fixture-v1` schema and an isolated adapter. Neither page creates HTTP endpoints. Agent A's actual contract and controller remain outside Agent B's ownership.

## Verification

On the new branch, from a trusted checkout:

    node --test tests/web/*.test.cjs
    node tests/browser/sagecode_contract.cjs
    npm run test:browser
    python -m unittest tests.test_free_studio_bundles -v
    python tools/build_free_studio_bundles.py --check-only

GitHub's required workflow runs the Node unit tests in the Python matrix (3.11 and 3.12) and real headless Mobile WebKit on the exact commit. WebKit tests use an iPhone 13 and an 834-pixel tablet viewport, keyboard navigation, focus, text-only source/diff display, SHA-256 mismatch rejection, truncated-read warnings, blocked cross-revision data and missing JSON. **This is not physical iPad Safari/VoiceOver testing**. The owner still needs manual physical-device accessibility acceptance.

The static Studio ZIP packaging has an explicit allowlist containing all five new contract inspector assets; the original reviewed templates and isolated previews remain unchanged. No automatic Netlify publication.

## Next contract questions for Agent A

1. What authenticated, read-only transport will serve `status()`, `list_tree()`, `read_file()` and `search()`? PR #46 currently defines internal Python APIs only.
2. How will a trusted controller bind all responses to the **same exact immutable source revision**, including paginated reads, and reject a stale response after HEAD changes?
3. What verified evidence protocol will justify future tested/approved labels? SageCode V1 explicitly reserves these transitions and has no test receipts.
4. How will project permissions be configured server-side (never from browser project IDs)? Who may request an approval and how is the human decision signed/recorded?

**Do not connect this page directly to a raw workspace, Python module or guessed fetch endpoint.** These require a separate cross-agent architecture review and a new PR.

## Engineering sources

- [Agent A's SageCode Tools V1 contract, PR #46](https://github.com/jimedusot-beep/Toadsagemode/blob/agent-a/sagecode-tools-v1-20261119/docs/SAGECODE_V1_CONTRACT.md) — the exact response fields, bounds and unverified semantics.
- [W3C WCAG Keyboard](https://www.w3.org/WAI/WCAG22/Understanding/keyboard) and [Focus Visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible) — keyboard navigation and focus.
- [MDN SubtleCrypto digest](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/digest) — browser SHA-256 availability and byte hashing.
- H.E.R.B.I.E. Master Knowledge Bank, Grace Hopper and Don Norman sections, pp. 9–10: modular contract interfaces, regression testing and understandable status/error feedback. Design analogies, not claims these people developed SageCode.
