from app.models.dating import DatingProfile, Interest
from app.models.friendship import Block
from app.dating.services import get_dating_matches


def test_dating_adult_age_requirement(client, create_test_user):
    user = create_test_user(username='minor_test', email='minor@test.com')
    client.post('/api/auth/login', json={'login_id': 'minor_test', 'password': 'Password123!'})

    # Try setting age to 16
    resp = client.patch('/api/dating/profile', json={
        'enabled': True,
        'age': 16,
        'gender': 'male',
        'interested_in': 'women'
    })
    assert resp.status_code == 400
    assert '18 years' in resp.get_json()['error']


def test_dating_matching_algorithm(client, create_test_user, db_session):
    tech = Interest.query.filter_by(name='Technology').first()
    travel = Interest.query.filter_by(name='Travel').first()
    gaming = Interest.query.filter_by(name='Gaming').first()
    music = Interest.query.filter_by(name='Music').first()

    # User 1: 25-year-old Male, likes Tech, Travel, Gaming. Looking for Women (22-28).
    u1 = create_test_user(username='male_user', email='male@test.com')
    p1 = u1.dating_profile
    p1.enabled = True
    p1.age = 25
    p1.gender = 'male'
    p1.interested_in = 'women'
    p1.min_age_pref = 22
    p1.max_age_pref = 28
    p1.interests = [tech, travel, gaming]

    # Candidate 1: Compatible 24-year-old Female, likes Tech, Travel, Music. Looking for Men (24-30).
    u2 = create_test_user(username='female_compatible', email='female1@test.com')
    p2 = u2.dating_profile
    p2.enabled = True
    p2.age = 24
    p2.gender = 'female'
    p2.interested_in = 'men'
    p2.min_age_pref = 24
    p2.max_age_pref = 30
    p2.interests = [tech, travel, music]

    # Candidate 2: Incompatible age 35-year-old Female.
    u3 = create_test_user(username='female_older', email='female2@test.com')
    p3 = u3.dating_profile
    p3.enabled = True
    p3.age = 35
    p3.gender = 'female'
    p3.interested_in = 'men'
    p3.min_age_pref = 20
    p3.max_age_pref = 40

    db_session.commit()

    matches = get_dating_matches(u1.id)
    match_usernames = [m['username'] for m in matches]

    assert 'female_compatible' in match_usernames
    assert 'female_older' not in match_usernames

    # Check shared interests
    comp_match = next(m for m in matches if m['username'] == 'female_compatible')
    assert 'Technology' in comp_match['shared_interests']
    assert 'Travel' in comp_match['shared_interests']
    assert comp_match['shared_count'] == 2


def test_blocked_users_excluded_from_dating(create_test_user, db_session):
    u1 = create_test_user(username='user_a', email='a@test.com')
    p1 = u1.dating_profile
    p1.enabled = True
    p1.age = 26
    p1.gender = 'male'
    p1.interested_in = 'everyone'

    u2 = create_test_user(username='user_b', email='b@test.com')
    p2 = u2.dating_profile
    p2.enabled = True
    p2.age = 26
    p2.gender = 'female'
    p2.interested_in = 'everyone'

    db_session.commit()

    # Before block, u2 is in u1's matches
    assert any(m['username'] == 'user_b' for m in get_dating_matches(u1.id))

    # Add block
    block = Block(blocker_id=u1.id, blocked_id=u2.id)
    db_session.add(block)
    db_session.commit()

    # After block, u2 is excluded
    assert not any(m['username'] == 'user_b' for m in get_dating_matches(u1.id))
