"""
Hubs service: slug generation, membership logic.
"""
import re
from backend.domains.hubs.models import Hub


def generate_slug(name: str) -> str:
    base = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    slug = base[:60]
    counter = 1
    while Hub.query.filter_by(slug=slug).first():
        slug = f'{base[:55]}-{counter}'
        counter += 1
    return slug
