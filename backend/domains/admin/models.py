"""
Admin domain models: AdminAuditLog.
"""
import uuid
from datetime import datetime
from backend.models import db


class AdminAuditLog(db.Model):
    __tablename__ = 'lu_admin_audit_log'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_id = db.Column(db.String(36), db.ForeignKey('lu_accounts.id', ondelete='CASCADE'), nullable=False)
    action = db.Column(db.String(60), nullable=False)
    target_account_id = db.Column(db.String(36), nullable=True)
    detail = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'admin_id': self.admin_id,
            'action': self.action,
            'target_account_id': self.target_account_id,
            'detail': self.detail,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


def log_admin_action(admin_id: str, action: str, target_account_id: str = None, detail: dict = None):
    """Best-effort audit write — a logging failure must never block the
    admin action itself."""
    try:
        db.session.add(AdminAuditLog(
            admin_id=admin_id, action=action,
            target_account_id=target_account_id, detail=detail,
        ))
    except Exception:
        pass
