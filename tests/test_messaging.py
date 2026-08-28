from app.chat.services import get_or_create_direct_conversation, send_text_message
from app.models.message import Message


def test_send_and_receive_text_message(client, create_test_user, db_session):
    u1 = create_test_user(username='sender', email='sender@example.com')
    u2 = create_test_user(username='receiver', email='receiver@example.com')

    conv = get_or_create_direct_conversation(u1.id, u2.id)

    # Login as sender
    client.post('/api/auth/login', json={'login_id': 'sender', 'password': 'Password123!'})

    send_resp = client.post(f'/api/chats/{conv.id}/messages', json={
        'content': 'Hello, this is an ephemeral text message.'
    })
    assert send_resp.status_code == 201
    msg_data = send_resp.get_json()['data']
    assert msg_data['content'] == 'Hello, this is an ephemeral text message.'
    assert msg_data['is_sender'] is True

    # Check recipient view
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'login_id': 'receiver', 'password': 'Password123!'})

    fetch_resp = client.get(f'/api/chats/{conv.id}/messages')
    assert fetch_resp.status_code == 200
    messages = fetch_resp.get_json()['messages']
    assert len(messages) == 1
    assert messages[0]['content'] == 'Hello, this is an ephemeral text message.'
    assert messages[0]['is_sender'] is False


def test_unauthorized_conversation_access(client, create_test_user):
    u1 = create_test_user(username='alice', email='alice@example.com')
    u2 = create_test_user(username='bob', email='bob@example.com')
    intruder = create_test_user(username='intruder', email='intruder@example.com')

    conv = get_or_create_direct_conversation(u1.id, u2.id)

    client.post('/api/auth/login', json={'login_id': 'intruder', 'password': 'Password123!'})
    
    # Try fetching messages
    get_resp = client.get(f'/api/chats/{conv.id}/messages')
    assert get_resp.status_code == 403

    # Try sending message
    post_resp = client.post(f'/api/chats/{conv.id}/messages', json={'content': 'hacked'})
    assert post_resp.status_code == 400 or post_resp.status_code == 403


def test_delete_individual_message(client, create_test_user, db_session):
    u1 = create_test_user(username='author', email='author@example.com')
    u2 = create_test_user(username='listener', email='listener@example.com')

    conv = get_or_create_direct_conversation(u1.id, u2.id)
    msg = send_text_message(u1.id, conv.id, "Secret message to be deleted")

    # Author deletes message
    client.post('/api/auth/login', json={'login_id': 'author', 'password': 'Password123!'})
    del_resp = client.delete(f'/api/messages/{msg.id}')
    assert del_resp.status_code == 200

    db_session.refresh(msg)
    assert msg.is_deleted is True
    assert msg.deleted_at is not None
