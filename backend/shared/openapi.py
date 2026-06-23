"""
OpenAPI 3.0 spec generation from the live Flask URL map (T-API-037).

No external dependency: introspects `app.url_map` to emit a path/method catalog
the mobile team can import into Postman/Swagger. It is intentionally
schema-light (paths, methods, params, auth hint) — richer request/response
schemas can be layered on later with flask-smorest if desired.
"""
from __future__ import annotations

import re

# Converts Flask's <converter:name> path params to OpenAPI's {name}.
_PARAM_RE = re.compile(r'<(?:[^:<>]+:)?([^<>]+)>')


def _to_openapi_path(rule: str) -> tuple[str, list]:
    params = _PARAM_RE.findall(rule)
    path = _PARAM_RE.sub(lambda m: '{' + m.group(1) + '}', rule)
    return path, params


def _tag_for(path: str) -> str:
    parts = [p for p in path.split('/') if p and not p.startswith('{')]
    # /v1/<domain>/... → domain
    if len(parts) >= 2 and parts[0] == 'v1':
        return parts[1]
    if parts and parts[0] == 'v1':
        return 'root'
    return parts[0] if parts else 'misc'


def generate_spec(app) -> dict:
    paths: dict = {}
    tags: set = set()

    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        raw = str(rule)
        if not (raw.startswith('/v1') or raw.startswith('/api')):
            continue
        path, params = _to_openapi_path(raw)
        methods = sorted(m for m in rule.methods if m in {'GET', 'POST', 'PUT', 'DELETE', 'PATCH'})
        if not methods:
            continue
        tag = _tag_for(path)
        tags.add(tag)
        path_item = paths.setdefault(path, {})
        for method in methods:
            op = {
                'tags': [tag],
                'summary': f'{method} {path}',
                'operationId': f'{method.lower()}_{rule.endpoint}',
                'responses': {
                    '200': {'description': 'Success — `{code:1, message, data}`'},
                    '400': {'description': 'Error — `{code:0, message}`'},
                },
            }
            if params:
                op['parameters'] = [
                    {'name': p, 'in': 'path', 'required': True, 'schema': {'type': 'string'}}
                    for p in params
                ]
            # Heuristic auth hint: everything except auth/health/public is bearer-auth.
            if not any(x in path for x in ('/auth/login', '/auth/register', '/auth/otp',
                                           '/health', '/reference', '/safety/location')):
                op['security'] = [{'bearerAuth': []}]
            path_item[method.lower()] = op

    return {
        'openapi': '3.0.3',
        'info': {
            'title': 'LinkUp API',
            'version': '1.0.0',
            'description': 'Uganda-first professional + dating network. '
                           'Envelope: `{code:1|0, message, data}`. Auth: Bearer JWT.',
        },
        'servers': [{'url': 'http://localhost:5001'}],
        'tags': [{'name': t} for t in sorted(tags)],
        'components': {
            'securitySchemes': {
                'bearerAuth': {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'}
            }
        },
        'paths': dict(sorted(paths.items())),
    }
