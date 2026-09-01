"""
Shared X-App header → app_id resolution. LinkUp, Abanoonya Pro, and Uganda
Dating App share one backend and one accounts table, distinguished only by
this header — this is the single place that normalizes whatever a client
sends into the real app_id values ('linkup' | 'abanoonya' | 'uganda_dating')
used everywhere else (lu_accounts.app_id, lu_app_versions.app_id).
"""
from flask import request

_APP_IDS = {
    'linkup': 'linkup',
    'app.linkup.mobile': 'linkup',
    'abanoonya': 'abanoonya',
    'abanoonya.pro': 'abanoonya',
    'app.abanoonya.pro': 'abanoonya',
    'uganda_dating': 'uganda_dating',
    'ugandadating': 'uganda_dating',
    'app.ugandadating.app': 'uganda_dating',
}

# Apps that are dating-only (no Professional/LinkedIn-style surface at all).
# The single source of truth for that distinction — other modules should
# check membership here instead of re-testing `app_id == 'abanoonya'`.
DATING_ONLY_APP_IDS = frozenset({'abanoonya', 'uganda_dating'})

# The complete set of real (normalized) app_id values — for validating
# admin-supplied app_id input.
VALID_APP_IDS = frozenset(_APP_IDS.values())

# Canonical display name per normalized app_id — for anything that renders
# the brand name server-side (e.g. the hosted legal pages), keyed off the
# resolved app_id rather than the raw header value.
APP_DISPLAY_NAMES = {
    'linkup': 'LinkUp',
    'abanoonya': 'Abanoonya Pro',
    'uganda_dating': 'Uganda Dating App',
}


def resolve_app_id(header_value: str = None) -> str:
    """Normalize an X-App header (mobile clients) or ?app= query param
    (browser links, e.g. the hosted legal pages) to a known app_id. Defaults
    to 'linkup' for missing/unrecognized values — the original, established
    brand."""
    value = header_value if header_value is not None else (
        request.headers.get('X-App') or request.args.get('app'))
    return _APP_IDS.get((value or '').strip().lower(), 'linkup')
