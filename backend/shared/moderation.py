"""
Content-moderation hooks (T-API-072).

Defines the seams where the models from `ARCHITECTURE.md §7.3` (harassment-text
classifier, NSFW vision model) will plug in. For now they are **pass-through**
interfaces with a tiny built-in heuristic so the call sites, return contract, and
review flow exist and are exercised — swap the bodies for real models later
without touching callers.

Contract: each `screen_*` returns `{'flagged': bool, 'reason': str|None,
'score': float}`. Callers decide what to do with a flag (queue for review,
soft-warn, block) — the hooks never raise.
"""
from __future__ import annotations

# Minimal placeholder lexicon — real deployment uses a multilingual classifier.
_ABUSE_TERMS = {'kill you', 'hate you', 'stupid idiot', 'scammer', 'fraudster'}


def screen_text(text: str | None) -> dict:
    """Screen a user-generated text (message, bio, prompt) for abuse/harassment."""
    if not text:
        return {'flagged': False, 'reason': None, 'score': 0.0}
    lowered = text.lower()
    for term in _ABUSE_TERMS:
        if term in lowered:
            return {'flagged': True, 'reason': 'possible_harassment', 'score': 0.9}
    return {'flagged': False, 'reason': None, 'score': 0.0}


def screen_image(url: str | None) -> dict:
    """Screen an uploaded image for NSFW/unsafe content (placeholder: allow)."""
    return {'flagged': False, 'reason': None, 'score': 0.0}
