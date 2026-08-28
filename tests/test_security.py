import io
from app.models.report import Report
from app.models.friendship import Block
from app.chat.services import get_or_create_direct_conversation


def test_security_headers_present(client):
    resp = client.get('/healthz')
    assert resp.status_code == 200
    assert resp.headers.get('X-Content-Type-Options') == 'nosniff'
    assert resp.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert resp.headers.get('X-XSS-Protection') == '1; mode=block'
    assert resp.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'


def test_blocking_prevents_messaging(client, create_test_user, db_session):
    u1 = create_test_user(username='blocker_user', email='blocker@test.com')
    u2 = create_test_user(username='blocked_target', email='blocked@test.com')

    # u1 blocks u2
    client.post('/api/auth/login', json={'login_id': 'blocker_user', 'password': 'Password123!'})
    block_resp = client.post(f'/api/users/{u2.id}/block')
    assert block_resp.status_code == 200

    assert u1.has_blocked(u2.id) is True
    assert u2.is_blocked_by(u1.id) is True

    # u2 tries to start chat with u1
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'login_id': 'blocked_target', 'password': 'Password123!'})

    chat_resp = client.post('/api/chats', json={'username': 'blocker_user'})
    assert chat_resp.status_code == 400
    assert 'block' in chat_resp.get_json()['error'].lower()


def test_file_upload_validation_rejects_fake_image(client, create_test_user):
    u1 = create_test_user(username='uploader', email='up@test.com')
    u2 = create_test_user(username='receiver_up', email='rec_up@test.com')
    conv = get_or_create_direct_conversation(u1.id, u2.id)

    client.post('/api/auth/login', json={'login_id': 'uploader', 'password': 'Password123!'})
    
    # Fake executable file disguised as image
    fake_data = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00FakeEXEContent")
    resp = client.post(
        f'/api/chats/{conv.id}/images',
        data={'image': (fake_data, 'malicious.jpg')},
        content_type='multipart/form-data'
    )
    assert resp.status_code == 400
    assert 'invalid image' in resp.get_json()['error'].lower()


def test_abuse_reporting_system(client, create_test_user, db_session):
    reporter = create_test_user(username='reporter_user', email='rep@test.com')
    bad_actor = create_test_user(username='bad_actor', email='bad@test.com')

    client.post('/api/auth/login', json={'login_id': 'reporter_user', 'password': 'Password123!'})

    report_resp = client.post(f'/api/users/{bad_actor.id}/report', json={
        'reason': 'Inappropriate harassment messages',
        'details': 'Sent unprovoked abusive texts'
    })
    assert report_resp.status_code == 201

    rep = Report.query.filter_by(reported_user_id=bad_actor.id).first()
    assert rep is not None
    assert rep.status == 'PENDING'
    assert rep.reporter_id == reporter.id
