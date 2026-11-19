# Toad Sage Free Studio V3 — isolated interactive previews

V3 adds a **real, interactive, browser-based preview** of each of the
three **reviewed** app templates. It is an enhancement to the separate
[visual-only layout preview and saved projects](FREE_STUDIO_V2.md).

## What runs

- The actual reviewed Tasks, Notes or Flashcards application logic,
  with clickable forms, filters, navigation and learned-progress states.
- One of six fixed prebuilt preview pages: three kinds × two themes.
- The page title shown in the frame updates from the owner's Studio
  title field as plain text.
- **Reset preview data** reloads the frame and discards its demo data.
- Saved Studio project settings (kind/name/title/theme) are independent
  of the interactive preview. They still persist only in the owner
  browser's localStorage.

The previews are compiled with `AppStudio._templates()` using the same
source files from which standalone app ZIPs are made. The generator
replaces only the reviewed app's storage status text, embeds the
previously reviewed CSS and JavaScript, and prepends a tiny auditable
**temporary in-memory localStorage shim**. This shim is isolated inside
the iframe script; it **does not write actual browser storage**.

## Security boundary

The parent Studio owns an iframe with:
- `sandbox="allow-scripts"` and **without** `allow-same-origin`
- a fixed `previews/{tasks|notes|flashcards}-{forest|midnight}/index.html`
  route. User titles/slugs can **never** become a URL or source path.
- `referrerpolicy="no-referrer"`
- a limited `postMessage` consisting **only** of a bounded visible
  title; no API keys, tokens, file contents or owner project state
- a child CSP allowing only embedded reviewed scripts/styles, with
  `connect-src 'none'`, `img-src 'none'`, `frame-src 'none'`,
  `form-action 'none'`, `object-src 'none'` and `base-uri 'none'`.

The sandbox has an **opaque origin**. Therefore, the child cannot read
the parent DOM, parent localStorage or cookies. Its own
`window.localStorage` access is denied by the browser. The small
temporary in-memory storage adapter is provided in the same trusted
JavaScript scope as the reviewed application.

The parent and embedded app only exchange a plain, bounded title.
No source code, HTML, URL, credentials, application state or user
secrets are communicated over this channel.

**This security model is specific to the reviewed template sources.**
It is **not a general sandbox for AI-generated or third-party code**;
sandboxed iframes alone do not impose CPU, memory or execution-time
quotas on malicious candidate code. Untrusted model-generated
applications remain quarantined and require the separately proposed
Docker WebKit worker, independent frozen tests, resource bounds and
explicit authorization before **any** execution. Do not reuse this
preview pathway to run untrusted applications.

## Actual app downloads

The separate `Prepare ZIP → Download prepared ZIP` flow still
packages the original standalone apps (not the preview's temporary
adapter). When deployed manually, generated apps use their own
per-app browser localStorage key and may preserve data on the same
device. They are not synced or securely backed up.

No Netlify deployment, paid model request or merge happens in V3.
Owner approval and actual device testing remain prerequisites for a
published release.

## Packaging

`tools/build_interactive_previews.py` generates exactly six
self-contained preview HTML pages from the reviewed templates, with
strict source anchors. Any mismatch in expected CSP, stylesheet
references, script references or data status causes a build failure.

`tools/build_free_studio_bundles.py` packages six preview pages
alongside the Free Studio main files into the same **separate**
GitHub Action artifact
`Toad-Sage-FreeStudio-iPad-ReadyToUpload`. This ZIP is designed for
manual upload to a **new Netlify Drop site**. The existing Tasks
website is left unchanged.

## Automated acceptance

- `tests/test_studio_v3_previews.py`: allowed kinds/themes, exact
  reviewed-source inclusion, inline CSP, volatile shim, SHA-256
  preview manifests and no unreviewed types.
- `tests/web/studio_v3.test.cjs`: strict iframe route allowlist and
  bounded, plain-text-only title messages.
- `tests/browser/studio_v3.cjs`: runs actual buttons on the reviewed
  three apps in iPhone-sized WebKit; verifies iframe DOM cannot be
  read from the parent, child permanent localStorage is denied,
  reset clears temporary data, theme/title updates, project saving
  stays independent, and no third-party network requests occur.

V3 follows the knowledge bank's historical examples of predictable
failure handling (Margaret Hamilton), repeatable tests (Grace Hopper)
and clearly labeled UI states (Don Norman). These are engineering
principles—not claims that those individuals endorsed this design.
