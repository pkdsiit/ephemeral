from app.models.public_room import PublicRoom, PublicMessage
from app.models.user import User


def test_public_chat_message_flow(client, create_test_user, db_session):
    u1 = create_test_user(username='public_author', email='author@pub.com')
    u1.gender = 'male'
    db_session.commit()

    u2 = create_test_user(username='public_reader', email='reader@pub.com')
    u2.gender = 'female'
    db_session.commit()

    room = PublicRoom.query.filter_by(code='general').first()
    assert room is not None

    # u1 sends public message
    client.post('/api/auth/login', json={'login_id': 'public_author', 'password': 'Password123!'})
    send_resp = client.post(f'/api/public/rooms/{room.code}/messages', json={
        'content': 'Hello everyone in the public square!'
    })
    assert send_resp.status_code == 201
    data = send_resp.get_json()['data']
    msg_id = data['id']
    
    # Assert sender identity in send response
    assert data['sender']['display_name'] == '@public_author'
    assert data['sender']['gender'] == 'Male'
    assert data['sender']['show_username'] is True
    assert 'age' not in data['sender']
    assert 'age' not in data

    # u2 reads messages
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'login_id': 'public_reader', 'password': 'Password123!'})

    fetch_resp = client.get(f'/api/public/rooms/{room.code}/messages')
    assert fetch_resp.status_code == 200
    messages = fetch_resp.get_json()['messages']
    target_msg = next((m for m in messages if m['id'] == msg_id), None)
    assert target_msg is not None
    assert target_msg['sender']['display_name'] == '@public_author'
    assert target_msg['sender']['gender'] == 'Male'
    assert 'age' not in target_msg['sender']

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


def test_public_chat_username_privacy_toggle(client, create_test_user, db_session):
    u_alice = create_test_user(username='alice', email='alice@privacy.com')
    u_alice.gender = 'female'
    u_alice.show_username_in_public_chat = True
    db_session.commit()

    u_bob = create_test_user(username='bob', email='bob@privacy.com')
    u_bob.gender = 'male'
    db_session.commit()

    room = PublicRoom.query.filter_by(code='random').first() or PublicRoom.query.first()

    # Step 1: Alice sends message with show_username ON
    client.post('/api/auth/login', json={'login_id': 'alice', 'password': 'Password123!'})
    resp1 = client.post(f'/api/public/rooms/{room.code}/messages', json={'content': 'Message with username visible'})
    assert resp1.status_code == 201
    msg1_data = resp1.get_json()['data']
    assert msg1_data['sender']['display_name'] == '@alice'
    assert msg1_data['sender']['username'] == 'alice'
    assert msg1_data['sender']['gender'] == 'Female'
    assert msg1_data['sender']['show_username'] is True

    # Step 2: Alice disables username visibility via API
    privacy_resp = client.post('/api/settings/privacy', json={'show_username_in_public_chat': False})
    assert privacy_resp.status_code == 200
    assert privacy_resp.get_json()['show_username_in_public_chat'] is False

    # Verify setting persisted in PostgreSQL
    db_session.refresh(u_alice)
    assert u_alice.show_username_in_public_chat is False

    # Step 3: Alice sends new message with show_username OFF
    resp2 = client.post(f'/api/public/rooms/{room.code}/messages', json={'content': 'Anonymous secret message'})
    assert resp2.status_code == 201
    msg2_data = resp2.get_json()['data']
    assert msg2_data['sender']['display_name'] == 'Anonymous'
    assert msg2_data['sender']['username'] is None  # Never leak actual username!
    assert msg2_data['sender']['gender'] == 'Female'
    assert msg2_data['sender']['show_username'] is False
    assert 'age' not in msg2_data['sender']

    # Step 4: Bob fetches messages and sees anonymous identity for msg2
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'login_id': 'bob', 'password': 'Password123!'})

    fetch_resp = client.get(f'/api/public/rooms/{room.code}/messages')
    assert fetch_resp.status_code == 200
    messages = fetch_resp.get_json()['messages']
    
    fetched_msg2 = next((m for m in messages if m['id'] == msg2_data['id']), None)
    assert fetched_msg2 is not None
    assert fetched_msg2['sender']['display_name'] == 'Anonymous'
    assert fetched_msg2['sender']['username'] is None
    assert fetched_msg2['sender']['gender'] == 'Female'
    assert fetched_msg2['sender']['show_username'] is False


def test_public_chat_applies_to_all_rooms(client, create_test_user, db_session):
    u = create_test_user(username='charlie', email='charlie@rooms.com')
    u.gender = 'other'
    db_session.commit()

    client.post('/api/auth/login', json={'login_id': 'charlie', 'password': 'Password123!'})

    rooms = PublicRoom.query.filter_by(is_active=True).all()
    assert len(rooms) >= 3

    for room in rooms:
        resp = client.post(f'/api/public/rooms/{room.code}/messages', json={'content': f'Hello #{room.name}'})
        assert resp.status_code == 201
        data = resp.get_json()['data']
        assert data['sender']['display_name'] == '@charlie'
        assert data['sender']['gender'] == 'Other'
        assert 'age' not in data['sender']


def test_multi_user_alternating_messages_alignment(client, create_test_user, db_session):
    u_alice = create_test_user(username='alice_chat', email='alice@alt.com')
    u_alice.gender = 'female'
    u_bob = create_test_user(username='bob_chat', email='bob@alt.com')
    u_bob.gender = 'male'
    u_charlie = create_test_user(username='charlie_chat', email='charlie@alt.com')
    u_charlie.gender = 'non-binary'
    u_charlie.show_username_in_public_chat = False  # Hidden
    db_session.commit()

    room = PublicRoom.query.filter_by(code='general').first()

    # Alice sends M1
    client.post('/api/auth/login', json={'login_id': 'alice_chat', 'password': 'Password123!'})
    m1 = client.post(f'/api/public/rooms/{room.code}/messages', json={'content': 'M1 from Alice'}).get_json()['data']
    client.post('/api/auth/logout')

    # Bob sends M2
    client.post('/api/auth/login', json={'login_id': 'bob_chat', 'password': 'Password123!'})
    m2 = client.post(f'/api/public/rooms/{room.code}/messages', json={'content': 'M2 from Bob'}).get_json()['data']
    client.post('/api/auth/logout')

    # Charlie sends M3 (anonymous)
    client.post('/api/auth/login', json={'login_id': 'charlie_chat', 'password': 'Password123!'})
    m3 = client.post(f'/api/public/rooms/{room.code}/messages', json={'content': 'M3 from Charlie'}).get_json()['data']

    # When Charlie views:
    # M1 (Alice) -> is_author is False, sender @alice_chat, Female
    # M2 (Bob) -> is_author is False, sender @bob_chat, Male
    # M3 (Charlie) -> is_author is True, sender Anonymous, Non-binary
    fetch_charlie = client.get(f'/api/public/rooms/{room.code}/messages').get_json()['messages']
    f_m1 = next(m for m in fetch_charlie if m['id'] == m1['id'])
    f_m2 = next(m for m in fetch_charlie if m['id'] == m2['id'])
    f_m3 = next(m for m in fetch_charlie if m['id'] == m3['id'])

    assert f_m1['is_author'] is False
    assert f_m1['sender']['display_name'] == '@alice_chat'
    assert f_m1['sender']['gender'] == 'Female'

    assert f_m2['is_author'] is False
    assert f_m2['sender']['display_name'] == '@bob_chat'
    assert f_m2['sender']['gender'] == 'Male'

    assert f_m3['is_author'] is True
    assert f_m3['sender']['display_name'] == 'Anonymous'
    assert f_m3['sender']['gender'] == 'Non-binary'

    # Now login as Alice and verify her view:
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'login_id': 'alice_chat', 'password': 'Password123!'})
    fetch_alice = client.get(f'/api/public/rooms/{room.code}/messages').get_json()['messages']
    fa_m1 = next(m for m in fetch_alice if m['id'] == m1['id'])
    fa_m2 = next(m for m in fetch_alice if m['id'] == m2['id'])
    fa_m3 = next(m for m in fetch_alice if m['id'] == m3['id'])

    assert fa_m1['is_author'] is True
    assert fa_m2['is_author'] is False
    assert fa_m3['is_author'] is False
    assert fa_m3['sender']['display_name'] == 'Anonymous'
    assert fa_m3['sender']['username'] is None

