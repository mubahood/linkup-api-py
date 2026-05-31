"""
Interest Graph scoring engine — Phase 0 implementation.

Uses weighted Jaccard similarity across the 8 Interest Graph dimensions.
No pgvector required: works with the existing MySQL lu_interest_profiles table.

Dimension weights (tuned for Phase 0; should become ML-trained in Phase 2):
  professional_domain   — heaviest weight for professional surface
  education_affiliation — strong signal (shared school/cohort = strong tie)
  geography_mobility    — proximity matters in Uganda context
  hobbies_passions      — meaningful for both surfaces
  causes_values         — high signal for matching (alignment on what matters)
  lifestyle             — moderate signal for dating surface
  personality_working_style — good for professional collaboration
  relationship_intent   — dating only; high signal
"""

from __future__ import annotations
from typing import Optional
from backend.models import db
from backend.domains.interest.models import InterestProfile, InterestTag

# --- Dimension weights ---------------------------------------------------
# Tune these numbers to shift recommendation behavior.
# Sum need not equal 1.0; scores are normalized after weighting.

_PROFESSIONAL_DIM_WEIGHTS: dict[str, float] = {
    'professional_domain':        3.0,
    'education_affiliation':      2.5,
    'geography_mobility':         2.0,
    'causes_values':              1.5,
    'personality_working_style':  1.5,
    'hobbies_passions':           1.0,
    'lifestyle':                  0.5,
    'relationship_intent':        0.0,  # never used on professional surface
}

_DATING_DIM_WEIGHTS: dict[str, float] = {
    'relationship_intent':        4.0,
    'causes_values':              2.5,
    'lifestyle':                  2.5,
    'hobbies_passions':           2.0,
    'geography_mobility':         2.0,
    'education_affiliation':      1.0,
    'personality_working_style':  1.0,
    'professional_domain':        0.5,
}


def _load_profile(account_id: str) -> dict[str, dict[str, float]]:
    """
    Load an account's interest weights, indexed by dimension and tag_id.
    Returns: {dimension: {tag_id: weight}}
    """
    rows = (
        db.session.query(InterestProfile, InterestTag)
        .join(InterestTag, InterestProfile.tag_id == InterestTag.id)
        .filter(InterestProfile.account_id == account_id)
        .all()
    )
    profile: dict[str, dict[str, float]] = {}
    for ip, tag in rows:
        dim = tag.dimension
        if dim not in profile:
            profile[dim] = {}
        profile[dim][tag.id] = float(ip.weight or 0.5)
    return profile


def _dim_overlap(tags_a: dict[str, float], tags_b: dict[str, float]) -> float:
    """
    Weighted Jaccard similarity for one dimension.
    score = sum(min(w_a, w_b)) / sum(max(w_a, w_b)) over all tags in union
    Returns 0.0 if both empty, 1.0 if identical.
    """
    all_tags = set(tags_a) | set(tags_b)
    if not all_tags:
        return 0.0
    numerator = sum(min(tags_a.get(t, 0.0), tags_b.get(t, 0.0)) for t in all_tags)
    denominator = sum(max(tags_a.get(t, 0.0), tags_b.get(t, 0.0)) for t in all_tags)
    return numerator / denominator if denominator > 0 else 0.0


def score_pair(
    account_a_id: str,
    account_b_id: str,
    mode: str = 'professional',
    profile_a: Optional[dict] = None,
    profile_b: Optional[dict] = None,
) -> float:
    """
    Compute a 0–1 Interest Graph compatibility score between two accounts.

    Args:
        account_a_id: ID of the first account (the viewer/actor)
        account_b_id: ID of the second account (the candidate)
        mode: 'professional' or 'dating'
        profile_a / profile_b: pre-loaded profiles (avoids DB hit if already loaded)

    Returns:
        float in [0, 1] — higher = more compatible
    """
    pa = profile_a or _load_profile(account_a_id)
    pb = profile_b or _load_profile(account_b_id)

    weights = _PROFESSIONAL_DIM_WEIGHTS if mode == 'professional' else _DATING_DIM_WEIGHTS

    total_weight = 0.0
    weighted_score = 0.0

    all_dims = set(pa) | set(pb) | set(weights)
    for dim in all_dims:
        w = weights.get(dim, 0.5)
        if w <= 0:
            continue
        overlap = _dim_overlap(pa.get(dim, {}), pb.get(dim, {}))
        weighted_score += w * overlap
        total_weight += w

    return (weighted_score / total_weight) if total_weight > 0 else 0.0


def rank_candidates(
    actor_id: str,
    candidate_ids: list[str],
    mode: str = 'professional',
) -> list[tuple[str, float]]:
    """
    Rank a list of candidate account IDs by Interest Graph compatibility with actor.
    Returns sorted list of (account_id, score) pairs, highest score first.
    Loads all profiles in a single batch query for efficiency.
    """
    if not candidate_ids:
        return []

    all_ids = [actor_id] + candidate_ids
    rows = (
        db.session.query(InterestProfile, InterestTag)
        .join(InterestTag, InterestProfile.tag_id == InterestTag.id)
        .filter(InterestProfile.account_id.in_(all_ids))
        .all()
    )

    # Build profile map: {account_id: {dimension: {tag_id: weight}}}
    profiles: dict[str, dict[str, dict[str, float]]] = {}
    for ip, tag in rows:
        aid = ip.account_id
        dim = tag.dimension
        if aid not in profiles:
            profiles[aid] = {}
        if dim not in profiles[aid]:
            profiles[aid][dim] = {}
        profiles[aid][dim][tag.id] = float(ip.weight or 0.5)

    actor_profile = profiles.get(actor_id, {})

    scored = []
    for cid in candidate_ids:
        s = score_pair(
            actor_id, cid,
            mode=mode,
            profile_a=actor_profile,
            profile_b=profiles.get(cid, {}),
        )
        scored.append((cid, s))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def get_compatibility_breakdown(
    account_a_id: str,
    account_b_id: str,
    mode: str = 'professional',
) -> dict:
    """
    Return a human-readable breakdown of compatibility by dimension.
    Used for the "why this person" explainability feature.
    """
    pa = _load_profile(account_a_id)
    pb = _load_profile(account_b_id)
    weights = _PROFESSIONAL_DIM_WEIGHTS if mode == 'professional' else _DATING_DIM_WEIGHTS

    breakdown = []
    for dim, w in sorted(weights.items(), key=lambda x: -x[1]):
        if w <= 0:
            continue
        overlap = _dim_overlap(pa.get(dim, {}), pb.get(dim, {}))
        shared_tags = set(pa.get(dim, {})) & set(pb.get(dim, {}))
        breakdown.append({
            'dimension': dim,
            'overlap': round(overlap, 3),
            'weight': w,
            'contribution': round(overlap * w, 3),
            'shared_tag_ids': list(shared_tags)[:5],
        })

    total = score_pair(account_a_id, account_b_id, mode, pa, pb)
    return {
        'total_score': round(total, 3),
        'mode': mode,
        'dimensions': breakdown,
    }
