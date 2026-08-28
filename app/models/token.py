import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
from app.extensions import db
from app.utils import utcnow


def generate_uuid() -> str:
    return str(uuid.uuid4())


class AuthToken(db.Model):
    __tablename__ = 'auth_tokens'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    token_type = db.Column(db.String(32), default='PASSWORD_RESET', nullable=False, index=True)  # PASSWORD_RESET, EMAIL_VERIFICATION
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)

    @classmethod
    def create_token(cls, user_id: str, token_type: str = 'PASSWORD_RESET', expires_in_minutes: int = 60) -> tuple['AuthToken', str]:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        expires_at = utcnow() + timedelta(minutes=expires_in_minutes)
        
        token_obj = cls(
            user_id=user_id,
            token_hash=token_hash,
            token_type=token_type,
            expires_at=expires_at
        )
        db.session.add(token_obj)
        return token_obj, raw_token

    @classmethod
    def verify_token(cls, raw_token: str, token_type: str = 'PASSWORD_RESET') -> 'AuthToken | None':
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        now_utc = utcnow()
        
        token_obj = cls.query.filter_by(
            token_hash=token_hash,
            token_type=token_type,
            used_at=None
        ).filter(cls.expires_at > now_utc).first()
        
        return token_obj
