# Local model and mission engine

Basic ingestion/catalog/queue/export work is entirely offline and needs neither Docker nor a model. Autonomous **Python standard-library** projects additionally need a locally running Ollama server, an installed coding model, and the restricted Docker lab in [LAB.md](LAB.md). No paid API, model pull, fine-tuning, or hardware configuration is performed automatically.

## Optional Ollama adapter

The default URL is `http://127.0.0.1:11434`, configurable with `TOAD_OLLAMA_URL`. Only loopback HTTP(S) origins are accepted. URL credentials, redirects, proxy forwarding and remote hosts are refused. This keeps source inside the configured local model boundary. It does not protect against a hostile local model service or a host administrator.

`TOAD_OLLAMA_MODEL` defaults to `qwen2.5-coder:1.5b` as a lightweight initial example, not a guarantee of coding quality or suitability for the Acer. Inspect the actual computer's resources before choosing/downloading a model. No hardware assumptions are made.

Requests use `/api/generate`, `format: "json"`, `stream: false`, temperature 0, seed 0 and at most 2,048 generated tokens by default. Defaults cap each prompt at 120,000 bytes, response at 256,000 bytes and the complete HTTP operation at 30 seconds. A separate trusted transport process enforces the wall deadline across connection, headers and body, including slow-trickle responses; candidate material remains JSON data. The adapter rejects malformed/incomplete/oversized responses. Deterministic options do not guarantee identical model answers. All answers remain candidate data; source validation, test evidence and permission policy are separate.

```sh
python -m toad_core model status
# Optional, after installing Ollama yourself and deciding the hardware can support it:
ollama pull qwen2.5-coder:1.5b
# Run the local Ollama service according to its official OS instructions.
```

A live probe here returned connection refused, so successful live inference is **unverified**. Adapter tests use a real local HTTP test server with controlled responses, not a running language model.

## Mission lifecycle

```sh
python -m toad_core mission create "Create a simple Python calculator"
python -m toad_core mission list
python -m toad_core mission run MISSION_ID
python -m toad_core mission show MISSION_ID
python -m toad_core mission pause MISSION_ID
python -m toad_core mission resume MISSION_ID
python -m toad_core mission run MISSION_ID
python -m toad_core mission cancel MISSION_ID
python -m toad_core mission report MISSION_ID
```

Create prints a real unique ID; substitute it for `MISSION_ID`. Resume requeues saved progress; run continues it. The process must be running for work to advance. This is a bounded CLI runner with checkpoints, not an always-on service or an automation scheduled by this chat. Run in a private terminal/tmux if appropriate; sleep, host shutdown and Codespace idle shutdown stop it.

The phases are plan, catalog search, generate, inspect, test, optional source repair and package. Search records potential reusable verified abilities and capability gaps; the model receives small matching package examples. This is a foundation for capability composition, not a general hardware/robot controller. Nothing gains physical-device access or modifies another repository.

Every operation saves durable progress to SQLite. Generation and candidate linkage share one transaction; repeated imports use content identity. A lease prevents simultaneous runners, and expired leases can be reclaimed. Model/test/repair budgets are reserved before calls and survive restarts. A runner also reserves its remaining elapsed-time allowance before work starts; normal exit refunds unused time, while an abandoned runner conservatively consumes that reservation when its expired lease is reclaimed. A crash may consume a reserved call and the remaining elapsed-time allowance without a result; it cannot reset the budget. This conservative choice can block a mission after a brief crash; its candidate source remains available for a new mission. The elapsed_seconds field includes such explicitly logged budget charges. `--steps 3` on mission run stops after three phases and leaves a queued checkpoint.

Pause/cancel is observed before/after bounded operations; worker execution also polls it. An in-flight model HTTP call may take its configured timeout to return. A paused mission's lease must be released before resuming. Cancellation is terminal. Completed missions return their existing outcome without regeneration. A blocked mission has a reason and preserved artifacts/candidates; resolve the reason and resume. Requeuing never resets its budgets.

Default total budgets: 6 model calls, 4 test runs, 2 source repairs, 180 seconds of processing time across runs, and 40 phase attempts. Override supported counts at create time:

```sh
python -m toad_core mission create "Create a calculator" \
  --max-model-calls 6 --max-test-runs 4 --max-repairs 2 --max-seconds 180
```

A repair receives observed failure output and an explicitly heuristic diagnosis. The proposal must keep name/version, file paths, entrypoint, dependencies, permissions, compatibility, test specifications and test files unchanged. It may change source contents only. Each version and its failure history remain in the catalog. Identical proposals, unchanged failing evidence, invalid packages and exhausted budgets stop the loop. An AI claim of success never completes a mission.

A completed mission requires an actual successful local Docker receipt for the current candidate. It produces `project.zip` (source plus portable manifest), `report.json` (test evidence and limits) and `PROJECT.md` in the private workspace. Installation is a separate explicit `library install` command and remains sandbox-only. Browser backup imports never import activation authority.

## Current limits

Live Docker and Ollama operation are blocked in this development host. End-to-end mission tests use explicit model/worker doubles; they demonstrate orchestration, checkpointing, repair, budgets and packaging, not the quality of any downloaded model or successful live containment. Large projects, third-party dependencies, non-Python execution, repository/document downloads, multi-user services, background scheduling and open-ended self-modification are not implemented. The core and policy remain outside candidates' authority.

Reference: [Ollama generation API](https://docs.ollama.com/api/generate).
