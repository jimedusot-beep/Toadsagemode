# Toad Sage Absorption Protocol

## Goal
Copy or upload code from ChatGPT/Gemini. The future local agent should inspect, test, and install it as an independent, reversible capability with minimal user babysitting.

## Current state
The GitHub Pages Feed Inbox is browser-only. It creates an unverified `toad-feed.json`. It does not execute or install content. The Python validator in this repo only performs structural checks; it is **not** a malware detector or sandbox.

## Planned milestones
1. Intake and review: accept a manifest with a list of files, validate format and paths, flag suspicious text. Never execute during intake.
2. Ability Library: catalog module name, version, source, required permissions, compatibility, tests, installation status, and previous known-good release.
3. Offline sandbox: run controlled automated tests with CPU/memory/time limits, read-only container filesystem, no network, and no access to personal files or secrets.
4. Install: stage modules outside the protected core; activate only after required tests pass; maintain versioned backups and rollback.
5. Repair and reuse: AI may propose modifications, but only tested modules become available to other projects.

## Constraints
No payment information, no paid APIs by default, no access to private files, no unattended host shell privileges, and no self-modifying core. Minimize approval prompts by preauthorizing only bounded workspace operations. GitHub must remain optional; the engine should eventually run locally.

## Example package
```json
{
  "schema": "toad-ability-v1",
  "name": "json-status-check",
  "version": "0.1.0",
  "description": "Validate a JSON status record",
  "files": [{"path": "main.py", "content": "import json\nprint(json.loads('{\\\"ok\\\": true}'))"}],
  "entrypoint": "main.py",
  "tests": ["python main.py"],
  "permissions": []
}
```

Never blindly run an untrusted package's tests. Execute only in a separately provisioned sandbox once implemented.
