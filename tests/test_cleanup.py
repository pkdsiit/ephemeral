import io
from datetime import datetime, timedelta
from PIL import Image
from app.extensions import storage_service
from app.chat.services import get_or_create_direct_conversation
from app.models.message import Message, MessageImage
from app.models.token import AuthToken
from app.tasks.cleanup import cleanup_expired_content
from app.utils import utcnow


def test_cleanup_expired_messages_and_images(create_test_user, db_session):
    u1 = create_test_user(username='u_clean1', email='clean1@test.com')
    u2 = create_test_user(username='u_clean2', email='clean2@test.com')

    conv = get_or_create_direct_conversation(u1.id, u2.id)

    # 1. Create a simulated expired message (8 days old)
    past_date = utcnow() - timedelta(days=8)
    past_expiry = utcnow() - timedelta(days=1)

    msg = Message(
        conversation_id=conv.id,
        sender_id=u1.id,
        message_type='IMAGE',
        content='[ Ephemeral Image ]',
        created_at=past_date,
        expires_at=past_expiry
    )
    db_session.add(msg)
    db_session.flush()

    # Save a physical dummy image file to storage
    img = Image.new('RGB', (50, 50), color=(100, 100, 100))
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    storage_path = storage_service.save(buf.getvalue(), 'expired.jpg', subfolder='private_images')

    msg_image = MessageImage(
        message_id=msg.id,
        storage_path=storage_path,
        original_filename='expired.jpg',
        mime_type='image/jpeg',
        file_size=len(buf.getvalue()),
        state='UPLOADED'
    )
    db_session.add(msg_image)

    # 2. Create expired auth token
    expired_token = AuthToken(
        user_id=u1.id,
        token_hash='dummyhash123',
        token_type='PASSWORD_RESET',
        expires_at=past_expiry
    )
    db_session.add(expired_token)
    db_session.commit()

    assert storage_service.exists(storage_path) is True

    # 3. Execute cleanup
    stats = cleanup_expired_content()
    assert stats['expired_messages_cleaned'] >= 1
    assert stats['images_deleted_from_disk'] >= 1
    assert stats['tokens_cleaned'] >= 1

    # 4. Verify file is deleted from disk
    assert storage_service.exists(storage_path) is False

    db_session.refresh(msg)
    db_session.refresh(msg_image)
    assert msg.is_deleted is True
    assert msg_image.state == 'EXPIRED'
    assert msg_image.storage_path is None

    # 5. Verify Idempotency - running cleanup again shouldn't fail
    stats2 = cleanup_expired_content()
    assert stats2['images_deleted_from_disk'] == 0
