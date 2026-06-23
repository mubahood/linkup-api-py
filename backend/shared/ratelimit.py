"""
Lightweight in-memory rate limiting (T-API-071).

A sliding-window limiter with no external dependency — suitable for the single
dev/process deployment now; swap the backing store for Redis when `T-API-061`
lands (the decorator API stays the same).

Keyed by account id for authed routes, or by an explicit field (e.g. phone) for
unauthenticated ones — never by IP alone, so many dummy accounts behind one
localhost don't throttle each other. Over-limit returns a clean JSON envelope
with HTTP 429.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from functools import wraps

from flask import request, jsonify

_buckets: dict[str, deque] = defaultdict(deque)


def _resolve_key(args, body_field):
    # Authed routes pass the Account as the first positional arg.
    if args and hasattr(args[0], 'id'):
        return str(args[0].id)
    if body_field:
        data = request.get_json(silent=True) or {}
        val = (data.get(body_field) or '').strip()
        if val:
            return f'{body_field}:{val}'
    return f'ip:{request.remote_addr}'


def rate_limit(max_calls: int, per_seconds: int, body_field: str | None = None):
    """Allow `max_calls` per `per_seconds` window per caller key."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = f'{fn.__name__}:{_resolve_key(args, body_field)}'
            now = time.time()
            dq = _buckets[key]
            cutoff = now - per_seconds
            while dq and dq[0] <= cutoff:
                dq.popleft()
            if len(dq) >= max_calls:
                retry = int(per_seconds - (now - dq[0])) + 1
                return jsonify({
                    'code': 0,
                    'message': f'Too many requests. Please try again in {retry}s.',
                }), 429
            dq.append(now)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
