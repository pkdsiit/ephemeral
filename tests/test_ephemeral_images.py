import io
from PIL import Image
from app.extensions import storage_service
from app.chat.services import get_or_create_direct_conversation
from app.models.message import Message, MessageImage


def create_dummy_image_bytes(format='JPEG'):
    """Create in-memory test image."""
    img = Image.new('RGB', (100, 100), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return buf


def test_ephemeral_image_lifecycle_and_deletion_on_reply(client, create_test_user, db_session):
    u1 = create_test_user(username='sender_user', email='sender@test.com')
    u2 = create_test_user(username='recipient_user', email='recipient@test.com')

    conv = get_or_create_direct_conversation(u1.id, u2.id)

    # 1. Sender uploads an ephemeral image
    client.post('/api/auth/login', json={'login_id': 'sender_user', 'password': 'Password123!'})
    img_data = create_dummy_image_bytes('JPEG')
    
    upload_resp = client.post(
        f'/api/chats/{conv.id}/images',
        data={'image': (img_data, 'photo.jpg')},
        content_type='multipart/form-data'
    )
    assert upload_resp.status_code == 201
    msg_json = upload_resp.get_json()['data']
    img_id = msg_json['image']['id']
    msg_id = msg_json['id']

    # Verify image exists in storage
    msg_img = db_session.get(MessageImage, img_id)
    assert msg_img is not None
    assert msg_img.state == 'UPLOADED'
    assert msg_img.storage_path is not None
    assert storage_service.exists(msg_img.storage_path) is True

    # 2. Recipient views the ephemeral image
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'login_id': 'recipient_user', 'password': 'Password123!'})

    view_resp = client.get(f'/media/ephemeral/{img_id}')
    assert view_resp.status_code == 200
    assert view_resp.mimetype == 'image/jpeg'
    assert 'no-store' in view_resp.headers.get('Cache-Control', '')

    db_session.refresh(msg_img)
    assert msg_img.state == 'CONSUMED'
    assert msg_img.seen_at is not None
    assert msg_img.consumed_at is not None
    # File is still present on disk until recipient replies!
    assert storage_service.exists(msg_img.storage_path) is True

    # 3. Recipient sends a subsequent NEW message in the conversation
    reply_resp = client.post(f'/api/chats/{conv.id}/messages', json={
        'content': 'I saw your photo! Deleting it now.'
    })
    assert reply_resp.status_code == 201

    # 4. Verify the image file was physically deleted from disk and state is DELETED
    db_session.refresh(msg_img)
    assert msg_img.state == 'DELETED'
    assert msg_img.storage_path is None
    assert msg_img.deleted_at is not None

    # 5. Verify the image can no longer be accessed
    repeat_view = client.get(f'/media/ephemeral/{img_id}')
    assert repeat_view.status_code in (404, 403)


def test_unauthorized_image_access_rejected(client, create_test_user, db_session):
    u1 = create_test_user(username='alice_img', email='alice_img@test.com')
    u2 = create_test_user(username='bob_img', email='bob_img@test.com')
    intruder = create_test_user(username='intruder_img', email='intruder_img@test.com')

    conv = get_or_create_direct_conversation(u1.id, u2.id)

    # Sender uploads image
    client.post('/api/auth/login', json={'login_id': 'alice_img', 'password': 'Password123!'})
    img_data = create_dummy_image_bytes('PNG')
    upload_resp = client.post(
        f'/api/chats/{conv.id}/images',
        data={'image': (img_data, 'secret.png')},
        content_type='multipart/form-data'
    )
    img_id = upload_resp.get_json()['data']['image']['id']

    # Intruder tries to view
    client.post('/api/auth/logout')
    client.post('/api/auth/login', json={'login_id': 'intruder_img', 'password': 'Password123!'})

    get_resp = client.get(f'/media/ephemeral/{img_id}')
    assert get_resp.status_code == 403
