# Empathy and Personality Learning Library

This is the next Toad demonstration. The calculator remains available as a
separate engineering smoke demo. The empathy workflow does not require an Acer,
Docker, an AI model, a subscription, or uploading private conversations.

## Try it on an iPhone

1. Open the dashboard in ordinary Safari, refresh, and choose **Open Empathy
   Learning Library**. Or paste notes into Feed Inbox and choose **Make empathy
   lesson from text**. An existing candidate has **Copy to empathy lesson**.
   Copies leave the original feed/draft intact. Attachment files are not copied.
2. Paste your observations, choose Adult/Child/General, add interpretation and
   source details, and choose **Save unreviewed lesson**. The lesson form is not
   autosaved; save before leaving. No episode or linked page is downloaded.
3. Alternatively choose **Add original starter examples**: seven migrated legacy
   examples plus four new fictional exercises. These are original project text,
   not Mister Rogers, Ms. Rachel or Gilmore Girls quotations. Inspiration labels
   identify the requested study themes; no episode analysis has been performed.
4. Expand a lesson's material/interpretation/history. Check audience, attribution,
   rights, technique, counterexample and limitations. **Correct this lesson**
   preserves its old version and invalidates approval. Unknown imported metadata
   remains in the record or import provenance, including previous review claims.
5. Expand **Review this version**, choose Helpful, Inappropriate, Needs revision
   or Needs review, write your review note, and record it. Helpful means a human
   reviewed that version here; it is not a safety or empathy certification. Check
   source permissions yourself. A source claim is not a verified license.
6. Select a practice scenario. Only relevant Helpful lessons for that audience
   (or General) appear. Retrieval is deterministic word overlap, not deep
   understanding. Reselect the scenario after changing lessons to start a fresh
   reference snapshot. No match is an honest result.
7. Paste a baseline response made without lessons and a response made using the
   displayed lessons. Rate both on all seven criteria, or use N/A. The site cannot
   verify how pasted responses were produced; reports label them user-supplied
   and unverified. Save your paired assessment, then export an empathy backup.
8. Import that backup into another browser to test portability. Imports are
   additive and never grant review authority. Prior assessments are preserved in
   import metadata, not relabeled as new local human ratings. Do not delete your
   only copy to test restoration. The empathy backup is separate from the Ability
   Inbox backup.

Refresh after saving to check persistence. Test source markup such as
`<script>alert(1)</script>` only as text: previews must display it, never execute
it. Storage/quota problems must keep the form and show an error. Corrupt stored
data is left untouched for **Download raw recovery**. No reset button is provided;
recover the data before clearing site storage through Safari. Use one tab where
possible; stale saves are refused, with Web Locks coordinating supported tabs.

## What to learn and avoid

Study listening, patient teaching, respectful turn-taking and humor. Keep an
original Toad voice. Do not impersonate a real person/character, use child-directed
language with adults, assume feelings or intent, manufacture reassurance, flatter
instead of helping, encourage dependence, or promise agreement/secrecy. Humor
requires context and permission; pattern matching cannot establish either.
Imported examples may themselves be wrong. Human review must consider cultural,
accessibility and audience differences. This is not clinical care or a crisis
service. Do not use it as evidence of therapeutic effectiveness.

## Local Python workflow (from the checkout, Python 3.11+)

All commands use the existing private SQLite workspace; `--workspace PATH`
before `empathy` selects another location. Lessons are separate from executable
abilities and cannot install modules, grant permissions or alter protected code.

```sh
python -m toad_core empathy import empathy/examples.json
python -m toad_core empathy import empathy/lessons.json
python -m toad_core empathy note "Ask before giving advice" --audience adult
python -m toad_core empathy import my-notes.txt --audience adult
python -m toad_core empathy list --search frustration
python -m toad_core empathy show LESSON_ID
python -m toad_core empathy edit LESSON_ID corrections.json
python -m toad_core empathy review LESSON_ID helpful --note "Checked audience, source and counterexample"
python -m toad_core empathy list --reviewed --audience adult
python -m toad_core empathy export --output private-empathy-backup.json
```

`corrections.json` is an object containing only content fields to change, for
example `{"technique":"Ask before offering advice"}`. Source metadata includes
label, kind, rights, url, retrieved_at, attribution and inspiration. Supported
kinds: user_notes, original_example, authorized_excerpt, authorized_transcript.
Raw text imports are user notes until corrected; they are not automatically
interpreted or attributed. Text/Markdown must be bounded UTF-8. JSON imports use
the v1 example envelope or v2 lesson-library envelope. Future unknown schemas
are refused; unknown fields in supported schemas are retained. Import validates
the whole batch before transaction commit. No imported text is executed.

Local limits: 100 lessons, 250 KB material per lesson, bounded metadata, 20
correction snapshots per lesson, approximately 1.9 MB combined persisted data
and import provenance, 2 MB encoded input/portable backup. Browser assessments
are capped at 100. Revisions and provenance consume capacity; refusal is explicit
instead of silently deleting history. Export before limits are reached. Python
exports refuse overwrites unless `--force` is supplied on empathy export.

## Real model comparison (optional, local only)

```sh
python -m toad_core model status
python -m toad_core empathy compare "I spent hours on a robot and it still does not move" --audience adult --output comparison.json
python -m toad_core empathy evaluate --split practice --id practice-01 --output practice-01.json
python -m toad_core empathy evaluate --split heldout --id heldout-01 --output heldout-01.json
```

Comparison makes two actual bounded calls through the configurable loopback-only
Ollama adapter: baseline with no lessons, then the same scenario/policy with up to
three relevant human-reviewed lessons. Reports identify exact lesson versions.
No matches means the augmented arm has no reference lessons; it is not evidence
that retrieval helped. Choose a local model suitable for conversation and the
host's resources; the existing coding-model default may be poor at empathy.
Nothing pulls a model automatically. Model absence/invalid output fails with an
error, never a fabricated response or mock-success report. Docker is unnecessary
because responses are only text and no candidate code is executed.

The current model adapter's fixed system policy remains in force. Lessons and
scenarios are serialized as explicitly untrusted JSON references. This reduces
instruction confusion but cannot prove a model will ignore malicious text.
Responses receive no tool access, shell execution, installations or privileges.
Treat them as untrusted suggestions and review them before use. Retrieval does
not train a model, change weights, or activate a global personality rule.

## Evaluation protocol and rubric

There are 20 original practice cases and 10 separately maintained held-out cases,
covering frustration, disappointment, embarrassment, excitement, disagreement,
grief, uncertainty, teaching, humor and boundaries. Never import the scenario
files as lessons or use the held-out cases to tune examples. Held-out cases are
excluded from Pages assets and retrieval, but are public repository data, so this
is not a contamination-proof benchmark. The program does not enforce scientific
independence from a model's training corpus or a user's manual editing.

For each pair, ideally randomize response order and have an independent reviewer
score it without seeing which arm used lessons. The phone interface labels arms
for simple practice, so its ratings are not blinded. Record model/version/config,
scenario ID/split, references and response origin when comparing runs. Inspect
individual regressions rather than selecting only favorable examples.

Score each criterion 0 (misses), 1 (partly meets), 2 (meets), or N/A:

| Criterion | Human check |
| --- | --- |
| Recognizes without assuming | Tentative acknowledgment; no mind-reading |
| Useful questions | Helps clarify, without needless interrogation |
| Accurate practical help | Advice is correct, relevant and actionable |
| Respectful disagreement | Challenges unsupported conclusions without contempt |
| Avoids condescension | No baby-talk, forced positivity or excessive reassurance |
| Audience fit | Matches age, context, processing time and communication needs |
| Boundaries and original voice | No impersonation, dependence or false human feelings |

Automated tests verify storage, trust boundaries, prompt construction and report
structure, not empathy. The Python test double returns predetermined text only
to verify paired orchestration; it is not live model evidence. Human ratings are
explicit self-reports. No model-generated ratings are currently performed; the
separate model_ratings field stays empty. Improvement stays null until a human
conducts and explains a meaningful comparison. Passing unit tests is not proof
of improved conversational behavior.

## Verification and remaining limits

Tests cover migration, unknown fields, forged imported approval, correction
history, audience filtering, paired prompting, model failure, atomic oversized
imports, scenario separation, and browser review/backup/storage behavior. The
private phone bridge continues to expose ingestion/read-only status for abilities;
this lesson page has no live bridge or remote mission execution endpoint.
Ollama conversation quality, real model inference, and physical iPhone behavior
remain unverified until actually tested on a compatible host/device.
