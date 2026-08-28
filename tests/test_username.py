from app.models.user import User
from app.chat.services import get_or_create_direct_conversation


def test_unique_username_registration(client, create_test_user):
    create_test_user(username='rahul123', email='rahul@example.com')

    # Rejection of exact same username
    resp1 = client.post('/api/auth/register', json={
        'email': 'rahul2@example.com',
        'username': 'rahul123',
        'password': 'Password123!'
    })
    assert resp1.status_code == 409
    assert 'username is already taken' in resp1.get_json()['error'].lower()

    # Rejection of case-insensitive duplicate username
    resp2 = client.post('/api/auth/register', json={
        'email': 'rahul3@example.com',
        'username': 'RAHUL123',
        'password': 'Password123!'
    })
    assert resp2.status_code == 409
    assert 'username is already taken' in resp2.get_json()['error'].lower()


def test_invalid_username_format(client):
    invalid_usernames = ['ab', 'a'*35, 'user name', 'user@name', 'user#1']
    for inv in invalid_usernames:
        resp = client.post('/api/auth/register', json={
            'email': f'test_{inv.replace(" ", "_")}@example.com',
            'username': inv,
            'password': 'Password123!'
        })
        assert resp.status_code == 400


def test_username_change_preserves_relationships(client, create_test_user, db_session):
    u1 = create_test_user(username='user_one', email='u1@example.com')
    u2 = create_test_user(username='user_two', email='u2@example.com')

    # Create conversation
    conv = get_or_create_direct_conversation(u1.id, u2.id)
    conv_id = conv.id

    # Login as u1 and update username
    client.post('/api/auth/login', json={'login_id': 'user_one', 'password': 'Password123!'})
    
    update_resp = client.patch('/api/users/me/username', json={'username': 'user_one_renamed'})
    assert update_resp.status_code == 200

    db_session.refresh(u1)
    assert u1.username == 'user_one_renamed'
    assert u1.username_lower == 'user_one_renamed'

    # Conversation still exists and references the same user ID
    db_session.refresh(conv)
    assert conv.is_participant(u1.id)
    other = conv.get_other_participant(u2.id)
    assert other.id == u1.id
    assert other.username == 'user_one_renamed'
