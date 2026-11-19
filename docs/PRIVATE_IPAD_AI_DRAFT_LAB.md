# Toad Sage private AI Draft Lab — iPad control, cloud-hosted Python (draft)

This feature provides an **owner-only, untrusted-source-only** web UI
served by a trusted Python process. It uses the existing model factory and
QuarantinedWebGenerator; it does **not** create a new AI model, provide a
subscription, or publish an AI app.

**Release state:** draft PR, contract and loopback-socket tests only. There
is **no provisioned cloud host, no real model request, no live iPad session,
no verified Docker WebKit containment, no repaired app and no deployment**.

## Why this is a separate service

The existing private phone bridge (docs/PRIVATE-BRIDGE.md) intentionally has
no network endpoint that launches a model or agent. Do not turn its feed
ingestion endpoint into command execution. This new independent service
provides a narrow explicit model-drafting capability only.

Existing model selection is replaceable on the trusted Python host:
- Default TOAD_MODEL_PROVIDER=ollama: loopback Ollama running on **that**
  host (could be a properly sized private cloud VM). No Ollama model is
  automatically downloaded or installed. The original laptop is optional.
- TOAD_MODEL_PROVIDER=openai: existing paid OpenAI Responses adapter,
  **disabled unless** the server has a model ID, a private API key and
  TOAD_ALLOW_PAID_AI=YES. No user-facing browser can supply these settings.
  Do not enable a paid service without an explicit later decision.

No provider is currently proven available in a user cloud host. A
Codespace is a possible **control-plane** Python environment, not proof
that it has enough RAM/CPU/GPU to run any chosen Ollama model. Codespaces
uses a limited included quota, so check account usage and spending controls.

## Trusted cloud setup (not deployed by this PR)

From the branch's checkout on a trusted private cloud Python host:

1. Review toad_core/owner_gateway.py, owner-ai-studio/*.js, CSS, tests,
   and GitHub PR check results.
2. Establish a **private HTTPS** ingress or GitHub Codespaces **private**
   forwarded port, with GitHub account authentication. Never set the
   forwarded port to public. Set its protocol to HTTPS if necessary.
3. Configure a permitted model on the cloud host. To stay within $0 API
   spending, keep paid AI disabled; only use an authorized local provider
   if it is actually installed and working. No free hosted inference or
   GPU availability is implied.
4. Explicitly opt into the private gateway on the host:

       TOAD_ENABLE_PRIVATE_AI_STUDIO=YES python -m toad_core.owner_gateway --port 8766 --max-drafts 1

5. The trusted host terminal displays a freshly generated **owner token**
   (unless a strong token is configured as a server environment variable).
   Never paste it into GitHub issues, PRs, Netlify, scripts, URLs or a
   public app. Open only the **private forwarded HTTPS URL** on the iPad.
6. Paste the token into the password field. The browser keeps it only in
   the current page's memory; it is sent in a request header to the same
   private origin, never as a URL or stored in browser localStorage.
7. Use **Check connection metadata** to see provider selection and
   remaining call budget; this makes **zero model requests** and does not
   validate model availability.
8. Ask for one small static site (for example an offline study planner).
   The server calls the selected model exactly once through the existing
   generate_json adapter, strictly validates the three-file manifest
   and saves the source as **private JSON data**, not executable files.
9. Review filenames, SHA-256, risk flags and HTML/CSS/JS as **text only**.
   The JavaScript is never loaded into a web page, iframe or eval.

Stopping the gateway or deleting a Codespace does not create a deployable
app; back up the private workspace through a separate reviewed process.

## API (owner-only, no CORS or webhooks)

GET /                     static trusted UI, no secret embedded
GET /api/status           owner header required; no inference
POST /api/drafts          owner header + matching Origin, JSON {goal: string}
GET /api/drafts/DRAFT_ID  owner header required; inert source as JSON data

- The listener binds to **127.0.0.1 only**, not a public interface.
- An owner token of 32+ printable characters is required; a fresh random
  one is generated per start when unspecified.
- Only a single bounded goal field is accepted. The input must be short
  UTF-8 JSON (1–2500 goal bytes); no instructions for shell, Docker,
  Git, secrets or deployment exist in the API.
- At most 1–3 total calls per server lifetime, default **one**. The quota
  is reserved before invoking the model, without retries. No billing
  claims are made by the gateway itself.
- A wrong token, cross-origin POST, extra JSON fields or malformed payload
  cannot trigger model generation. Model failures return a generic error
  without raw provider errors or secrets.
- Response headers disable caching, sniffing and framing, and restrict
  scripts and network requests to the same origin. All AI-generated source
  is inserted into the UI by textContent, never innerHTML or iframe.
- The browser shows ONLY metadata / inert source strings. It has no API
  for candidate execution, source ZIP, export, repair, Git push or
  deployment. The original app Studio's safe-template ZIP pathway is
  intentionally separate.

These safeguards are **not** a full security guarantee. Cloud ingress,
OS, model runtime, account permissions and reverse-proxy configuration
must be inspected separately. Do not use this with sensitive or clinical data.

## How to verify

- Run Python unit tests on a trusted CI runner (no model call):
  python -m unittest tests.test_owner_gateway tests.test_web_codegen -v
- Confirm that all standard Node/WebKit/template tests remain green.
- A **real** first-person trial needs an actually configured host and
  model, an actual response, its private quarantine record and independently
  reviewed code. CI model doubles are not evidence of live inference.
- Generated JavaScript must remain inert until a separately secured
  disposable Docker WebKit host passes real isolation probes and independent
  frozen acceptance tests. Green CI tests of mocked Docker are not proof.

## Design rationale and primary references

- Reuse the existing model selection and source quarantine instead of
  inventing a second coding engine:
  toad_core/cloud_models.py, toad_core/web_codegen.py
- Separate the network AI surface from feed-ingestion authority:
  toad_core/bridge.py and docs/PRIVATE-BRIDGE.md
- Independent human-defined checks must precede generation:
  docs/FROZEN_WEB_ACCEPTANCE.md and docs/WEBKIT_LAB.md
- GitHub Codespaces port forwarding:
  https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace
- GitHub Codespaces included quota:
  https://docs.github.com/en/codespaces/troubleshooting/troubleshooting-included-usage
- Playwright warns its Docker image alone is not appropriate for
  running untrusted websites:
  https://playwright.dev/docs/docker
