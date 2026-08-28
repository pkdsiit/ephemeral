import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db
from app.utils import utcnow


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    username_lower = db.Column(db.String(32), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(64), nullable=True)
    avatar_path = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_suspended = db.Column(db.Boolean, default=False, nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_seen_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    # Relationships
    dating_profile = db.relationship('DatingProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    
    sent_friendships = db.relationship(
        'Friendship',
        foreign_keys='Friendship.requester_id',
        backref='requester',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    received_friendships = db.relationship(
        'Friendship',
        foreign_keys='Friendship.addressee_id',
        backref='addressee',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    sent_blocks = db.relationship(
        'Block',
        foreign_keys='Block.blocker_id',
        backref='blocker',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    received_blocks = db.relationship(
        'Block',
        foreign_keys='Block.blocked_id',
        backref='blocked',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    conversation_participants = db.relationship(
        'ConversationParticipant',
        backref='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    sent_messages = db.relationship(
        'Message',
        backref='sender',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    public_messages = db.relationship(
        'PublicMessage',
        backref='author',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    reports_filed = db.relationship(
        'Report',
        foreign_keys='Report.reporter_id',
        backref='reporter',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    reports_received = db.relationship(
        'Report',
        foreign_keys='Report.reported_user_id',
        backref='reported_user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    tokens = db.relationship('AuthToken', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def is_active(self) -> bool:
        """Flask-Login property: active if account is enabled and not suspended."""
        return self.is_active_account and not self.is_suspended

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_blocked(self, other_user_id: str) -> bool:
        """Check if current user has blocked another user."""
        from app.models.friendship import Block
        return db.session.query(Block.id).filter_by(blocker_id=self.id, blocked_id=other_user_id).first() is not None

    def is_blocked_by(self, other_user_id: str) -> bool:
        """Check if current user is blocked by another user."""
        from app.models.friendship import Block
        return db.session.query(Block.id).filter_by(blocker_id=other_user_id, blocked_id=self.id).first() is not None

    def is_mutually_blocked(self, other_user_id: str) -> bool:
        """Check if any block exists between the two users."""
        from app.models.friendship import Block
        return db.session.query(Block.id).filter(
            ((Block.blocker_id == self.id) & (Block.blocked_id == other_user_id)) |
            ((Block.blocker_id == other_user_id) & (Block.blocked_id == self.id))
        ).first() is not None

    def can_communicate_with(self, other_user_id: str) -> bool:
        """Check if two users can communicate (not blocked, not self, active)."""
        if self.id == other_user_id:
            return False
        if self.is_mutually_blocked(other_user_id):
            return False
        return True

    def get_public_profile(self) -> dict:
        """Safe public representation without sensitive email or private data."""
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name or self.username,
            'avatar_url': f"/media/avatar/{self.id}" if self.avatar_path else None,
            'bio': self.bio or '',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'dating_enabled': bool(self.dating_profile and self.dating_profile.enabled)
        }

    def __repr__(self) -> str:
        return f"<User @{self.username} ({self.id})>"
