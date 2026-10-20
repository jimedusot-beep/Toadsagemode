# Dashboard and deployment

`index.html`, `web/catalog.js`, `web/ability-library.js` and `web/styles.css` form a dependency-free static inbox. Feeds are saved only to the current browser, and portable backups connect it to the Python engine.

The Pages workflow builds an explicit static allowlist and deploys only after validation succeeds on main. Feature-branch changes do not alter the existing live deployment. See the pull request/commit for deployment state; a local browser test is not proof that production has updated.

A physical iPhone retest is still needed after deployment: paste ordinary content, Feed Toad, read the local-save confirmation, reload, verify persistence, then export a backup. If scripts fail to load the static startup message remains visible and Feed Toad stays disabled. Storage corruption opens recovery controls automatically.

The phone draft/recovery and multi-tab behavior is documented in [PHONE.md](docs/PHONE.md). Drafts are tab-local session data, separate from persistent inbox entries and library backups. Attachment contents are not cached in drafts.
