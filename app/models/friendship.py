import uuid
from datetime import datetime
from app.extensions import db
from app.utils import utcnow


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Friendship(db.Model):
    __tablename__ = 'friendships'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    requester_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    addressee_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    status = db.Column(db.String(20), default='PENDING', nullable=False, index=True)  # PENDING, ACCEPTED, REJECTED
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('requester_id', 'addressee_id', name='uq_friendship_pair'),
    )

    def to_dict(self, current_user_id: str = None) -> dict:
        other_user = self.addressee if self.requester_id == current_user_id else self.requester
        return {
            'id': self.id,
            'requester_id': self.requester_id,
            'addressee_id': self.addressee_id,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'other_user': other_user.get_public_profile() if other_user else None
        }


class Block(db.Model):
    __tablename__ = 'blocks'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    blocker_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    blocked_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('blocker_id', 'blocked_id', name='uq_block_pair'),
    )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'blocker_id': self.blocker_id,
            'blocked_id': self.blocked_id,
            'blocked_user': self.blocked.get_public_profile() if self.blocked else None,
            'created_at': self.created_at.isoformat()
        }
