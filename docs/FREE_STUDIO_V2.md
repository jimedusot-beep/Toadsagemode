# Toad Sage Free App Studio V2 — visual preview and local projects

Version 2 extends the [zero-cost, template-based App Studio](FREE_STUDIO_IPAD.md)
without any OpenAI API key, credits, model inference, or paid hosting.

## Features built

### Live **design** preview
The form shows a real-time **visual example** of the chosen app kind,
title and theme, with a phone/tablet width toggle. It reacts as the
user types and changes options and it safely treats the title as plain
text, not executable HTML.

**Important distinction:** The preview is **not a running execution of
the generated app**. It contains example text and a limited
representation of the reviewed template design; no candidate source
code executes and no app data is read or written by the preview.
Actual interactions, storage and browser persistence must be tested in
the standalone generated app, as the existing WebKit tests do.

### Browser-local project memory
Click **Save current project** to store these settings only:
- app slug, title, kind and theme
- last saved timestamp

Users can load a saved project to repopulate the build form and preview,
update it using the same slug, or delete it using a two-step
confirmation. The library is capped at 20 projects and 12,000 JSON
characters. The app refuses ambiguous re-use of a slug for a
*different* app type.

Projects are stored in Safari's `localStorage` under a dedicated
`toad-sage-free-studio-projects-v1` key. This is **not** cloud sync,
secure backup or cross-device memory. Browser storage may be cleared.
No passwords, credentials, model inputs, app source, or app content
are included.

Malformed or unreadable saved data is not overwritten: project-saving
controls are disabled, but the visual preview and source ZIP creator
remain available. If storage writes fail (e.g. quota full), the
existing library is preserved and the user sees a clear error.

### Building and downloading
The existing **Prepare ZIP → Download prepared ZIP** flow is unchanged.
It still downloads a complete functional offline Tasks, Notes or
Flashcards app based on the exact reviewed sources with per-file
SHA-256 integrity hashes. These are deterministic app templates, not
AI-written arbitrary applications. App ZIPs remain separate from
saved Studio project settings.

The GitHub Actions packaging job still generates two separate test
artifacts:
- `Toad-Sage-Flashcards-iPad-ReadyToUpload`
- `Toad-Sage-FreeStudio-iPad-ReadyToUpload` (now includes `v2.js`
  and `v2.css`)

No deployment or repository merge happens automatically. The owner
can upload the Studio package to a **new separate** Netlify Drop site
without touching the existing Tasks demo.

## Verification

- `tests/web/studio_v2.test.cjs`: project whitelist, strict length
  and schema validation, conflict refusal, update, corruption safety,
  capacity and no secret/source storage.
- `tests/browser/studio_v2.cjs`: real iPhone-sized WebKit testing:
  title/XSS text handling, live theme/type/tablet design updates,
  save/reload/load/deletion, kind collision, malformed storage,
  denied local storage and quota failures.
- Existing download tests still verify actual ZIPs for all three
  types; no remote resources allowed in the test server.
- `tests/test_free_studio_bundles.py` verifies the entire package
  and that the Studio ZIP contains all required V2 assets.
- CI terminal merge gate requires both Python and WebKit jobs to pass.

## Remaining work

True interactive execution in a **separate, verified isolated preview
origin**, arbitrary model-written apps, a validated free inference
host, automatic repair and owner-approved release remain future
milestones. Do not treat the design preview as source execution.

Guiding implementation practices reflect the project knowledge
bank's emphasis on Margaret Hamilton's resilient state management,
Grace Hopper's repeatable debugging/testing and Don Norman's
clear, predictable interfaces. These are design principles, not
claims of direct historical endorsement.
