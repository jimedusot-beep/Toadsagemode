# Skill library: review before execution

Toad Sage keeps submitted skill instructions as **quarantined local data**. Importing a `SKILL.md` file does not run the body, download referenced files, grant any tool, enable an MCP server, or activate code. The public GitHub Pages dashboard remains separate from the private Python engine.

## Local usage

```sh
python -m toad_core skills import MY_SKILL.md --kind knowledge
python -m toad_core skills list --search debugging
```

The importer now validates a deliberately conservative **string-only subset** of the [Agent Skills specification](https://agentskills.io/specification). The top-level `name` and `description` are required. Optional string fields are `license`, `compatibility`, and experimental `allowed-tools`. An optional `metadata:` mapping accepts up to 32 indented string entries. Duplicate keys, unsupported YAML tags/aliases/complex structures, malformed quoting, invalid names, and oversized values are rejected.

**This is not full YAML or full Agent Skills directory support.** Folded/multiline YAML scalars, scripts/resources beside `SKILL.md`, and parent-directory/name matching are not processed by this file-only importer. Do not claim that an imported skill has passed upstream `skills-ref validate`. Use an independently audited validator for more complex upstream packages.

## Trust boundary

- Every imported item remains `status: quarantined`, `executed: false`, `installed: false`, and `granted_permissions: []`.
- `allowed-tools` is recorded inside `source_metadata` **as an untrusted declaration**; it never turns into a capability grant.
- The operator-supplied `permissions` list is also a declaration, not an authorization.
- The source SHA-256 digest binds stored metadata to the original imported text.
- Keep imported knowledge separate from tool instructions and sandbox execution. A reviewer must independently assess source rights, claimed dependencies, risk, expected behavior and tests.
- Executable programs remain subject to Toad Sage's existing inspection, restricted Docker testing, local receipt and explicit sandbox-only installation policy. Skill import alone is not an activation path.

## Next incremental steps

1. Add offline full-text search for verified knowledge and review evidence.
2. Attach independent scan results (Ruff/Bandit/secret checks) to candidate records.
3. Extend reviewed permissions and digest-bound approval as an explicit, separate operation.
4. Exercise the real Docker isolation checks on a configured local host before any claims of safe execution.

Do not automatically merge imported instructions into the protected core.

## Offline discovery and reported evidence

The existing JSON skill catalog remains the canonical local store. The optional `--ranked`
search creates a temporary SQLite **FTS5 index entirely in memory** from that local
catalog, uses quoted search terms, and discards the index after returning ranked
metadata-only results. No downloads, hosted embeddings, persistent copy of source,
plugins, or model inference are needed. If the Python SQLite build lacks FTS5,
a bounded local substring fallback is used.

```sh
# Return top-five matching records without the original instruction bodies.
python -m toad_core skills list --ranked --search "python debugging" --limit 5
python -m toad_core skills list --ranked --search "offline" --kind knowledge
```

The original `skills list --search` remains unchanged for backward compatibility.
The current catalog still limits import to 100 skills; FTS5 is **not** a claim of
production-scale search performance. Queries are limited and escaped as text.

For documentation of what a human actually attempted, an append-only,
bounded **self-reported evidence** log is available. Find a skill's full
64-character digest using `skills list`:

```sh
python -m toad_core skills evidence FULL_SKILL_SHA256 scan passed --note "Manual offline scan, no detected findings"
python -m toad_core skills evidence FULL_SKILL_SHA256 sandbox blocked --note "No validated local Docker worker"
python -m toad_core skills evidence FULL_SKILL_SHA256 test not-run --note "Awaiting reviewed behavior tests"
```

The optional `--report-sha256` records a reported report/artifact digest; it
does **not** retrieve, parse, or verify that report. Evidence has
`trust: self_reported_unverified`, `execution_performed: false`, and
`grants_permissions: false`. An entry saying `passed` is **not a verified
receipt or approval**, and it cannot activate any skill. The record is explicitly
a user's claim about an external observation, not a statement about a test run
performed by this command.

To graduate executable abilities from quarantine in a later phase, use a
separate, trusted workflow that independently validates the report, confirms
the exact skill/content digest, checks worker isolation and test relevance,
and obtains explicit human authorization. Do not infer consent or promote a
record based on a self-reported event.

No execution hooks, automatic activation, GitHub writes, browser connection,
or model calls are added by these commands.
