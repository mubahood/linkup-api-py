"""
Unified recommend service (T-API-029).

The single seam through which every recommendation surface ranks candidates —
People-you-may-know (links), the Sparks deck, and feed ranking. Today the ranker
is the weighted-Jaccard Interest Graph scorer; isolating it here means the future
LightGBM / two-tower model (ARCHITECTURE.md §7.3) plugs in **one place** without
touching the call sites.

Pipeline: candidate-gen (done by the domain) → `rank()` → optional `explain()`.
"""
from __future__ import annotations

from backend.shared.scoring.interest_graph import (
    rank_candidates as _rank_candidates,
    get_compatibility_breakdown as _breakdown,
    score_pair as _score_pair,
)

# Re-export so call sites import the ranker from the recommend domain, not the
# low-level scoring module — the seam where the model implementation is swapped.
rank_candidates = _rank_candidates
score_pair = _score_pair


def rank(actor_id: str, candidate_ids: list[str], mode: str = 'professional') -> list[tuple[str, float]]:
    """Rank candidates for an actor in a given mode. Returns [(id, score), …]."""
    return _rank_candidates(actor_id, candidate_ids, mode=mode)


def explain(actor_id: str, candidate_id: str, mode: str = 'professional') -> dict:
    """Human-readable 'why you're seeing this' breakdown for one pair."""
    return _breakdown(actor_id, candidate_id, mode=mode)


def pct(score: float) -> int:
    """Normalise a 0–1 score to a 1–99 compatibility percentage for the UI."""
    return min(99, max(1, round((score or 0) * 100)))
