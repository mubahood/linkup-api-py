"""
App version domain model: AppVersion — one row per (app_id, platform),
drives the force-update check at GET /v1/app/version.
"""
import uuid
from datetime import datetime
from backend.models import db


class AppVersion(db.Model):
    __tablename__ = 'lu_app_versions'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    app_id = db.Column(db.String(20), nullable=False)
    platform = db.Column(db.String(10), nullable=False)
    latest_build = db.Column(db.Integer, nullable=False)
    latest_version_name = db.Column(db.String(20), nullable=False)
    min_supported_build = db.Column(db.Integer, nullable=False)
    update_notes = db.Column(db.Text, nullable=True)
    android_url = db.Column(db.String(500), nullable=True)
    ios_url = db.Column(db.String(500), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, installed_build: int) -> dict:
        return {
            'latest_build': self.latest_build,
            'latest_version_name': self.latest_version_name,
            'min_supported_build': self.min_supported_build,
            'update_available': installed_build < self.latest_build,
            'force_update': installed_build < self.min_supported_build,
            'update_notes': self.update_notes or '',
            'android_url': self.android_url,
            'ios_url': self.ios_url,
        }
