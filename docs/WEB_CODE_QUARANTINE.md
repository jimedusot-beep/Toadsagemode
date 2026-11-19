# AI-authored web app source — quarantine-first prototype

**This is the first Toad Sage feature that allows an AI model to WRITE the
proposed contents of a web app** (HTML, CSS and JavaScript). It is NOT yet a
working autonomous app developer or an executable model-generated app.

Toad Sage's existing loopback-only Ollama adapter is the only configured live
model path. A model must first be installed and running on a compatible
**trusted host** (see [MISSIONS.md](MISSIONS.md)). Netlify's static site
cannot run Python or Ollama by itself.

## What happens when you request a custom app

```sh
python -m toad_core app draft-code "Build a simple original flashcard game with a flip button"
```

1. Toad Sage sends a bounded prompt to its configured local model.
2. The model returns one JSON manifest declaring **exactly** three file
   contents: `index.html`, `styles.css`, `app.js`. No other file
   paths, dependencies, scripts or permissions are accepted.
3. Toad Sage validates the shape and source sizes, then performs a **text
   only** scan for risky APIs, external URLs, dynamic evaluation,
   HTML injection and script patterns. The scan is heuristic; a clean
   report does not mean that generated code is safe.
4. Toad Sage saves the complete model response as a **JSON data record**
   in the private workspace's `ai-web-drafts/` folder; no runnable HTML,
   CSS, JavaScript or ZIP is extracted.
5. The output is always `quarantined_unverified` and `release_allowed:
   false`. The model cannot change this state, even if it claims testing
   or deployment succeeded.
6. No browser, shell, Docker candidate, network request, Netlify deployment,
   Git push, or H.E.R.B.I.E. hardware action is performed.

The report includes per-file SHA-256 values, the full draft digest,
source classification, risks to inspect, explicit `executed:false`,
`tested:false`, `deployed:false`, and the independent-JavaScript-worker
requirement.

### Review the proposal without execution

```sh
python -m toad_core app code-report DRAFT_ID
python -m toad_core app code-show DRAFT_ID
```

`code-report` displays only digests, risk hints and gate status.
`code-show` emits the raw model-proposed source as JSON **data** so you
can read it. Neither command writes or executes `.html`, `.css`,
or `.js` files. Do not paste it into a web console or deploy it.

The private draft record uses exclusive create (no overwrite),
POSIX owner-only file permissions, a bounded maximum of 100 drafts, and
a content hash checked before every read. There is no current
`code-run`, `code-approve`, `code-export` or `code-deploy` command:
their omission is a deliberate security barrier, not a missing menu.

## Difference from the two safe template apps

| Capability | AI app blueprint | AI code draft |
| --- | --- | --- |
| Model chooses app requirements | Yes | Yes |
| Can choose task or notes app | Yes | Can propose any static site |
| Model writes executable HTML/CSS/JS | **No** | **Yes, as quarantined strings** |
| Direct output: reviewable app ZIP | Only with owner-approved template build | No |
| JavaScript execution on host or browser | Trusted templates tested in CI | **Never** |
| Automatically deployable to Netlify | No | **No** |
| Security status | Trusted template, specific build unverified | Untrusted and unverified |

A draft may contain accidental bugs, unsafe source, hallucinated features,
or intentionally malicious instructions. A test double showing that the
quarantine stores strings correctly does not establish model quality.

## Remaining gates for genuinely autonomous applications

Before Toad Sage can build arbitrary AI-authored apps that are safe enough
to preview and release, we still need:

1. A dedicated restrictive browser test worker separate from GitHub's
   trusted-code WebKit tests. It must run generated code with no host
   credentials or privileged filesystem access, bounded time/resources,
   isolated origin, network blocking and cleanup evidence.
2. Independent acceptance tests fixed **before** the model generates code,
   plus pass/fail receipts tied to source digests.
3. A human review screen showing source differences, risky APIs,
   unmet requirements and test results.
4. A separate owner-approved export/Netlify release action, with a
   staging URL and rollback/fix-forward plan.
5. A live Ollama or other explicitly authorized model service accessible
   in an authenticated, isolated backend. The current Netlify site is
   a **static frontend**; never embed a secret AI key or expose the local
   Ollama port publicly to bypass setup.

## Evidence

- `tests/test_web_codegen.py`: uses explicit model doubles; asserts
  valid and malicious-looking source stays inert JSON, refuses unsafe
  file paths, extra fields, oversized content and symlinks, verifies
  digests and draft limits.
- Existing GitHub Actions WebKit tests **do not** run these drafts.
  They only exercise trusted code from the reviewed templates.
- A real model has **not** successfully generated a source draft in the
  project's environment, and no model-generated app has been deployed.

References:
- [Tao Sage model adapter](../toad_core/models.py)
- [AI blueprint workflow](AI_APP_BLUEPRINTS.md)
- [Restricted local lab](LAB.md)
- [Ollama structured JSON output](https://docs.ollama.com/api/generate)
