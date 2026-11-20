# Sage Studio Project Explorer V1 — fixture-only frontend

**Release state:** reviewable draft. No backend integration, model call, generated-code execution, Docker validation of AI candidates, or deployment.

This page extends the existing Free App Studio **without replacing its builder**. From the Studio homepage, select **Open Project Explorer demo**. Browse five local example projects, explore nested source files, compare before/after changes and read plainly labeled simulated test output. Approve or reject a mock revision using an explicit browser confirmation. A decision affects **only the current page's memory** and does not edit source, create a commit, run code or update a server.

The optional **Inspect selected fixture JSON** control allows the owner to import another local example-data JSON file (maximum 100 KB) after strict UTF-8 and schema validation and an explicit confirmation. A rejected, corrupt, invalid or oversized file never replaces the currently displayed catalog. **Restore built-in examples** recovers the original fixtures. Neither action imports or writes a production project.

The verified and testing examples are **sample labels only**, not evidence. Every status badge says **Fixture** and **sample only**. Source uses DOM textContent, never executable HTML, iframe or eval. The existing separate sandboxed reviewed-template previews remain unchanged.

## Explorer V1.2 — local fixture source search

A searchable source panel offers a **user-submitted, bounded** filename/content term with keyboard Enter or a touch-friendly Search button. Results are inert text-only buttons that navigate to the corresponding source file, moving focus to its read-only source viewer and scrolling toward a one-based matching line.

This **fixture-only** search intentionally mirrors the *shape* of Agent A's [draft SageCode Tools V1 backend-to-Studio contract](https://github.com/jimedusot-beep/Toadsagemode/blob/agent-a/sagecode-tools-v1-20261119/docs/SAGECODE_V1_CONTRACT.md) (PR #46): `project_id`, `term`, `matches` with `path`, `line`, `snippet`, `kind`, and a `limited` flag. Filename matches have line 0; content matches use one-based lines. Default limit is 50 and 100 maximum, and the UI always says when it has reached the limit.

**Critical differences from the backend:** The fixture adapter adds `source: "local-fixture-only"`, sets `revision: null` (not a fabricated revision hash), searches only already-validated fixture text in page memory, and compares case with JavaScript lowercase (not full Python Unicode casefold). It does **not** issue an API request, authorize project access, index the host filesystem, or establish exhaustive search. Search results are cleared on project changes, successful fixture import, reset or failed built-in fixture loading to prevent stale navigation. A bounded result only means the first 50 matches were displayed; there may be more.

The Agent A contract is an **unmerged draft Python interface**; no real HTTP endpoint exists to connect to. Actual revision IDs, authorization, immutable file hashes, chunked 16-kB reads and any test receipts require a separately reviewed server-side integration.

## Agent A interface boundary

The planned Agent A document docs/SAGECODE_V1_CONTRACT.md was not available on the parent branch at the time of this work. No live service endpoint or API schema is invented here.

- free-studio/explorer-adapter.js defines a separate fixture-only schema: toad-sage-explorer-fixture-v1.
- validateCatalog(raw) checks exact fields, sizes, states, relative paths, unique files, matching revision before-source and supported metadata.
- loadFixtures(fetcher) reads only the static same-origin ./explorer-fixtures.json path.
- free-studio/explorer.js consumes the validated structure and never accesses localStorage, a model, GitHub, terminal, deployment or credentials.
- Agent A should separately define a real authenticated **read-only** project/files/test contract with evidence provenance and release authority boundaries. A future adapter must distinguish independently verified receipts from illustrative fixtures and **must not promote demo approval to production approval**.

Fixture structure: top-level schema and projects (0–20); each project has id, title, summary, state, files, revision, test. File contains relative path and bounded text content. Revision may be null or includes id, path, before, after, status, test. Each test includes status and output. States are draft, untested, testing, failed, verified, blocked. Reject unknown fields, traversal, mismatched source, duplicates and oversized content.

## Verification

From a trusted checkout of this branch:

    node --test tests/web/*.test.cjs
    node tests/browser/explorer.cjs
    npm run test:browser
    python -m unittest tests.test_free_studio_bundles -v
    python tools/build_free_studio_bundles.py --output /tmp/toad-explorer-build

The automated WebKit test covers iPhone 13 and 834 px tablet viewports, keyboard file navigation, focus styles, responsive overflow, source safety, approval confirmation/cancellation, rejection, empty project, testing/failed/verified sample labels, failed fixture load, invalid JSON/data and local fixture imports, searched file/line navigation and capped result warnings, unavailable storage, long filenames, independent diff hunks and complete large-file fallback, and large malicious-looking source. **Automated WebKit is not physical Safari/iPad testing.** The owner must still test real iPad Safari and VoiceOver, large text, touch targets and browser dialogs.

The existing bundle builder packages the five new Explorer assets together with the unchanged Free Studio templates and six reviewed iframe previews; the original ZIP verification and digest checks remain.

## Limits

- No real project persistence, provider connection, terminal or live code generation.
- Demo approvals are neither production approvals nor release authorizations.
- Explorer V1.1 identifies multiple independent changed blocks using a bounded line-level longest-common-subsequence comparison. Unchanged lines between edits remain unchanged in the display. It reports exact additions/removals and change-group totals **only when exact matching completed**. The algorithm does not claim word-level or full Git diff parity.
- If the changed middle region exceeds 160,000 comparison cells, the adapter switches to a clearly labeled **coarse** changed-block comparison (no false exact-count claim). For more than 600 displayed diff rows, the UI shows **complete original and proposed source as plain text** instead of rendering thousands of highlighted spans; it never silently truncates code.
- The source diff and all evidence still come only from fixture data and cannot authorize a real revision.
- Explorer works when localStorage is denied because it never reads or writes it. This does not change the separate saved-settings feature.
- Invalid or missing fixture data clears the view and enables Retry, without using previously displayed data.
- Never use this page to execute AI-authored code. The existing reviewed-template sandbox boundary belongs to the separate interactive preview page.

## References and design reasoning

- Reuses existing free-studio/styles.css and v2.css, avoiding a competing design system.
- H.E.R.B.I.E. Master Knowledge Bank (12 October 2026), Grace Hopper pp. 9–10: documented abstractions and regression tests; Don Norman p. 10: feedback, predictable controls and recovery.
- W3C keyboard: https://www.w3.org/WAI/WCAG22/Understanding/keyboard
- W3C focus: https://www.w3.org/WAI/WCAG22/Understanding/focus-visible
- MDN status live region: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/status_role
- OpenCode tools provide workflow inspiration, not code or a runtime dependency: https://opencode.ai/docs/tools/
