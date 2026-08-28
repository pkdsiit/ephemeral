import uuid
from datetime import datetime, timedelta
from app.extensions import db
from app.utils import utcnow


def generate_uuid() -> str:
    return str(uuid.uuid4())


def default_public_message_expiration() -> datetime:
    """Default 7-day public message expiration."""
    return utcnow() + timedelta(days=7)


class PublicRoom(db.Model):
    __tablename__ = 'public_rooms'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    messages = db.relationship(
        'PublicMessage',
        backref='room',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='PublicMessage.created_at.asc()'
    )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }


class PublicMessage(db.Model):
    __tablename__ = 'public_messages'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    room_id = db.Column(db.String(36), db.ForeignKey('public_rooms.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, default=default_public_message_expiration, nullable=False, index=True)
    
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    @property
    def is_expired(self) -> bool:
        return utcnow() >= self.expires_at

    def to_dict(self, current_user_id: str = None) -> dict:
        is_author = (self.user_id == current_user_id) if current_user_id else False
        sender_info = self.author.get_public_chat_identity() if self.author else {
            'id': self.user_id,
            'display_name': 'Anonymous',
            'username': None,
            'gender': 'Member',
            'show_username': False
        }
        return {
            'id': self.id,
            'room_id': self.room_id,
            'sender_id': self.user_id,
            'user_id': self.user_id,
            'sender': sender_info,
            'content': '[ Message deleted ]' if (self.is_deleted or self.is_expired) else self.content,
            'is_author': is_author,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_deleted': self.is_deleted
        }
