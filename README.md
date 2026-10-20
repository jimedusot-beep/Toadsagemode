# Toad Sage Mode

A local-first absorption inbox and Python development engine. Save ideas or source, inspect them without execution, and organize reusable candidates. Optional Ollama and a separately restricted Docker worker provide bounded Python project missions. The protected core is never rewritten by imported abilities.

[Open the iPhone dashboard](https://jimedusot-beep.github.io/Toadsagemode/) · [Audit](docs/audit/2026-10-20-baseline.md) · [Lab security and setup](docs/LAB.md) · [Models and missions](docs/MISSIONS.md)

## Feed Toad on iPhone

1. Open the dashboard in ordinary Safari.
2. Paste an idea, code block, source, or error log.
3. Press **Feed Toad**. The confirmation must say it was saved locally.
4. Find it in the inbox below; expand its inspection/files, edit its name, search, archive or delete it.

Optional text/source uploads are available under “Add a name, description, source, or files.” Names are automatic. Export a backup regularly, and keep it outside Safari. Backup import **merges** unique entries; it never replaces the inbox. Storage/quota failures retain your input and show an error. Unreadable data can be downloaded raw before resetting. Private browsing is unsuitable for durable storage, even when a browser permits saving in that session.

The site never uploads feeds to GitHub, executes pasted code, connects to your computer, or requests a model API key. Source previews use text rendering. Avoid entering secrets and avoid shared-device storage. GitHub Pages still serves the public application assets; feeds stay in your browser. There is no service worker; versioned script URLs reduce stale-asset confusion. A real iPhone retest remains necessary after deployment.

## Run the local engine without a model

Requires Python **3.11+**. No runtime pip dependencies. From this repository's checkout:

```sh
python -m toad_core doctor
python -m toad_core status
python -m toad_core ingest examples/hello.json
python -m toad_core ingest toad-library.json
python -m toad_core library list
python -m toad_core library list --search sensor --language Python
python -m toad_core inspect CANDIDATE_ID
python -m toad_core library show CANDIDATE_ID
python -m toad_core export --output toad-backup.json
```

Use `python -m toad_core doctor` for an offline catalog/setup report, or `python -m toad_core doctor --probe` to also check local Docker and Ollama metadata. [Readiness guide](docs/READINESS.md) explains the results and exit codes. Dependency availability is separate from successful containment and mission tests.

Replace `CANDIDATE_ID` with an ID printed by ingestion or listing. A path of `-` reads a bounded feed from standard input. Supported local files: Python, JavaScript, HTML/CSS, JSON, Markdown, text, TOML/INI/YAML, bounded UTF-8 source ZIPs and v1/v2 manifests/library backups. Links are retained as unverified references; no repository or documentation download occurs automatically.

The catalog is a transactional SQLite file in the user's private data directory, **outside the Git checkout** by default: Linux/macOS `$XDG_DATA_HOME/toad-sage` or `~/.local/share/toad-sage`, Windows `%LOCALAPPDATA%\ToadSage`. Set `TOAD_WORKSPACE`, or put `--workspace PATH` **before** the command. Keep that workspace private and back it up. File backups created by the CLI use owner-only POSIX permissions; on Windows, keep exports in a folder protected by your user account’s ACLs. GitHub is optional after obtaining the code.

```sh
python -m toad_core --workspace /my/private/toad status
python -m toad_core library archive CANDIDATE_ID
python -m toad_core library restore CANDIDATE_ID
python -m toad_core library delete CANDIDATE_ID
python -m toad_core queue inspect CANDIDATE_ID
python -m toad_core queue run --limit 10
python -m toad_core logs --limit 50
python -m toad_core export --id CANDIDATE_ID --output selected-backup.json
```

Export refuses to overwrite a file unless `--force` is explicit. Larger catalogs can be exported in selected batches (2 MB per portable backup). Catalog records include full source, dependency/compatibility metadata, inspection reports, permissions, test outcomes, history, related missions and previous versions. Unknown imported metadata is retained. Imported verification/install claims never become local authority.

If you want the shorter `toad` command, use a virtual environment and `python -m pip install -e .`. The module commands above work without installation or network access.

## Status means an actual event

| Status | Meaning |
| --- | --- |
| Received | Intake event recorded before inspection |
| Inspected | Static observations saved; no successful execution is claimed |
| Needs review | Invalid syntax, warnings, unresolved dependencies or incomplete executable information |
| Ready for testing | Configured tests and structural prerequisites exist; still unverified |
| Testing | A restricted worker operation is in progress |
| Failed | Actual execution/test evidence failed |
| Verified | Configured tests actually passed in the local Docker worker for this source digest |
| Installed | Locally verified snapshot activated in the **sandbox-only** versioned registry |
| Archived | Kept out of the active inbox, without granting new authority |

The browser produces received/inspected/review/archive events. It cannot verify or install abilities. Structural analysis, pattern scans and AI statements never certify safety. A tested malicious package can still be malicious; tests must meaningfully cover the intended behavior.

## Portable package format

```json
{
  "schema": "toad-ability-v2",
  "name": "hello-demo",
  "version": "0.1.0",
  "description": "Print a deterministic greeting",
  "files": [{"path": "main.py", "content": "print(\"hello\")\n"}],
  "entrypoint": "main.py",
  "permissions": [],
  "dependencies": [],
  "tests": [{"kind": "python", "path": "main.py", "expected_stdout": "hello\n"}]
}
```

Multiple pasted blocks may name files with a fence such as `python main.py` or `python tests/test_main.py`. The complete pasted source remains available. Unittest packages use `{"kind":"unittest","path":"tests"}` with actual `tests/test_*.py` files. V1 shell-style tests are retained as disabled metadata and must be replaced with structured specs. Nothing runs at ingestion. JSON/Python syntax checks are nonexecuting; other languages are labelled as unchecked where no parser is provided.

Limits: 250,000 UTF-8 bytes per file, 512,000 bytes per package/ZIP input, 40 files, 10 tests, 100 catalog candidates, 2,000,000 bytes per backup. Portable paths reject traversal, case aliases, device names, symlinks in ZIPs and protected core paths. ZIP expansion is bounded and no archive is extracted on the host.

## Optional tests, activation and missions

Provision your own supported Docker/Ollama environment with the [Acer guide](SETUP-ACER.md), [lab guide](docs/LAB.md) and [mission guide](docs/MISSIONS.md). No Acer specifications or successful host installation are assumed.

```sh
python -m toad_core lab status
python -m toad_core model status
python -m toad_core test CANDIDATE_ID
python -m toad_core library install CANDIDATE_ID
python -m toad_core library rollback ABILITY_NAME
python -m toad_core library deactivate ABILITY_NAME
python -m toad_core mission create "Create a simple Python calculator"
python -m toad_core mission run MISSION_ID
python -m toad_core mission report MISSION_ID
```

A mission saves checkpoints and budgets, finds relevant verified candidates, asks the local model for source and meaningful tests, statically inspects them, runs the restricted worker, attempts bounded source-only repairs and packages actually verified results. Pause/resume/cancel are durable. Completed missions do not run again. Missing Docker/model, unsupported permissions/dependencies, frozen-test violations or exhausted budgets produce an honest blocked report.

The present execution worker supports Python standard-library projects only. No imported hooks, shell tests, dependency installers, personal files, credentials, hardware access, host Docker socket mounts or public command endpoints are available. Installs preserve versions and rollback; they do not import third-party modules into the core. See the lab threat model for the security limits of containers.

## Development checks and deployment

```sh
python -m unittest discover -s tests -v
python tools/check_inline_js.py
node --test tests/web/*.test.cjs
npm ci --ignore-scripts
npx playwright install --with-deps webkit
npm run test:browser
python tools/build_site.py
```

Tests exercise trusted project code. Candidate samples are treated as data; live containment probes in `tools/lab_smoke.py --run` are opt-in on a separately provisioned **local** lab and are not run by GitHub Actions. CI checks Python 3.11/3.12, browser data logic and an iPhone-sized WebKit workflow. Pages deploys only `index.html` and the three `web/` assets after validation; catalogs, sources, ZIPs and private runtime directories are excluded.

The historical download `sage-toad-github-pages.zip` is obsolete and excluded from deployment. Use the repository's current source and guides.
