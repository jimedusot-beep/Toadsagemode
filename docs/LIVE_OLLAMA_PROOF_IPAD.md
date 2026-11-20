# First REAL Toad Sage source proof — iPad-controlled, no laptop, no paid API

**Release state:** review-only draft. There is no provisioned Ollama cloud
host in the repository and no recorded real inference from this work.

This runner is a narrow bridge between an iPad-accessible trusted cloud
terminal and the already implemented Toad Sage AI web-source quarantine.
Unlike a test double in CI, a successful **operator-initiated** live run
must query Ollama on the host, freeze independent browser checks,
call the actual configured model once, validate its three source files,
and store their SHA-256-bound JSON record **without executing anything**.

## What is and is not proven

There are three intentionally separate statuses:

| Operation | Model request? | Output |
| --- | --- | --- |
| \`python tools/ai_live_proof.py\` | **No** | Read-only configuration status |
| \`python tools/ai_live_proof.py --probe\` | Ollama **/api/tags only** | Actual local model presence, **not inference** |
| \`TOAD_ALLOW_REAL_OLLAMA_PROOF=YES python tools/ai_live_proof.py --run\` | **One local Ollama /api/generate** | Private source record + operator-host receipt, if everything passes |

The live runner refuses any \`TOAD_MODEL_PROVIDER\` other than \`ollama\`,
and refuses an environment with \`TOAD_ALLOW_PAID_AI=YES\`. There is
**no paid API fallback**, OpenCode, remote HTTP endpoint, model download,
shell execution of model content, Docker worker or publication.

The receipt status is
\`live_ollama_manifest_received_quarantined_unverified\`.
That means a **source manifest** was received and saved by the actual
Ollama path, not that the generated code functions correctly, is
secure, has passed a browser test, or was independently attested.
The host/operator must still preserve truthful origin logs and never
substitute CI test-double output for a live receipt.

## Prepare from Safari on iPad

1. Review the branch and checks before using a cloud terminal:
   \`feature/live-ollama-quarantined-proof-20261119\`, based on
   \`feature/opt-in-cloud-ai-adapter-20261118\` (PR #30).
2. In Safari visit
   https://github.com/jimedusot-beep/Toadsagemode .
   Choose **Code → Codespaces → Create codespace on
   feature/live-ollama-quarantined-proof-20261119**. Make sure you
   select the development branch, not the old \`main\`.
   Codespace creation is a **user action** and may consume included
   compute/storage quota. Check billing, machine size, and limits first.
3. In the browser VS Code terminal, inspect the actual Python and
   available host resources (without installing anything):

       python --version
       free -h
       df -h
       command -v ollama || true

4. Run the **non-generating cold status**:

       python tools/ai_live_proof.py

   It must say \`not_run\`, \`model_response_received:false\`,
   \`candidate_executed:false\`, \`deployed:false\`.

5. Run the **local model registry probe**:

       python tools/ai_live_proof.py --probe

   A new Codespace normally has no configured Ollama model unless you
   independently installed/provisioned it. A \`model_unavailable\`
   result is **expected and correct** when there is no model. This
   does not mean the model was run. No models are fetched automatically.

6. **Only after** a trusted operator has explicitly installed Ollama
   and pulled a suitable local model **on that cloud machine**, the
   selected model appears in \`/api/tags\`, resource usage is acceptable
   and the user approves the one real inference call:

       TOAD_MODEL_PROVIDER=ollama TOAD_ALLOW_REAL_OLLAMA_PROOF=YES python tools/ai_live_proof.py --run

   \`TOAD_OLLAMA_MODEL\` may name an already-installed model. Default:
   \`qwen2.5-coder:1.5b\`. Only credential-free, loopback Ollama origins
   are accepted. The default adapter has a 30-second request deadline;
   slower CPU-only hosts may fail closed, not automatically retry.
   **Do not use a paid OpenAI API key for this step.**

7. A successful run writes a private
   \`live-ai-proofs/PROOF_ID.json\` alongside
   \`web-acceptance-plans/\`, \`web-acceptance-trials/\`,
   \`ai-web-drafts/\` in the private Toad Sage workspace (not in Git).
   The terminal prints bounded metadata, file hashes, plan/trial IDs
   and a receipt filename. **No generated source or secrets are printed
   by the live proof runner.**
8. Use the owner-only review controls documented in
   [Private iPad AI Draft Lab](PRIVATE_IPAD_AI_DRAFT_LAB.md) for
   text-only source review after its separate approval.
   Do not push private draft records or owner tokens into GitHub,
   issue comments, public Netlify pages or Codespace screenshots.
9. Stop your Codespace when finished to avoid consuming included
   core-hours and storage. Export *nonsecret* review metadata privately
   before removing a workspace; deletion may discard the files.

### First acceptance plan

The runner freezes the following **before** any model sees the goal:
- Browser document title = \`Flashcard Practice\`
- Click \`#flip\`; text in \`#answer\` contains \`Answer\`

These fixed, independently supplied checks are intentionally **not sent**
to the model. The draft response is stored as inert JSON only. The
runner calls the existing **dry** \`FrozenWebAcceptance.test\` method,
which must yield \`executed:false\`, \`passed:false\`,
\`receipt:null\`.

**Nothing in this runner evaluates the generated JavaScript.**
Actual WebKit execution is a later, separately authorized, live
containment-tested operation on a disposable, hardened Linux VM.
See [frozen test plans](FROZEN_WEB_ACCEPTANCE.md) and
[experimental browser worker](WEBKIT_LAB.md). A model-authored
candidate must not run inside the public iPad site or ordinary
GitHub Actions CI.

## What automated CI proves

\`tests/test_ai_live_proof.py\` runs without Ollama:
- Default status never probes, calls a model or creates files
- Provider \`openai\` and paid opt-in cannot trigger a proof
- Missing explicit opt-in prevents a model call
- A simulated unavailable model fails **without** creating a proof
- The non-generating probe never claims inference
- Frozen acceptance is created without a source draft
- Private proof receipts are exclusive-create and owner-only
- Workspace symlinks are rejected

**CI deliberately NEVER calls \`--run\`**. It cannot establish live
Ollama availability, local model memory requirements or a real app
from this runner. The first actual non-mock trial must be performed on
the operator's provisioned private host.

## Sources

- Existing model transport and no-remote-origin constraints:
  [models.py](../toad_core/models.py)
- Existing data-only source quarantine:
  [web_codegen.py](../toad_core/web_codegen.py)
- Existing freeze-before-generation acceptance records:
  [web_acceptance.py](../toad_core/web_acceptance.py)
- GitHub Codespaces browser creation:
  https://docs.github.com/en/codespaces/developing-in-a-codespace/creating-a-codespace-for-a-repository
- Codespaces included usage and billing:
  https://docs.github.com/en/codespaces/troubleshooting/troubleshooting-included-usage
- Ollama JSON generation API:
  https://docs.ollama.com/api/generate
- Ollama model list API:
  https://docs.ollama.com/api/tags
