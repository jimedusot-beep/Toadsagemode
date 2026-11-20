# SageCode Tools V1 — backend-to-Studio contract

**Status:** internal, source-only Python interface. This document is a contract for Agent B's proposed UI adapter, **not a deployed API**, a remote execution endpoint, an AI model connection or a proof of running applications.

## Trust and authorization

- SageCode uses `toad_core.project_tools.SageProjectTools` and the repository's existing `toad_core.schema.normalize_package` contract. A trusted orchestrator explicitly supplies an `allowed_project_ids` `set` or `frozenset`. **Do not derive that allowlist from AI output, browser text, imported skills, or an untrusted project manifest.** A project ID alone is not authentication.
- Source lives in private `workspace/sagecode-v1/PROJECT_ID/` JSON records. It does not navigate the host checkout or execute source. The trusted operator must protect the workspace and manage its backups.
- The records are immutable revisions addressed by their SHA-256 digest, with an atomic HEAD pointer and an immutable original baseline. Edited code is a **proposal**, not a verified installed ability. Source hashes detect accidental/casual tampering, but **are not a cryptographic authentication scheme against same-user host compromise**.
- The current V1 component has **no network service, subprocess tool, shell, model invocation, approval transition, live preview, deployment, Git commit or automatic push**. These require separately reviewed modules. No privilege or hardware control is granted.
- Operations use the existing 40-file, 250-kB-per-file, 512-kB-package constraints; accepted source names are portable and protected core paths are forbidden. Secret-suggesting paths are rejected conservatively, but this is not a comprehensive credential scanner. Never import secrets into source candidates.
- **Local writer exclusion (audit hardening):** source edits and restores now claim an exclusive, owner-private `.sagecode-write.lock` before checking `expected_revision` and modifying HEAD. Concurrent writers fail closed instead of both accepting the same stale revision. A crash may leave the lock; the trusted operator must inspect project state before removing it manually. This is **not** a distributed transaction or a guarantee for network/shared filesystems; no public editing endpoint is authorized.
- A source diff is prepared **before** the revision pointer moves. Diff preparation or failed immutable-record writes leave the prior HEAD in place; a failed HEAD replacement also removes any newly created orphan revision when cleanup is possible. The storage directory must still be protected and backed up by its trusted owner.

## Trusted Python entry points

```python
from toad_core.project_tools import SageProjectTools

allowed = {"example-project"}  # trusted controller decides this
project = SageProjectTools.create(
    "/private/toad-workspace", "example-project", trusted_package,
    allowed_project_ids=allowed,
)
project = SageProjectTools("/private/toad-workspace", "example-project", allowed_project_ids=allowed)
status = project.status()
tree = project.list_tree()
source = project.read_file("src/main.py", start_line=1, max_lines=100)
search = project.search("calculator", limit=50)
proposal = project.propose_edit("src/main.py", "print(42)\n", expected_revision=status["revision"])
restored = project.restore(status["revision"], expected_revision=proposal["revision"])
```

All file operations are restricted to **the finite source manifest already provided for that project**. V1 edits existing declared files only; new files, renames and deletions will require a separately reviewed expansion. Calling `restore` only switches the draft revision pointer. Neither operation changes the approved checkout or installed abilities.

## JSON-shaped data for Agent B's UI adapter

These are example response **shapes**, not live API endpoints. All values below are illustrative, never verified test receipts or an actual model response.

### 1. Project status

```json
{
  "schema": "sagecode-project-status-v1",
  "project_id": "example-project",
  "revision": "<64-character SHA-256 revision>",
  "baseline_revision": "<64-character SHA-256 revision>",
  "verification": "unverified",
  "review_status": "pending_review",
  "executed": false,
  "approved": false,
  "release_allowed": false,
  "test_evidence": null
}
```

**Do not** display a green "verified", "tested" or "approved" badge solely because the model proposed a working app. Those transitions belong to later independent testing and owner approval services; this module intentionally has no method that grants them.

### 2. File list

```json
{
  "project_id": "example-project",
  "revision": "<revision>",
  "entries": [
    {"path": "src", "kind": "directory"},
    {"path": "src/main.py", "kind": "file", "bytes": 10, "sha256": "<file-content SHA-256>"}
  ]
}
```

Folder entries are **virtual**, derived from declared manifest paths. Sage does not browse arbitrary user files. Files have SHA-256 content digests and byte lengths.

### 3. Source reader

```json
{
  "project_id": "example-project",
  "revision": "<revision>",
  "path": "src/main.py",
  "start_line": 1,
  "total_lines": 1,
  "content": "print(42)\n",
  "truncated": false,
  "sha256": "<file-content SHA-256>"
}
```

`start_line` is 1-based; `max_lines` must be 1–200; output is capped at 16 kB. The UI must display `truncated` and offer bounded additional reads instead of pretending the file ended.

### 4. Search results

```json
{
  "project_id": "example-project",
  "revision": "<revision>",
  "term": "calculator",
  "matches": [{"path": "README.md", "line": 2, "snippet": "Calculator test", "kind": "content"}],
  "limited": false
}
```

`line: 0` means a filename match, not a source line. A bounded result set does not prove the term occurs nowhere else.

### 5. Proposed edit and diff

```json
{
  "project_id": "example-project",
  "revision": "<new revision>",
  "parent_revision": "<previous revision>",
  "unchanged": false,
  "diff": "--- a/src/main.py\n+++ b/src/main.py\n@@ ...\n",
  "truncated": false,
  "verification": "unverified",
  "review_status": "pending_review",
  "release_allowed": false
}
```

The caller supplies `expected_revision`; stale requests fail closed and do not move HEAD. Concurrent writers are also excluded by the private lock, with no automatic stale-lock removal. A diff may be truncated at 30 kB and must be labeled as partial. To avoid unbounded line-comparison costs, a very large comparison may instead return **`diff: ""`, `truncated: true`, `unchanged: false`**; this means **the diff was omitted, not that there are no changes**. In that case, require complete before/after source inspection before review. The project is unverified after any edit, regardless of model assurances.

### 6. Restore result

```json
{
  "project_id": "example-project",
  "revision": "<target revision>",
  "previous_revision": "<revision before restore>",
  "restored": true,
  "verification": "unverified",
  "review_status": "pending_review",
  "release_allowed": false
}
```

Restoration is a source-only draft operation; it **does not undo deployed software or physical operations**.

### 7. Test and approval presentation

SageCode Tools V1 always reports `test_evidence: null` and `verification: "unverified"`. Future independent workers may provide separately authenticated receipts that bind the exact source revision, test plan, worker identity, execution result and cleanup. The UI may show these states as **not yet available**, but must not create fake passing test records.

Owner approval/rejection is a separate, authorization-controlled workflow. The UI can display review buttons as disabled or fixture-only until Agent A provides a safe owner gateway. **Do not call any source-only edit method "approve."**

### 8. Errors and blocked states

Invalid, unauthorized, tampered or stale requests raise `toad_core.schema.PackageError`. A trusted future adapter should map these to a generic `blocked` state without leaking host paths, filesystem details, credentials or stack traces to an untrusted client. Suggested UI-only error shape:

```json
{"status": "blocked", "code": "invalid_or_unauthorized_project_request", "message": "This source operation is unavailable", "retryable": false}
```

Other UI states: `loading`, `ready_unverified`, `pending_review`, `failed`, `blocked`, `tests_unavailable`. `verified` and `approved` are **reserved**, and must be backed by separately checked evidence.

## Acceptance and handoff to Agent B

Agent B can implement a read-only, mobile-friendly file tree, source viewer, bounded search UI and proposal diff panel against **explicitly labeled local fixtures** matching these response shapes. Do not invent an HTTP endpoint or pass authorization from browser to the trusted controller. Do not preview or execute arbitrary candidate source inside the main Studio page.

The backend's own tests cover multi-file listing/search, bounded reads, revision snapshots, restore/reopen, stale-write rejection, concurrent writer exclusion, failed diff/write recovery, bounded diff fallback, path traversal, denied source paths, symlinks, tampered revisions and honest unverified status. Full repository CI must pass independently; a unit-test pass is not a proof of OS-level containment, production authorization or browser functionality.

## Engineering basis and provenance

- Existing project contracts: [`schema.py`](../toad_core/schema.py), [`controlled_agent.py`](../toad_core/controlled_agent.py), [`mission_engine.py`](../toad_core/mission_engine.py), [`git_drafts.py`](../toad_core/git_drafts.py) and [`lab.py`](../toad_core/lab.py).
- H.E.R.B.I.E. Master Knowledge Bank (research reference edition, 12 October 2026): p. 4, Margaret Hamilton — explicit safe states and resilience; p. 9, Grace Hopper — modular interfaces and repeatable tests; p. 7, Rodney Brooks — independently enforced lower-level safety. These are project design analogies, **not** claims that their original systems implement SageCode.
- OpenCode documentation (comparative requirements, no copied implementation): https://opencode.ai/docs/tools/ and https://opencode.ai/docs/permissions/ .
- GitHub Actions and review controls: https://docs.github.com/en/actions .
