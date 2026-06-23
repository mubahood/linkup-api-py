"""
JSON-safety helpers (T-API-041).

MySQL `JSON` columns can end up holding a JSON *string* instead of a JSON
*object* when something double-encodes a value before insert (see defect D-2:
`json.dumps()` passed to a JSON column). SQLAlchemy then hands domain code a
plain `str`, and any `.get(...)` call on it raises
`AttributeError: 'str' object has no attribute 'get'`.

`as_obj()` is the single, defensive way to read any JSON-object column: it always
returns a `dict`, regardless of whether the stored value was an object, a
(possibly multiply-) encoded string, or NULL.

Prefer the model properties (`Account.modes`, `Account.notif_prefs`) in domain
code; use `as_obj()` directly only for ad-hoc JSON fields that lack an accessor.
"""
from __future__ import annotations

import json
from typing import Any


def as_obj(value: Any) -> dict:
    """Coerce a JSON-column value into a dict. Never raises.

    Handles: dict (returned as-is), JSON-encoded string (decoded, even if
    encoded more than once), None/empty, and unexpected types (-> {}).
    """
    # Unwrap up to a few layers of accidental string-encoding.
    for _ in range(5):
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return {}
            try:
                value = json.loads(s)
                continue
            except (ValueError, TypeError):
                return {}
        # any other type (None, list, int, ...) is not a JSON object
        return {}
    return value if isinstance(value, dict) else {}
