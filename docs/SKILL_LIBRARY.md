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
