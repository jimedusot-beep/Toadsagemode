# SageCode Contract Inspector V1 — Agent B frontend handoff

**Status:** Draft, static, read-only, fixture-only. No SageCode HTTP service, live model generation, permission grant, external file access, code execution, Git merge, deployment, or real approval.

## What this adds

The existing Project Explorer links to `free-studio/sagecode-contract.html`, a separate iPad-friendly inspection page backed by `free-studio/sagecode-contract-fixture.json`. This is a **sample**, not a real `SageProjectTools` response.

The page displays the response shapes from Agent A's separate [SageCode Tools V1 PR #46](https://github.com/jimedusot-beep/Toadsagemode/pull/46): project status, manifest-derived directories and file entries, bounded source readers, filename/content search hits, and a pending proposed unified diff. All source and diffs use `textContent`. The page has **no apply, approve, edit, execute, deploy, checkout or host-access functionality**.

Every source remains explicitly marked **fixture**. Even a passing local SHA-256 check is described as `sample text consistency`, never as authenticated source, tested code or safe execution.

## Agent B usability review — November 20, 2026

This review audits the stacked draft dependencies **#45 → #47 → #48 → #50** without editing their branches.

**Defects found and fixed in a new stacked draft:**

- Explorer project selection rebuilt the project list and could discard the active keyboard control. The newly selected project button now receives focus after rerendering.
- Editing the search input left old clickable results visible. Results now clear immediately when the query changes; new results require running Search again.
- The Explorer's local JSON fixture import could finish **after** the owner reset to the built-in fixtures, overwriting that reset. Each fixture load/import now tracks a monotonic in-page generation and rejects outdated async completions. A late import read error cannot overwrite the newer reset status. No persistent storage is used.
- The Explorer's fixture `verified` sample used a green visual accent. The sample badge is now amber, with an adjacent explicit `SIMULATED ... NO independent verification evidence` explanation. Failed/testing/blocked examples also explain their lack of real test evidence. Demo approvals remain page-memory only and never modify production.
- Inspector incorrectly treated a later-page `read_file` response with `truncated:false` as a complete file, or rejected the shape. Backend `truncated:false` means **no more data after that read**, not necessarily that earlier lines were read. A `start_line > 1` view is always marked partial and **never** treated as whole-file hash checked.
- Inspector search hits outside a loaded excerpt could look like successful line navigation. It now announces that the matching line is **outside the visible excerpt** and that there is no page-fetch endpoint.
- Inspector accepted an empty diff with `unchanged:false`, producing a misleading "Complete example diff" claim. Such fixture data now fails validation.
- Inspector sections now offer keyboard-visible, 48-pixel touch targets for *current sample source*, *sample search* and *proposed revision diff*. These are **section anchors**, not an invented revision history, project switcher, editor or restore API.
- Empty Inspector projects now show an explicit no-files message. Keyboard focus and long paths have dedicated mobile regression coverage.

**Audited but not implemented (no justified backend authority):** Inspector has one static example project, so there is no real project switcher; revision IDs are labels tied to samples, not a fetchable history; no live source pages, test jobs, actual approval, restore or deployment endpoint exists. The Explorer's restore button **only reloads built-in fixtures**, not a saved real project revision. A truncated unified diff remains read-only, labeled incomplete and not suitable for production approval.

**Regression proof required:** Node contract tests and real automated WebKit on phone (including 320 px) and 834 px tablet must pass with corrupt/invalid fixtures, partial source, stale search, import/reset races, empty projects, long filenames, touch target minimums, absent storage and repeated navigation. Automated WebKit is not physical iPad Safari or VoiceOver testing. Screenshots are not supplied unless captured as actual browser artifacts; workflow logs are the current evidence.

## Trust and provenance checks

- `free-studio/sagecode-contract-adapter.js` validates the exact example fields, project IDs, 64-character lowercase revision and file digests, revision matching across status/tree/reads/search, bounded declared source paths, file counts, byte lengths, 16-kB source views, line numbering, bounded search results, proposal ancestry and 30-kB diff text.
- SageCode V1 status must remain `verification: "unverified"`, `review_status: "pending_review"`, `executed: false`, `approved: false`, `release_allowed: false` and `test_evidence: null`. Attempts to inject green verified/approved outcomes are rejected before rendering.
- Complete sample source views must match manifest byte lengths and the SHA-256 digests recomputed using browser `crypto.subtle.digest('SHA-256', ...)`. A mismatch blocks the entire inspector.
- **Partial/truncated source cannot prove a whole-file digest.** Either `truncated:true` **or** `start_line>1` marks the view partial, even when `truncated:false`. It stays readable only as a flagged partial view and does not display a green verified status or pretend more source can be fetched.
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
