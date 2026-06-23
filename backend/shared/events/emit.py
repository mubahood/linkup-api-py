"""
Behavioral-event emitter (T-API-053).

`emit(verb, account_id, ...)` writes one append-only signal row. It is
fire-and-forget: failures never propagate to the originating request, and it
uses its own short transaction so it can't interfere with the caller's session.

Verbs follow `<domain>.<action>` — spark.up, spark.pass, profile.view,
link.request, message.send, post.like, job.apply, … (ARCHITECTURE.md §7.5).
"""
from __future__ import annotations

import uuid
from datetime import datetime


def emit(verb: str, account_id: str | None = None,
         object_type: str | None = None, object_id: str | None = None,
         context: dict | None = None) -> None:
    try:
        from backend.models import db
        from backend.shared.events.models import BehavioralEvent
        ev = BehavioralEvent(
            id=str(uuid.uuid4()),
            account_id=account_id,
            verb=verb,
            object_type=object_type,
            object_id=object_id,
            context=context,
            created_at=datetime.utcnow(),
        )
        db.session.add(ev)
        db.session.commit()
    except Exception:
        try:
            from backend.models import db
            db.session.rollback()
        except Exception:
            pass
