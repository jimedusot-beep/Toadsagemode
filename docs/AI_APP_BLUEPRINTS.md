# AI app blueprints — controlled application generation (V1)

**Scope:** a locally configured coding model proposes a structured app design;
the protected core validates it; a human reviews and approves; trusted templates
render an app source bundle. This is a meaningful first step toward AI-assisted
building, but **not** arbitrary autonomous React/JavaScript coding.

The base App Studio is documented in [APP_STUDIO.md](APP_STUDIO.md). This branch
adds a second independent functional template (**notes**) alongside **tasks**.

## What AI can and cannot do today

The existing [Ollama adapter](../toad_core/models.py) accepts only a local
loopback endpoint. When actually installed and running, that model may choose
these fields in a JSON blueprint:

| Field | Example | Rule |
| --- | --- | --- |
| `schema` | `toad-app-blueprint-v1` | exact literal |
| `name` | `study-journal` | lowercase 2–40-character slug |
| `title` | `Study Journal` | at most 80 characters |
| `kind` | `notes` | exactly `tasks` or `notes` |
| `theme` | `midnight` | exactly `forest` or `midnight` |
| `summary` | `Local searchable study notes` | short description |
| `unmet_requirements` | `["Cloud sync is not supported"]` | max five declared gaps |

Any additional field, such as JavaScript, commands, third-party libraries,
network permissions or custom API endpoints, **invalidates the entire proposal**.
The AI does **not** write executable HTML/CSS/JS in this release. It chooses
and describes the fixed implementation. Always inspect gaps; models can
misclassify goals or omit important requirements.

**Supported apps today:**
- **Tasks**: add/toggle, active/completed filters, individual deletion,
  clear completed, local storage.
- **Notes**: add, edit, search, delete, local storage. The new notes editor
  intentionally supports plain text only; it does not render arbitrary HTML.
- Both have two themes, unique per-app browser storage keys, no dependencies,
  no backends, and source-only ZIP outputs. A locally rendered app has not
  automatically been tested on the owner's device.

**Unsupported:** arbitrary apps/games, cloud sync, user accounts, external
APIs, live AI in the generated website, backend servers, file uploads, email,
hardware control, scraping, and auto-deployment. A goal requiring these should
report `unmet_requirements` and remain under human review.

## Three-step operator workflow

On a **trusted Python 3.11+ computer** with this branch and a preinstalled
**local** Ollama model configured as described in [MISSIONS.md](MISSIONS.md):

```sh
# Step 1 — ONE bounded model call: proposal only, not a build
python -m toad_core app propose "Build a private study notebook with search"

# Copy the returned ID and examine the full untrusted proposal.
python -m toad_core app plan PLAN_ID

# Step 2 — After human review, approve a trusted template build.
python -m toad_core app build PLAN_ID --approve

# If the plan has gaps, the command refuses the build by default.
# Add --allow-partial only after accepting exactly those missing features.
python -m toad_core app build PLAN_ID --approve --allow-partial

# Step 3 — inspect actual produced source, SHA-256 hashes and ZIP.
python -m toad_core app inspect APP_SLUG
```

`app propose` creates a private plan in the Toad workspace's `app-plans/`
folder with explicit `awaiting_review` status. `app build` does not merge
Git changes or deploy; it writes a source ZIP in `app-previews/APP_SLUG/`.
The plan ID is unique, source content is digest-protected, and it refuses
an existing output directory to avoid overwriting owner work. The owner
approval here **only authorizes building a local review bundle**. Separate
testing and release decisions are still mandatory.

No Ollama endpoint or model is provisioned by this feature. On an iPhone
accessing the Netlify task app, there is **no connection to the local model
or these Python commands**. This is a repository capability, not yet a
phone-hosted AI service.

## Offline deterministic usage (works with no AI)

```sh
python -m toad_core app create school-tasks --title "School Tasks" --kind tasks
python -m toad_core app create lecture-notes --title "Lecture Notes" --kind notes --theme midnight
python -m toad_core app inspect lecture-notes
```

Each new app has its own browser storage key, based on its validated slug.
This keeps one generated app's notes and tasks from overwriting another's
when hosted on the same web origin. It also means previously saved data
under the original template's old key will not automatically migrate;
the already deployed `Toad Sage Tasks` site is **not modified** by this PR.

## Verification and security evidence

- Python unit tests use **explicit simulated model responses** to test
  the proposal path, schema rejection, plan tampering, refusal without
  approval, optional partial scope acceptance and idempotent overwrite refusal.
- Browser CI uses real iPhone-sized WebKit to test *reviewed static source*
  for both tasks and notes; the model never gets to submit or execute JS
  inside GitHub Actions.
- Model hallucinations, target machine performance and genuine model
  generation quality **are not verified**.
- The Python-only Docker candidate worker is unchanged. This app builder
  has no permission to run imported code and is not a replacement for the
  restricted browser execution worker we would need before allowing
  unconstrained AI-written code.
- Netlify remains a **static app host** for current deployments. Netlify
  alone does not create an always-on local Ollama or Docker agent. An
  authenticated remote backend would require a separate reviewed design,
  secrets management, and possible additional costs.

### Next milestone after review

Prove one real `app propose` request with an actual configured model,
review the output, approve one notes build, test the exact bundle on a
mobile browser, and publish through a separate owner-approved Netlify
workflow. Only then expand to extra app templates and test coverage.

This design uses explicit subsystem boundaries and measurable acceptance
evidence rather than assuming generated code is trustworthy.

## Sources

- [Toad Sage's model adapter](../toad_core/models.py)
- [GitHub repo's restricted lab](LAB.md)
- [Netlify deploy documentation](https://docs.netlify.com/deploy/create-deploys/)
- [Ollama structured JSON generation API](https://docs.ollama.com/api/generate)
