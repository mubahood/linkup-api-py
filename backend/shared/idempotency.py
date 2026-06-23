"""
Idempotency-Key support for write endpoints (T-API-045).

Per `ARCHITECTURE.md §14` / `PROJECT_BRIEFING.md §6.3.15`, writes should accept an
`Idempotency-Key` header so a retried request (flaky 3G is the norm in the target
market) does not repeat an irreversible side-effect — a duplicate spark, a double
job application, a re-sent message, a double wallet credit.

Usage — place `@idempotent` BELOW the auth decorator (which injects `account`):

    @bp.route('/action', methods=['POST'])
    @lu_jwt_required
    @idempotent
    def action(account):
        ...

Behaviour:
  • No `Idempotency-Key` header, or non-write method → pass through untouched.
  • First call with a key → execute; if the response is success (2xx), store
    (account_id, key) → (status, body) for 24h.
  • Repeat call with the same key → replay the stored response verbatim; the
    handler never runs again, so the side-effect happens exactly once.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import request, make_response, Response

from backend.models import db

_TTL_HOURS = 24


class IdempotencyKey(db.Model):
    __tablename__ = 'lu_idempotency_keys'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = db.Column(db.String(36), nullable=False)
    idem_key = db.Column(db.String(255), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    path = db.Column(db.String(500), nullable=False)
    status_code = db.Column(db.Integer, nullable=False, default=200)
    response_body = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('account_id', 'idem_key', name='uq_account_idem_key'),
    )


def idempotent(fn):
    @wraps(fn)
    def wrapper(account, *args, **kwargs):
        key = request.headers.get('Idempotency-Key')
        if not key or request.method not in ('POST', 'PUT', 'DELETE'):
            return fn(account, *args, **kwargs)

        now = datetime.utcnow()
        existing = IdempotencyKey.query.filter_by(
            account_id=account.id, idem_key=key
        ).first()
        if existing:
            if existing.expires_at and existing.expires_at < now:
                db.session.delete(existing)
                db.session.commit()
            else:
                # Replay the original response verbatim — handler never re-runs.
                resp = Response(existing.response_body or '',
                                status=existing.status_code,
                                mimetype='application/json')
                resp.headers['Idempotent-Replay'] = 'true'
                return resp

        rv = fn(account, *args, **kwargs)
        resp = make_response(rv)

        # Only persist successful, committed results so a failed first attempt
        # can still be legitimately retried.
        if 200 <= resp.status_code < 300:
            try:
                db.session.add(IdempotencyKey(
                    account_id=account.id, idem_key=key,
                    method=request.method, path=request.path,
                    status_code=resp.status_code,
                    response_body=resp.get_data(as_text=True),
                    created_at=now, expires_at=now + timedelta(hours=_TTL_HOURS),
                ))
                db.session.commit()
            except Exception:
                db.session.rollback()
        return resp
    return wrapper
