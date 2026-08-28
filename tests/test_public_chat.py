from app.models.public_room import PublicRoom, PublicMessage


def test_public_chat_message_flow(client, create_test_user, db_session):
    u1 = create_test_user(username='public_author', email='author@pub.com')
    u2 = create_test_user(username='public_reader', email='reader@pub.com')

    room = PublicRoom.query.filter_by(code='general').first()
    assert room is not None

    # u1 sends public message
    client.post('/api/auth/login', json={'login_id': 'public_author', 'password': 'Password123!'})
    send_resp = client.post(f'/api/public/rooms/{room.code}/messages', json={
        'content': 'Hello everyone in the public square!'
    })
    assert send_resp.status_code == 201
    msg_id = send_resp.get_json()['data']['id']

    # u2 reads messages
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'login_id': 'public_reader', 'password': 'Password123!'})

    fetch_resp = client.get(f'/api/public/rooms/{room.code}/messages')
    assert fetch_resp.status_code == 200
    messages = fetch_resp.get_json()['messages']
    assert any(m['id'] == msg_id for m in messages)

    # u2 tries to delete u1's message (unauthorized)
    del_fail = client.delete(f'/api/public/messages/{msg_id}')
    assert del_fail.status_code == 403

    # u1 deletes their own message
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'login_id': 'public_author', 'password': 'Password123!'})
    del_ok = client.delete(f'/api/public/messages/{msg_id}')
    assert del_ok.status_code == 200

    msg_record = db_session.get(PublicMessage, msg_id)
    assert msg_record.is_deleted is True
