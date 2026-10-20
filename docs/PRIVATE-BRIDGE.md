# Private Phone-to-Acer Bridge — experimental

The private bridge is **not** the public GitHub Pages dashboard. It is an
authenticated, loopback-only service running alongside the local Python engine.

## Setup (on an authorized Acer/host)

1. Get the Toad repository onto the computer and confirm Python 3.11+:
   `python -m toad_core doctor`.
2. Start the private bridge from the repository checkout:
   `python -m toad_core bridge --port 8765`.
3. The command prints a fresh pairing code in the local terminal. It is not
   committed, uploaded, or accepted by GitHub Pages. Keep it private.
4. For iPhone access, configure a **private HTTPS reverse proxy** to
   `127.0.0.1:8765` using a trusted private networking tool, for example
   Tailscale **Serve**, NOT **Funnel**. The proxy must preserve the request
   `Host` header and browser `Origin`. Do not forward this port publicly.
5. Open `https://YOUR-PRIVATE-DEVICE-HOST/private` on the phone. If not
   paired, you will see a sign-in form at `/login`. Enter the temporary code.
   The browser receives a Secure, HttpOnly, SameSite=Strict session cookie.
6. Paste a harmless sample and select **Send to private engine**. A saved
   candidate appears in the private SQLite-backed catalog and the status list.
   The site polls actual catalog and mission status every 10 seconds.

The pairing code regenerates every time the bridge restarts. Sessions are
short-lived in-memory records and can be cleared by restarting the service.
No passwords or tokens are required in a public URL or browser JavaScript.
Failed logins are throttled. No CORS access is allowed.

**Important:** This service never executes submitted feeds or creates/runs a
mission from a network POST. It accepts only a size-limited feed import, and
offers authenticated read-only status. Agent commands and Docker tests must
be explicitly started from the trusted local console.

## Security boundaries

- TCP listener bound to `127.0.0.1`. Public serving is prohibited.
- No authentication token in GitHub, GitHub Pages or permanent site assets.
- Sensitive POSTs require an authenticated cookie, browser Origin and
  matching per-session CSRF header.
- Response headers disallow framing, caching, cross-origin scripts and
  outbound web requests from the private console.
- No endpoint runs the host shell, git, a mission, or Docker commands.
- An authenticated user can import data; do not expose the private bridge
  to untrusted household or shared-network accounts.
- HTTPS must be provided by the private reverse proxy. Browsers may reject
  Secure cookies on plain HTTP. Avoid direct HTTP use from mobile devices.
- A reverse proxy or operating system compromise is outside this boundary.
- The bridge is single-user experimental software, not a hardened public
  multi-tenant product.

## Testing

`python -m unittest tests.test_private_bridge -v` or run all tests:
`python -m unittest discover -s tests -v`.

HTTP tests use a real loopback socket, exercise pairing/session/cross-origin/
CSRF controls, ingest actual candidate records, and confirm no feed execution.
These tests do not prove real Tailscale/HTTPS/iPhone operation.

## Controlled agent, Git drafts and skill imports

The separate experimental model tool loop uses **explicit candidate IDs**:
`python -m toad_core agent run demo1 --candidate-id CANDIDATE_ID --goal "Review and repair this candidate"`.
It can read only candidate manifest files, inspect, propose Git-backed edits,
ask the restricted Docker worker to run declared tests, and finish. It cannot
run shell commands. Each step is recorded in a private trajectory checkpoint.
If an operation is interrupted mid-step, it is blocked from blind replay.

Skills can be imported as quarantined metadata:
`python -m toad_core skills import MY_SKILL.md --kind knowledge`
`python -m toad_core skills list --search debugging`.
Skill descriptions are **not** executable permissions. `executable` is a
classification, not authorization or host installation.

The Git draft layer uses newly created local Git repositories with hooks and
global configuration disabled. Each proposed change has a bounded diff and a
separate catalog revision. Versioned sandbox installation and rollback remain
separate, under Toad's existing registry/receipt policy.

## Actual demonstration still needed

Run on your **real provisioned computer**:
`python tools/calculator_demo.py` (readiness only)
`python tools/calculator_demo.py --run` (explicit actual Ollama + Docker run)

The second command must be blocked until the local Docker lab and model are
available. It never reports success based on mock-worker results. Before using
the Docker lab with unfamiliar code, run the containment smoke suite documented
in [LAB.md](LAB.md), and verify resource limits on the actual host. No one
should claim a real autonomous demonstration before it has produced a genuine
Docker receipt and output artifacts.

## Third-party source attributions

`toad_core/controlled_agent.py` adapts the minimal loop architecture and
run/step/query/execute-actions separation of
[mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent)
(MIT, copyright Kilian A. Lieret and Carlos E. Jimenez, 2025).
The full copyright/license is retained in
[`third_party_licenses/mini-swe-agent-MIT.txt`](../third_party_licenses/mini-swe-agent-MIT.txt).

Other implementation approaches were **inspired** by
[OpenHands](https://github.com/OpenHands/OpenHands),
[Aider](https://github.com/Aider-AI/aider),
[Agent Skills](https://github.com/agentskills/agentskills),
[Goose](https://github.com/aaif-goose/goose) and
[LangGraph](https://github.com/langchain-ai/langgraph).
Their source was not copied by these changes.

This work has not modified unrelated repositories or devices.
