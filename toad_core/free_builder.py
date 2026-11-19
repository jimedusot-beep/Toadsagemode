"""Zero-cost deterministic brief-to-app router.

This is an honest offline alternative to paid model inference: a strict,
bounded, explicit request interpreter, NOT a generative AI model.
It picks one of the reviewed app templates and rejects ambiguous or
unsupported capabilities instead of silently promising a custom app.
"""
from __future__ import annotations

import re

from .app_studio import AppStudio
from .schema import PackageError

MAX_BRIEF_BYTES = 1200
KINDS = (
    ("flashcards", re.compile(r"\b(?:flash[ -]?cards?|study[ -]?cards?)\b", re.I)),
    ("tasks", re.compile(r"\b(?:tasks?|to[ -]?dos?|check[ -]?lists?)\b", re.I)),
    ("notes", re.compile(r"\b(?:notes?|notebook|journals?)\b", re.I)),
)
# Not a safety classifier: conservative rule to prevent false claims about
# features that the reviewed offline templates do not provide.
UNSUPPORTED = (
    ("user accounts or login", r"\b(?:login|log[ -]?in|sign[ -]?in|accounts?|authentication|oauth)\b"),
    ("cloud sync or backend service", r"\b(?:sync|cloud|backend|server|realtime|real[ -]?time|database)\b"),
    ("online API or AI", r"\b(?:api|chatbot|llm|artificial intelligence|ai[ -]?powered)\b"),
    ("payments or storefront", r"\b(?:payments?|checkout|storefront|stripe|paypal|shopping)\b"),
    ("media or hardware integration", r"\b(?:camera|microphone|speech|audio|video|upload|robot|hardware)\b"),
    ("export or additional file formats", r"\b(?:pdf|excel|csv|download|export|import)\b"),
    ("advanced study scheduler", r"\b(?:spaced[ -]?repetition|sm[ -]?2|anki|automatic grading)\b"),
    ("multiplayer or collaborative editing", r"\b(?:multiplayer|collaborat(?:e|ion|ive)|shared editing)\b"),
)
_COMPILED_UNSUPPORTED = tuple(
    (label, re.compile(pattern, re.I)) for label, pattern in UNSUPPORTED
)


def interpret_brief(brief):
    """Return one unambiguous, supported app type without invoking a model."""
    if not isinstance(brief, str) or not brief.strip():
        raise PackageError("Free app request must be a nonempty text description")
    try:
        count = len(brief.encode("utf-8"))
    except UnicodeError as exc:
        raise PackageError("Free app request must be UTF-8") from exc
    if count > MAX_BRIEF_BYTES or any(ord(x) < 32 or ord(x) == 127 for x in brief):
        raise PackageError("Free app request exceeds 1200 bytes or contains control characters")
    unsupported = [label for label, pattern in _COMPILED_UNSUPPORTED if pattern.search(brief)]
    if unsupported:
        raise PackageError(
            "The free templates cannot implement: " + ", ".join(unsupported) +
            ". No app was generated. Simplify your request to offline tasks, notes or flashcards."
        )
    matches = [kind for kind, pattern in KINDS if pattern.search(brief)]
    if not matches:
        raise PackageError(
            "No supported app type found. Include the word tasks, notes or flashcards. "
            "This is a deterministic offline builder, not AI understanding."
        )
    if len(matches) > 1:
        raise PackageError(
            "More than one app type requested (" + ", ".join(matches) +
            "). Build and review one type at a time."
        )
    return {
        "kind": matches[0],
        "provider": "reviewed_template_only",
        "model_called": False,
        "paid_requests": 0,
        "supports_arbitrary_code": False,
        "constraints": "Offline, single-device localStorage only, no external APIs",
    }


def build_from_brief(workspace, brief, *, name, title=None, theme="forest"):
    plan = interpret_brief(brief)
    generated = AppStudio(workspace).create(
        name, kind=plan["kind"], title=title, theme=theme
    )
    return {
        "schema": "toad-free-brief-build-v1",
        "brief": brief.strip(),
        "selection": plan,
        "app": generated,
        "source": "deterministic_reviewed_template",
        "model_called": False,
        "paid_requests": 0,
        "deployed": False,
        "review_required": True,
    }
