"""
Interest service: taxonomy, suggestion logic, weight decay.
"""
from datetime import datetime
from backend.domains.interest.models import InterestTag, InterestProfile


# Default decay rate: 2% per month (per CORE_DATA_MODEL.md §4.3)
DEFAULT_DECAY_RATE = 0.02


def apply_decay(ip: 'InterestProfile') -> float:
    """
    Calculate the decayed weight for an InterestProfile.
    Decay formula: w * (1 - rate)^months_since_last_signal
    Pinned interests never decay. Explicit (user-declared) interests decay at half rate.
    Returns the decayed weight (does NOT persist — call this on read for display).
    """
    if ip.pinned:
        return float(ip.weight or 0.5)

    last_signaled = ip.last_signaled or ip.created_at
    if not last_signaled:
        return float(ip.weight or 0.5)

    months_elapsed = max(0.0, (datetime.utcnow() - last_signaled).days / 30.0)
    rate = DEFAULT_DECAY_RATE if ip.source != 'explicit' else DEFAULT_DECAY_RATE / 2
    decayed = float(ip.weight or 0.5) * ((1 - rate) ** months_elapsed)
    return max(0.01, round(decayed, 4))  # never go fully to zero


def get_taxonomy() -> dict:
    """Return all tags grouped by dimension."""
    tags = InterestTag.query.order_by(InterestTag.dimension, InterestTag.popularity.desc()).all()
    taxonomy = {}
    for tag in tags:
        dim = tag.dimension
        if dim not in taxonomy:
            taxonomy[dim] = []
        taxonomy[dim].append(tag.to_dict())
    return taxonomy


def get_suggestions(account_id: str, limit: int = 10) -> list:
    """Suggest interest tags based on existing profile interests."""
    # Get dimensions that account already has
    existing = InterestProfile.query.filter_by(account_id=account_id).all()
    existing_tag_ids = {ip.tag_id for ip in existing}
    existing_dims = set()
    for ip in existing:
        if ip.tag:
            existing_dims.add(ip.tag.dimension)

    # Suggest popular tags in same dimensions not yet selected
    suggestions = []
    if existing_dims:
        suggestions = InterestTag.query.filter(
            InterestTag.dimension.in_(existing_dims),
            ~InterestTag.id.in_(existing_tag_ids) if existing_tag_ids else True
        ).order_by(InterestTag.popularity.desc()).limit(limit).all()

    # If still less than limit, fill with popular tags from any dimension
    if len(suggestions) < limit:
        more = InterestTag.query.filter(
            ~InterestTag.id.in_(existing_tag_ids | {t.id for t in suggestions}) if (existing_tag_ids or suggestions) else True
        ).order_by(InterestTag.popularity.desc()).limit(limit - len(suggestions)).all()
        suggestions.extend(more)

    return [t.to_dict() for t in suggestions]
