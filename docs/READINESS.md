# Check the local engine

From the downloaded/cloned repository, using Python 3.11 or newer:

```sh
python -m toad_core doctor
python -m toad_core doctor --probe
```

Put `--workspace PATH` **before** `doctor` to choose another private catalog directory. The default is the same private directory used by the other CLI commands. The offline check opens/initializes the catalog, tightens existing POSIX workspace/database/sidecar permissions and checks catalog access. It does not ingest anything or export candidate contents or names. It reports the workspace path and candidate count; review these before sharing a diagnostic report.

The default check makes no network request and does not invoke Docker or a model. `--probe` additionally performs the existing restricted Docker capability/image inspections and one loopback Ollama `/api/tags` request. It does not create/start containers, execute a candidate, generate code, install dependencies, download images/models, or change runtime configuration. Docker metadata calls have existing five-second per-call deadlines; model metadata has a three-second whole-operation deadline. These are setup probes, not performance measurements or hardware sizing recommendations.

JSON output uses `schema: "toad-readiness-v1"`. The `checks` object reports runtime, workspace, lab and model observations. `capabilities` separates the following:

| Capability | `ready` means | It does not establish |
| --- | --- | --- |
| `library` | Supported Python and access to the private catalog | That imported code is correct, safe, verified or installed |
| `testing` | Library access plus the lab's required metadata/image checks pass | Actual containment, test success or cleanup on this host |
| `missions` | Library and testing prerequisites plus the configured model appears installed | Successful inference, good model output or a completed mission |

`not_checked` means optional dependencies were not probed. `blocked` means a required check failed; use its reason and `next_steps`. The report always sets `execution_performed` and `containment_verified` to `false`, including when all prerequisites are ready. Runtime/workspace errors block all capabilities. A missing lab/model does not block library management. If the library check fails, dependency probes are skipped.

| Exit code | Meaning |
| --- | --- |
| `0` | Offline library check passes; with `--probe`, all requested prerequisites pass |
| `1` | Python/workspace check failed |
| `2` | With `--probe`, library works but testing/model prerequisites are blocked |

Invalid CLI arguments use the standard argparse error and exit `2`, rather than a readiness JSON report. Diagnostic check failures are JSON on stdout; argument parsing errors are on stderr.

After a successful lab metadata check, follow [LAB.md](LAB.md) and run `python tools/lab_smoke.py --run` **on the local execution host** before relying on restrictions. Then run one harmless bounded mission using [MISSIONS.md](MISSIONS.md). No smoke suite runs automatically from `doctor` or in GitHub Actions. A blocked report must never trigger direct host execution as a fallback.

On Windows, POSIX mode bits cannot establish privacy: use a workspace and export folder protected by your Windows user ACLs. Existing catalogs are not reset when a diagnostic check fails. Preserve the files and investigate or restore a known backup.

## What was checked here

The report is tested with real temporary catalogs, blocked/corrupt workspace paths, a local HTTP metadata fixture and the Docker subprocess boundary double. The live development-host probe reports offline library access ready, Docker absent and Ollama unavailable. Actual container containment, actual model inference and Acer installation remain unverified.
