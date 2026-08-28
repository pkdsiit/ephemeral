from typing import List, Dict, Any
from app.extensions import db
from app.models.user import User
from app.models.friendship import Block
from app.models.dating import DatingProfile, Interest

DEFAULT_INTERESTS = [
    ('Technology', 'Interests'),
    ('Photography', 'Creative'),
    ('Travel', 'Lifestyle'),
    ('Fitness & Gym', 'Health'),
    ('Music', 'Creative'),
    ('Gaming', 'Entertainment'),
    ('Movies & TV', 'Entertainment'),
    ('Reading & Books', 'Intellectual'),
    ('Cooking & Food', 'Lifestyle'),
    ('Art & Design', 'Creative'),
    ('Outdoors & Nature', 'Lifestyle'),
    ('Writing & Poetry', 'Intellectual'),
    ('Dancing', 'Creative'),
    ('Yoga & Mindfulness', 'Health'),
    ('Sports', 'Health'),
    ('Fashion & Style', 'Lifestyle')
]


def seed_interests():
    """Seed initial interest tags if not present."""
    for name, cat in DEFAULT_INTERESTS:
        if not Interest.query.filter_by(name=name).first():
            db.session.add(Interest(name=name, category=cat))
    db.session.commit()


def check_gender_preference_match(
    user_gender: str | None,
    user_interested_in: str | None,
    candidate_gender: str | None,
    candidate_interested_in: str | None
) -> bool:
    """Check bidirectional gender compatibility between two users."""
    def matches(interested_in, gender):
        if not interested_in or interested_in == 'everyone':
            return True
        if interested_in == 'men' and gender == 'male':
            return True
        if interested_in == 'women' and gender == 'female':
            return True
        if interested_in == 'non-binary' and gender == 'non-binary':
            return True
        return False

    user_likes_candidate = matches(user_interested_in, candidate_gender)
    candidate_likes_user = matches(candidate_interested_in, user_gender)
    return user_likes_candidate and candidate_likes_user


def get_dating_matches(user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    """
    Generate compatible dating match suggestions for user_id.
    Ensures:
    1. Both users have enabled=True and age >= 18
    2. Mutual age range compatibility
    3. Mutual gender interest compatibility
    4. Not blocked and not self
    5. Calculates shared interest score
    """
    user = db.session.get(User, user_id)
    if not user or not user.dating_profile or not user.dating_profile.enabled:
        return []

    profile = user.dating_profile
    if not profile.age or profile.age < 18:
        return []

    # Get blocked IDs
    blocked_ids = set(
        [b.blocked_id for b in Block.query.filter_by(blocker_id=user_id).all()] +
        [b.blocker_id for b in Block.query.filter_by(blocked_id=user_id).all()]
    )

    # Candidates query
    candidates = DatingProfile.query.join(User).filter(
        DatingProfile.enabled == True,
        DatingProfile.user_id != user_id,
        DatingProfile.age >= 18,
        User.is_active_account == True,
        User.is_suspended == False
    ).all()

    user_interests_set = set(i.name for i in profile.interests)
    matches = []

    for cand in candidates:
        if cand.user_id in blocked_ids:
            continue

        # 1. Candidate's age must fall within user's preferred range
        if cand.age < profile.min_age_pref or cand.age > profile.max_age_pref:
            continue

        # 2. User's age must fall within candidate's preferred range
        if profile.age < cand.min_age_pref or profile.age > cand.max_age_pref:
            continue

        # 3. Gender preference compatibility
        if not check_gender_preference_match(
            profile.gender, profile.interested_in,
            cand.gender, cand.interested_in
        ):
            continue

        # Calculate compatibility
        cand_interests_set = set(i.name for i in cand.interests)
        shared = user_interests_set.intersection(cand_interests_set)
        shared_count = len(shared)
        
        # Compatibility score
        age_diff = abs(profile.age - cand.age)
        score = (shared_count * 20) + max(0, 30 - (age_diff * 2))

        match_data = cand.to_dict(include_compatibility_with=profile)
        match_data['compatibility_score'] = score
        match_data['shared_interests'] = list(shared)
        match_data['shared_count'] = shared_count
        matches.append(match_data)

    # Sort by compatibility score descending
    matches.sort(key=lambda x: x['compatibility_score'], reverse=True)
    return matches[:limit]
