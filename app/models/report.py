import uuid
from datetime import datetime
from app.extensions import db
from app.utils import utcnow


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Report(db.Model):
    __tablename__ = 'reports'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    reporter_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    reported_user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    message_id = db.Column(db.String(36), nullable=True)
    public_message_id = db.Column(db.String(36), nullable=True)
    
    reason = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text, nullable=True)
    
    # Status: PENDING, RESOLVED, DISMISSED
    status = db.Column(db.String(20), default='PENDING', nullable=False, index=True)
    admin_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'reporter_id': self.reporter_id,
            'reporter_username': self.reporter.username if self.reporter else 'Unknown',
            'reported_user_id': self.reported_user_id,
            'reported_username': self.reported_user.username if self.reported_user else 'None',
            'reason': self.reason,
            'details': self.details,
            'status': self.status,
            'admin_notes': self.admin_notes,
            'created_at': self.created_at.isoformat(),
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }
