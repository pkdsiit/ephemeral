import uuid
from datetime import datetime
from app.extensions import db
from app.utils import utcnow


def generate_uuid() -> str:
    return str(uuid.uuid4())


# Association table for Many-to-Many relationship between DatingProfile and Interest
dating_profile_interests = db.Table(
    'dating_profile_interests',
    db.Column('profile_id', db.String(36), db.ForeignKey('dating_profiles.id', ondelete='CASCADE'), primary_key=True),
    db.Column('interest_id', db.Integer, db.ForeignKey('interests.id', ondelete='CASCADE'), primary_key=True)
)


class Interest(db.Model):
    __tablename__ = 'interests'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)
    category = db.Column(db.String(64), default='General', nullable=False)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category
        }


class DatingProfile(db.Model):
    __tablename__ = 'dating_profiles'

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    
    enabled = db.Column(db.Boolean, default=False, nullable=False, index=True)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(32), nullable=True)  # 'male', 'female', 'non-binary', 'other'
    interested_in = db.Column(db.String(32), default='everyone', nullable=True)  # 'men', 'women', 'everyone', 'non-binary'
    
    min_age_pref = db.Column(db.Integer, default=18, nullable=False)
    max_age_pref = db.Column(db.Integer, default=99, nullable=False)
    
    bio = db.Column(db.Text, nullable=True)
    show_gender = db.Column(db.Boolean, default=True, nullable=False)
    
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    interests = db.relationship(
        'Interest',
        secondary=dating_profile_interests,
        lazy='joined',
        backref=db.backref('dating_profiles', lazy='dynamic')
    )

    def to_dict(self, include_compatibility_with: 'DatingProfile' = None) -> dict:
        interests_list = [i.name for i in self.interests]
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'display_name': self.user.display_name if self.user else None,
            'avatar_url': f"/media/avatar/{self.user_id}" if (self.user and self.user.avatar_path) else None,
            'enabled': self.enabled,
            'age': self.age,
            'gender': self.gender if self.show_gender else None,
            'interested_in': self.interested_in,
            'min_age_pref': self.min_age_pref,
            'max_age_pref': self.max_age_pref,
            'bio': self.bio or (self.user.bio if self.user else ''),
            'interests': interests_list,
        }

        if include_compatibility_with:
            current_interests = set(i.name for i in include_compatibility_with.interests)
            target_interests = set(interests_list)
            shared = current_interests.intersection(target_interests)
            data['shared_interests'] = list(shared)
            data['shared_count'] = len(shared)
            data['compatibility_score'] = len(shared) * 15 + (10 if self.age and include_compatibility_with.age and abs(self.age - include_compatibility_with.age) <= 5 else 0)

        return data
