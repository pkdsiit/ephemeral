from app.models.user import User
from app.models.token import AuthToken


def test_user_registration(client, db_session):
    resp = client.post('/api/auth/register', json={
        'email': 'alice@example.com',
        'username': 'alice_123',
        'password': 'StrongPassword123!'
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['user']['username'] == 'alice_123'
    
    user = User.query.filter_by(username='alice_123').first()
    assert user is not None
    assert user.check_password('StrongPassword123!')
    assert user.dating_profile is not None
    assert user.dating_profile.enabled is False


def test_duplicate_email_rejection(client, create_test_user):
    create_test_user(username='user1', email='dup@example.com')
    
    resp = client.post('/api/auth/register', json={
        'email': 'dup@example.com',
        'username': 'user2',
        'password': 'StrongPassword123!'
    })
    assert resp.status_code == 409
    assert 'email already exists' in resp.get_json()['error'].lower()


def test_login_success_and_failure(client, create_test_user):
    create_test_user(username='bob', email='bob@example.com', password='CorrectPassword123!')

    # Login with incorrect password
    bad_resp = client.post('/api/auth/login', json={
        'login_id': 'bob',
        'password': 'WrongPassword!'
    })
    assert bad_resp.status_code == 401

    # Login with username
    ok_resp = client.post('/api/auth/login', json={
        'login_id': 'bob',
        'password': 'CorrectPassword123!'
    })
    assert ok_resp.status_code == 200
    assert ok_resp.get_json()['user']['username'] == 'bob'

    # Login with email (case-insensitive)
    ok_email_resp = client.post('/api/auth/login', json={
        'login_id': 'BOB@EXAMPLE.COM',
        'password': 'CorrectPassword123!'
    })
    assert ok_email_resp.status_code == 200


def test_logout(client, create_test_user):
    user = create_test_user(username='carol', email='carol@example.com')
    client.post('/api/auth/login', json={'login_id': 'carol', 'password': 'Password123!'})
    
    logout_resp = client.post('/api/auth/logout')
    assert logout_resp.status_code == 200

    # Protected me endpoint should now fail
    me_resp = client.get('/api/auth/me')
    assert me_resp.status_code in (401, 302)


def test_password_reset_flow(client, create_test_user, db_session):
    user = create_test_user(username='dave', email='dave@example.com', password='OldPassword123!')
    
    # Request token
    token_obj, raw_token = AuthToken.create_token(user_id=user.id, token_type='PASSWORD_RESET')
    db_session.commit()

    # Reset password with token
    resp = client.post(f'/reset-password/{raw_token}', data={
        'new_password': 'NewPassword123!',
        'confirm_new_password': 'NewPassword123!'
    }, follow_redirects=True)
    assert resp.status_code == 200

    db_session.refresh(user)
    assert user.check_password('NewPassword123!')
    assert not user.check_password('OldPassword123!')
