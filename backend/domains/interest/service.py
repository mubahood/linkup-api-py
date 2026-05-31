"""
Interest service: taxonomy, suggestion logic.
"""
from backend.domains.interest.models import InterestTag, InterestProfile


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
