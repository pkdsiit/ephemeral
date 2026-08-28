import uuid
from datetime import datetime, timedelta
from app.extensions import db
from app.utils import utcnow


def generate_uuid() -> str:
    return str(uuid.uuid4())


def default_expiration() -> datetime:
    """Default 7-day message expiration."""
    return utcnow() + timedelta(days=7)


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    conversation_id = db.Column(db.String(36), db.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    sender_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Message type: TEXT, IMAGE, SYSTEM
    message_type = db.Column(db.String(20), default='TEXT', nullable=False)
    content = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, default=default_expiration, nullable=False, index=True)
    
    is_seen = db.Column(db.Boolean, default=False, nullable=False)
    seen_at = db.Column(db.DateTime, nullable=True)
    
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    image = db.relationship('MessageImage', backref='message', uselist=False, cascade='all, delete-orphan')

    @property
    def is_expired(self) -> bool:
        return utcnow() >= self.expires_at

    def to_dict(self, current_user_id: str = None) -> dict:
        is_sender = (self.sender_id == current_user_id) if current_user_id else False
        
        data = {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'sender_id': self.sender_id,
            'sender_username': self.sender.username if self.sender else None,
            'message_type': self.message_type,
            'is_sender': is_sender,
            'is_seen': self.is_seen,
            'seen_at': self.seen_at.isoformat() if self.seen_at else None,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_deleted': self.is_deleted,
        }

        if self.is_deleted or self.is_expired:
            data['content'] = '[ Message expired or deleted ]'
            data['image'] = None
            return data

        if self.message_type == 'TEXT':
            data['content'] = self.content
            data['image'] = None
        elif self.message_type == 'IMAGE' and self.image:
            data['content'] = self.content or ''
            data['image'] = self.image.to_dict(is_sender=is_sender)
        elif self.message_type == 'SYSTEM':
            data['content'] = self.content
            data['image'] = None
        else:
            data['content'] = self.content
            data['image'] = None

        return data


class MessageImage(db.Model):
    __tablename__ = 'message_images'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    message_id = db.Column(db.String(36), db.ForeignKey('messages.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    
    storage_path = db.Column(db.String(512), nullable=True)
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(64), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    
    # States: UPLOADED, DELIVERED, SEEN, CONSUMED, EXPIRED, DELETED
    state = db.Column(db.String(20), default='UPLOADED', nullable=False, index=True)
    
    seen_at = db.Column(db.DateTime, nullable=True)
    consumed_at = db.Column(db.DateTime, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    view_count = db.Column(db.Integer, default=0, nullable=False)

    @property
    def is_accessible(self) -> bool:
        """Return True if image is not deleted, not consumed, not expired, and storage path exists."""
        if self.state in ('DELETED', 'EXPIRED'):
            return False
        if not self.storage_path:
            return False
        if self.message and self.message.is_expired:
            return False
        return True

    def to_dict(self, is_sender: bool = False) -> dict:
        return {
            'id': self.id,
            'state': self.state,
            'is_accessible': self.is_accessible,
            'view_count': self.view_count,
            'seen_at': self.seen_at.isoformat() if self.seen_at else None,
            'consumed_at': self.consumed_at.isoformat() if self.consumed_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            # Media endpoint is access-controlled, never expose direct filesystem path
            'view_url': f"/media/ephemeral/{self.id}" if self.is_accessible else None,
            'is_sender': is_sender
        }
