# Empathy learning implementation

User-authorized scope: extend the existing empathy examples into a local-first,
phone-usable learning library without requiring the Acer, a model or Docker.

Use a portable `toad-empathy-library-v2` envelope containing versioned lessons.
Keep the original v1 examples unchanged and migrate them on explicit import.
Preserve unknown fields. Each lesson records audience, situation, attribution,
rights, material, technique, helpful behavior, counterexample, original response,
limitations, human review, evaluations and revision history. Imported approval
claims are data, never local review authority. Corrections invalidate approval.

Python stores lessons in the existing private SQLite workspace, separate from
executable abilities. The browser uses a separate bounded localStorage catalog
and explicit backup/import. Feed Inbox entries can be copied into this library;
the original feed remains. Render previews as text. No automatic uploads.

Retrieve only helpful lessons explicitly reviewed on this device, filtered by
audience and deterministic word overlap. Keep lesson text as JSON reference data
under a fixed policy. Model output is untrusted display text, never a tool call.
Prompt separation mitigates injection; it cannot prove model obedience.

Provide paired baseline/retrieval generation through the existing loopback-only
Ollama adapter. Do not make model calls on the public website. Twenty original
practice scenarios plus ten separate held-out scenarios cover ten domains. Do
not index scenarios as lessons. Human rubric ratings are separate from automated
checks; generate no automatic empathy score or improvement claim. A phone user
can paste both responses and record a paired human assessment without a model.

Tests cover migration/unknown data, forged reviews, correction invalidation,
audience/retrieval boundaries, bounded inputs, transactional failure, model
failure, paired prompting, scenario separation, persistent mobile review/edit,
backup round trip, inert markup and storage errors. Static deployment uses an
explicit allowlist of public code and original practice data, excluding held-out
data and all private runtime storage. Ship a guide and disclose live Ollama and
physical iPhone limits.
