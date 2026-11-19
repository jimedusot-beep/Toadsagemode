# Cloud AI option for Toad Sage App Studio

This branch adds a **server-side OpenAI Responses adapter** as an opt-in
alternative to Toad Sage's existing loopback-only Ollama model. It uses
the current OpenAI Responses API, not the retired GitHub Models API.

The goal is to make an **actual model request** possible on a trusted,
authorized cloud Python host without embedding a token in the static
iPhone/Netlify app. The adapter is tested with controlled response doubles;
**no paid model request has yet occurred**, no server host has been
provisioned and no custom AI-generated app has been deployed.

## Default is OFF

The existing app planning/source drafting flows still use local Ollama
by default. To explicitly choose a paid hosted model, a trusted server
operator must configure all four settings privately in the hosting service:

| Server-side setting | Meaning |
| --- | --- |
| `TOAD_MODEL_PROVIDER=openai` | Explicitly select this provider |
| `TOAD_OPENAI_MODEL` | Exact API model ID approved for the project |
| `OPENAI_API_KEY` | Secret set **only** in server environment/secret manager |
| `TOAD_ALLOW_PAID_AI=YES` | Separate explicit permission to make billable calls |

No default API model is chosen. No key is created, acquired or shared by
Toad Sage. Do **not** paste a key into ChatGPT, a GitHub repository, a
Netlify frontend variable, an iPhone shortcut, or browser localStorage.

**Cost**: ChatGPT Plus does not automatically pay for OpenAI API calls.
API usage is billed separately at the configured model's published rates.
The current adapter makes at most **one** Responses request per method
call, with no automatic retries or loops. The host operator should
set project spending limits/alerts and use a restricted key. An
automated long-running builder needs additional budget enforcement
before remote access is enabled.

## What is available now

```sh
# Check local environment flags; NO external request, NO billing.
python -m toad_core app ai-status

# After your secure server is configured, explicitly invoke one proposal:
python -m toad_core app propose "Build a searchable study journal"

# Source code generation is quarantined as JSON, never auto-executed:
python -m toad_core app draft-code "Build an original flashcard app"
```

For independent test evidence, prefer the plan-first workflow:
`app freeze-tests` → `app draft-with-tests` → `app web-trial` →
`app test-web-trial`. The last step remains **dry-run by default** and
requires a separately verified, local, opt-in Docker WebKit worker
on a dedicated disposable Linux VM.

The adapter accepts only a configured model ID and a fixed
`https://api.openai.com/v1/responses` destination. It uses the
`text.format.type=json_object` format, `store:false`, an empty tools
list, and bounded input/output size and wall time. Model output is
still treated as **untrusted JSON data**, validated by the app-planner
and web-draft schemas before storage. Unsupported model responses,
refusals, timeouts, redirects, tool calls and malformed JSON fail
closed without executing source.

The outbound request is made by a trusted isolated Python subprocess,
with no shell invocation. The key travels only through that process's
environment, never through the model prompt, command arguments or
logs. The request helper refuses proxy-based routing and HTTP redirects.
This does not remove the need for proper trusted server administration.

## What it does NOT do

- It does not authenticate people using an iPhone, expose a REST endpoint,
  install Replit/Render/Netlify Functions, or grant public access.
- It cannot safely connect directly from a public static page; doing so
  would expose the API key and invite abuse/charges.
- It does not activate GitHub branch protection, merge drafts or deploy.
- It does not prove that a particular API model supports JSON mode
  correctly until a real authorized request succeeds.
- It does not provide actual on-host Docker containment evidence.

## Live-proof checklist before enabling any mobile user interface

1. Select the authorized provider/model, establish a restricted billing
   project, and store the API key only in a server secret manager.
2. Confirm `app ai-status` indicates a configured key and explicit opt-in;
   this is metadata, not successful authentication.
3. Send **one** non-sensitive, bounded app proposal on a trusted server
   and record the provider ID, model ID, elapsed time, request/output
   hashes, response status and approximate token usage without any
   secrets or user private data.
4. Confirm the source draft remains quarantined; no automatic browser
   execution occurs.
5. Independently verify the WebKit Docker worker on a disposable Linux VM
   before running generated JS. Frozen acceptance tests and owner review
   are mandatory.
6. Design an authenticated, rate-limited, owner-only iPhone web service
   with billable-use caps and no unsafe secret leakage. Keep it
   completely separate from the public static task app until reviewed.

## Up-to-date primary references

- [OpenAI Responses create API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [API pricing](https://platform.openai.com/pricing/)
- [GitHub Models retirement (July 30, 2026)](https://github.blog/changelog/2026-07-30-github-models-is-now-retired/)
