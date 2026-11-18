# Toad Sage App Studio — first working app checkpoint

Status: **trusted template-backed web application**, not autonomous AI coding.

## What is genuinely built

`python -m toad_core app create NAME --title "My Tasks"` creates a complete,
responsive, dependency-free **offline task manager** with:

- Add a task, mark it completed or active, delete it, and clear completed tasks.
- All/Active/Completed filters, accessible labels and keyboard input.
- Browser-local persistence (localStorage), with explicit failure warnings and
  preservation of unreadable saved data.
- No analytics, login, external scripts, remote API, paid service or network.
- HTML, CSS, JavaScript, a README, a source-hash report and a portable ZIP.

The CSS has two vetted themes: `forest` and `midnight`.
The user's title is inserted with HTML escaping. Task text always uses
`textContent`; it is never inserted as executable HTML.

All source templates are maintained in
[`toad_core/studio_templates`](../toad_core/studio_templates). A normal
Python package installation must include these templates via
`pyproject.toml`. The app generator performs **no** LLM calls, Docker
operations, downloaded code execution, Git commits or deployments.
It is a practical deterministic first build system, not yet an AI
that invents arbitrary applications.

## Create a reviewable app

On a trusted checkout with Python 3.11+:

```sh
python -m toad_core app create daily-tasks --title "Daily Tasks" --theme forest
python -m toad_core app inspect daily-tasks
```

Default private output: `~/.local/share/toad-sage/app-previews/daily-tasks/`
on Linux; the actual path is returned by the command and follows the
configured Toad Sage workspace. On Windows, the root follows the existing
`TOAD_WORKSPACE` / `%LOCALAPPDATA%` convention.

Files:

```txt
app-previews/daily-tasks/
  index.html          browser page
  styles.css          responsive design
  app.js              task CRUD, filters, local persistence
  README.md           usage and privacy
  build_report.json   source SHA-256 and explicit unverified status
  app.zip             portable review-only source package
```

**No files are overwritten.** To create a new snapshot, choose a new
lowercase name. The `inspect` operation compares source hashes without
executing JavaScript. Edited or missing source files are reported
`source_modified`, and do not become `verified` automatically.

For local testing with browser persistence, serve the generated directory
through a **loopback-only** static server, then open its localhost URL
on that same machine. Do not expose the private workspace externally.
`index.html` may open as a local file, but some browsers restrict
`localStorage` on `file://` pages.

## What CI proves, and what it doesn't

- Python unit tests exercise name/title validation, HTML escaping,
  exclusive output creation, archive content/digests and tamper detection.
- GitHub's Mobile WebKit job uses the **real browser** on a locally
  generated copy of this fixed trusted template. It checks task
  creation, persistence, completion, filtering, deletion, clearing,
  XSS resistance, unreadable storage and storage-quota failures.
- GitHub CI **does not** execute arbitrary candidate JavaScript,
  prove a live Ollama model can generate an application, install a
  reusable ability or deploy the app.
- App Studio output is `generated_unverified`. Template tests verify
  the trusted implementation; a specific owner's generated build has
  not been individually acceptance-tested on their phone or lab.
- Generated applications are separate from the mission engine's
  `Python-only` sandbox, cannot bypass it and carry no elevated grants.

## Next engineering steps

1. Owner reviews this PR's source, browser evidence and output contract.
2. Finish [main branch protection](https://github.com/jimedusot-beep/Toadsagemode/issues/9).
3. Prove real restricted Docker / Ollama calculator repair
   ([issue #11](https://github.com/jimedusot-beep/Toadsagemode/issues/11)).
4. Design an independently restricted **JavaScript execution lab** before
   supporting model-produced web apps as verified; avoid running arbitrary
   submitted JS in GitHub Actions or the current Python-only worker.
5. Add a bounded model-generated *app specification* and rubric (not
   arbitrary shell access) to choose/revise reviewed app templates.
6. Add separate build, browser, owner-review and release stages with
   explicit evidence. Never silently publish a generated application.

This deliberately follows Margaret Hamilton's explicit fault state and
Grace Hopper's testable boundary mindset: distinguish generated source,
CI-tested template, validated build, owner-approved candidate and release.
