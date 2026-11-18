# Toad Sage Tasks — isolated Netlify preview

**This branch is a separate deployment staging source, not a finished deploy.**
It derives from the unmerged App Studio draft PR #24; its production safety and
browser acceptance are not yet certified.

## One-click deployment

[Deploy this standalone task app to Netlify](https://app.netlify.com/start/deploy?repository=https%3A%2F%2Fgithub.com%2Fjimedusot-beep%2FToadsagemode&branch=deploy%2Ftoad-sage-task-netlify-preview-20261118&create_from_path=netlify-preview)

The link uses Netlify's official public-repository **Deploy to Netlify**
flow with the `branch` and `create_from_path` parameters. It copies
**only `netlify-preview/`** from the staging branch into a separate
newly connected site/repository, rather than replacing `sage-toad-mode`
or `herbieprivate`. Netlify may ask you to log in, select a team, authorize
the GitHub connection and confirm the deployment. Review the selected plan,
credits, generated repository, and site name before approving.

You can also navigate manually using the Netlify dashboard's
**Add new project → Import from Git** workflow, but for this monorepo prefer
the button's `create_from_path` option to avoid publishing any runtime
source, tests or private data.

## What will be published

```text
index.html
styles.css
app.js
robots.txt
netlify.toml
```

These are a fixed, source-reviewed task app; `app.js` and `styles.css`
match the trusted App Studio templates byte for byte. The HTML only
substitutes the title `Toad Sage Tasks` and theme `forest`.

- Static-only: no build command, server function or paid API dependency.
- Browser-local tasks using localStorage. No sync and no account system.
- No connected AI model, Docker worker or hardware controller.
- Security response headers block remote connections and inline scripts.
- Netlify preview may be publicly reachable; **do not enter sensitive data**.
  The `robots.txt` exclusion discourages indexing but is not access
  protection. If privacy is required, configure appropriate Netlify
  visitor-access controls in the new site before sharing its URL.

## Acceptance after clicking Deploy

1. Wait until the new site's deployment state is **Ready** in Netlify.
2. Open the exact `https://<new-site>.netlify.app/` shown in that site,
   not an assumed URL and not the existing `sage-toad-mode` homepage.
3. Add a test task, mark complete, filter, reload (task persists), delete.
4. Use an obvious plain-text HTML-like task to check it's displayed as text.
5. Confirm no browser console exceptions or missing CSS/JS in the site.
6. Record the deploy ID, URL, branch/repo, test evidence and owner approval.
7. If deployment fails, do **not** claim it is running; fix the configuration
   and redeploy. Do not overwrite an existing live site to bypass setup.

## Why the operator click remains necessary

The connected Netlify tools can inspect and create *empty* projects, but do
not expose a deploy/publish operation or attach a Git repository. Creating an
empty project through ChatGPT would **not** publish this app. The Netlify
button enables the necessary Git authorization in the user's browser.

`netlify.toml` lives inside `netlify-preview` on purpose because
`create_from_path` copies that directory as the new repo root. No
`[template]` config is used: Netlify template config would need to reside
in the original repository root, not the cloned subfolder.

This staging branch should **not be merged into the existing Toad Sage
`main` site** until downstream deployments have been reviewed separately.

References:
- [Netlify — Create deploys](https://docs.netlify.com/deploy/create-deploys/)
- [Netlify — Deploy to Netlify buttons](https://docs.netlify.com/deploy/create-deploys/#deploy-to-netlify-button)
- [Netlify — Security and access](https://docs.netlify.com/manage/security/)
