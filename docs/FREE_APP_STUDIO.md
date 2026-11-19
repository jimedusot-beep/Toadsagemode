# Zero-cost App Studio — offline tasks, notes and flashcards

Toad Sage can now build **three distinct functional mobile web apps**
without any paid AI model, API key, tokens or provider calls:

| Reviewed app | Actually implemented |
| --- | --- |
| Tasks | Create, complete/uncomplete, filter, delete, clear completed |
| Notes | Create, edit, search, delete |
| Flashcards | Create, edit, search, delete, flip, next/previous, mark learned, progress |

All three use the same reviewed HTML/CSS/JavaScript design system,
can run on an offline-capable static host, and use browser-local
`localStorage` with distinct per-app keys. This is **a deterministic
builder, not an AI coding agent**. No server, live model, authentication,
sync, AI inference, clinical/child records or hardware control is added.

## Short example (on any trusted Python 3.11+ host)

```sh
# Build a genuine mobile-friendly flashcard study app from a short brief:
python -m toad_core app free-build "Make an offline flashcard app for vocabulary" \
  --name vocabulary-cards --title "Vocabulary Cards" --theme forest

# Also supports:
python -m toad_core app free-build "Make a study notes app" \
  --name study-notes --title "Study Notes"
python -m toad_core app free-build "Make a checklist of daily tasks" \
  --name daily-checklist --title "Daily Checklist"

# Review the SHA-256 source hashes before any preview or deployment:
python -m toad_core app inspect vocabulary-cards
```

Output is written to a fresh `app-previews/<name>/` with
`index.html`, `styles.css`, `app.js`, `README.md`,
`build_report.json` and a reviewable `app.zip`. Existing app names
cannot be overwritten. **Creating a source ZIP is not testing that
specific output or publishing it to Netlify.**

### An honest natural-language interpreter

The `free-build` command is a transparent keyword/constraint router.
It recognizes explicit requests for **tasks, notes, or flashcards**. It
rejects requests for ambiguous multi-app scope or features not currently
implemented such as login, cloud sync, third-party APIs, payments,
uploaded media, PDF export, or spaced repetition. It does not infer
requirements, write custom code with an LLM, or claim that a visually
similar app fully satisfies the prompt.

The model-backed workflow in PRs #26–#30 remains optional and
inactive: local Ollama is the default for explicit model calls,
and paid cloud inference requires separately configured host settings
and `TOAD_ALLOW_PAID_AI=YES`. **No API credentials or credits are needed
for `app free-build`.**

### Flashcard acceptance behaviors

- Mobile accessible keyboard/touch controls: flip the card, move
  previous/next with wraparound navigation, mark/unmark learned.
- Creating, editing, searching and deleting cards.
- Progress display for learned cards and persistence after browser reload.
- Every user-entered question/answer renders as **text**, not HTML.
- Corrupt/unsupported localStorage is not silently overwritten.
  Unavailable or full storage is reported accurately; changes remain
  visible in that browser session only.
- At most 120 cards, with 160-character front and 1,200-character back.
- No network requests, external libraries, cookies, tracking or API keys.
- Separate storage key per generated slug; does not migrate or disturb
  the previously deployed `Toad Sage Tasks` site's storage.

## Verification and gates

- `tests/test_free_builder.py` covers explicit selection, refusals,
  CLI build, independent storage and source-integrity reporting.
- `tests/browser/app_flashcards.cjs` runs in trusted, iPhone-sized
  WebKit and exercises flip/navigate/progress/CRUD/search/reload, HTML
  injection-as-text, missing/invalid storage and quota failure.
- All these browser runs execute **reviewed template code only**.
  They do not run the model-written quarantined code described in
  [WEBKIT_LAB.md](WEBKIT_LAB.md).
- Tests run automatically in the [required GitHub validation workflow](../.github/workflows/validate.yml).
  No GitHub Action deploys this PR to Netlify.

## What to do next for actual AI app building at $0

Use ChatGPT + connected GitHub as an interactive development workflow
to author and review new app templates or improve Toad Sage. That
is still AI-assisted human-supervised software engineering, not
Toad Sage autonomously calling a model.

A future local self-hosted, free-to-run model could enable true
on-device generation, but that still requires a computer or other
host capable of running it. There is no verified always-on hosted
free model or current iPhone backend for this project.

Never paste an API key into ChatGPT or source control. Previously
exposed keys must be revoked even if no billing credit remains.
