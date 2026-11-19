# Free App Studio — build from Safari, no API credits

The owner can download two ready-to-upload static website artifacts directly
from GitHub Actions. The download files do not modify or deploy the existing
Toad Sage Tasks site, do not call paid AI providers, and contain no secrets.

## What is new

**Free App Studio** is a mobile, static website with a simple form:
choose **Flashcards**, **Tasks**, or **Notes**; enter a title and lowercase
slug; select a forest or midnight theme; download a standalone app ZIP.

The browser studio packages the exact reviewed templates stored in
`free-studio/templates.json`. The Python packaging test refuses a
template catalog if it differs in any byte from the existing App Studio's
reviewed template sources.

The browser ZIP generator uses a small, dependency-free ZIP (STORE) writer,
checks CRC32, and creates a `build_report.json` with per-file SHA-256 hashes.
No AI model or server is called, and no generated source is uploaded anywhere
until the owner explicitly uploads the resulting ZIP to Netlify Drop.

**This remains a deterministic template builder**, not a generative coding
agent, even though the interface accepts a short title and slug.

## iPad installation — two separate websites

1. Open GitHub's [Prepare free iPad app download ZIPs workflow](https://github.com/jimedusot-beep/Toadsagemode/actions/workflows/free-app-artifacts.yml).
2. Open the newest **successful** run of this branch.
3. Under **Artifacts**, download
   `Toad-Sage-Flashcards-iPad-ReadyToUpload`.
   GitHub supplies one ZIP containing `index.html`, `styles.css`,
   `app.js`, `README.md`, and `build_report.json` at its root.
4. Save the ZIP into iPad Files.
5. Open [Netlify Drop](https://app.netlify.com/drop/) in Safari,
   select **Choose file**, and select that ZIP. Netlify provides a
   *new separate* `netlify.app` URL. Do not select or redeploy
   the current Tasks site. The deployment is a manual action the
   owner authorizes.
6. Test creating, flipping, learning, deleting, and reloading cards.
   Only use disposable test data: browser localStorage isn't secure
   cross-device storage, and is not a backup.

To build *more* apps from your iPad, repeat the same process using
`Toad-Sage-FreeStudio-iPad-ReadyToUpload`.
After deploying its ZIP to a separate Netlify site, open Free App Studio,
choose an app type, enter the name/title/theme and download your new ZIP.
Upload the new app ZIP to Netlify Drop to obtain a third test URL.

**Important:** GitHub Action download artifacts are temporary and may
require signing in to GitHub. Their expiration is seven days. They are
not permanent public app URLs. GitHub's UI might wrap downloaded ZIPs
differently: inspect the unzipped contents before upload if the resulting
site does not load.

## Verification

- `tests/test_free_studio_bundles.py`: exact trusted catalog/source
  comparison, exported static file layout, validation of ZIP contents,
  non-deployment evidence and symlink rejection.
- `tests/browser/free_studio.cjs`: real mobile-sized WebKit
  end-to-end test that downloads Tasks, Notes and Flashcards ZIPs from
  the browser Studio, verifies file contents and ZIP CRC32, validates
  per-app unique storage keys, checks invalid form names and
  disconnected-template failure behavior.
- Existing flashcards, tasks and notes WebKit tests continue running.
- `free-app-artifacts.yml` uploads two separate root-level static ZIP
  archives; there is NO deploy step, Netlify token or API key.

## Remaining limits

This does not connect Toad Sage to a real code-writing model. Hosted
OpenAI inference stays off under the user's $0 budget decision.
No paid credits or server-side secrets are needed.

A future authenticated free cloud workspace might support actual model
inference with verified zero-cost quotas, but those quotas cannot be
assumed stable and must be checked before any integration.
The local Ollama option still requires a suitable host device.

The currently deployed Toad Sage Tasks app remains unchanged.
GitHub draft PRs still require owner review and branch protection
before any merge.

## Sources

- [Netlify Drop quickstart — accepts folders or ZIP files](https://docs.netlify.com/start/quickstarts/netlify-drop-quickstart/)
- [GitHub Actions artifact download](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)
