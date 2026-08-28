import uuid
from datetime import datetime
from app.extensions import db
from app.utils import utcnow


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Conversation(db.Model):
    __tablename__ = 'conversations'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    is_group = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_message_at = db.Column(db.DateTime, default=utcnow, nullable=False, index=True)

    participants = db.relationship(
        'ConversationParticipant',
        backref='conversation',
        lazy='joined',
        cascade='all, delete-orphan'
    )
    
    messages = db.relationship(
        'Message',
        backref='conversation',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='Message.created_at.asc()'
    )

    def is_participant(self, user_id: str) -> bool:
        return any(p.user_id == user_id and p.is_active for p in self.participants)

    def get_other_participant(self, current_user_id: str):
        for p in self.participants:
            if p.user_id != current_user_id:
                return p.user
        return None

    def get_participant_record(self, user_id: str):
        for p in self.participants:
            if p.user_id == user_id:
                return p
        return None

    def to_dict(self, current_user_id: str) -> dict:
        other_user = self.get_other_participant(current_user_id)
        current_participant = self.get_participant_record(current_user_id)
        
        # Get unread message count
        unread_count = 0
        last_msg = None
        
        # Query latest non-deleted message
        from app.models.message import Message
        now_utc = utcnow()
        
        query = self.messages.filter(
            Message.is_deleted == False,
            Message.expires_at > now_utc
        )
        if current_participant and current_participant.cleared_history_at:
            query = query.filter(Message.created_at > current_participant.cleared_history_at)

        latest_message = query.order_by(Message.created_at.desc()).first()
        if latest_message:
            last_msg = latest_message.to_dict(current_user_id)
            
        if current_participant and current_participant.last_read_at:
            unread_count = query.filter(
                Message.sender_id != current_user_id,
                Message.created_at > current_participant.last_read_at
            ).count()
        elif current_participant:
            unread_count = query.filter(Message.sender_id != current_user_id).count()

        return {
            'id': self.id,
            'is_group': self.is_group,
            'other_user': other_user.get_public_profile() if other_user else None,
            'last_message': last_msg,
            'unread_count': unread_count,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else self.created_at.isoformat()
        }


class ConversationParticipant(db.Model):
    __tablename__ = 'conversation_participants'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    conversation_id = db.Column(db.String(36), db.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    joined_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    last_read_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    cleared_history_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('conversation_id', 'user_id', name='uq_conversation_user'),
    )
