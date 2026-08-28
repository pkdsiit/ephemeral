import logging
from datetime import datetime
from app.extensions import db, storage_service
from app.models.message import Message, MessageImage
from app.models.public_room import PublicMessage
from app.models.token import AuthToken
from app.utils import utcnow

logger = logging.getLogger('ephemeral.cleanup')


def cleanup_expired_content() -> dict:
    """
    Idempotent server-side cleanup task:
    1. Removes expired & consumed ephemeral images from disk storage.
    2. Updates database records to mark messages/images expired.
    3. Cleans up expired auth tokens.
    4. Ensures zero private image or text leakage in logs.
    """
    now_utc = utcnow()
    stats = {
        'expired_messages_cleaned': 0,
        'images_deleted_from_disk': 0,
        'consumed_images_deleted': 0,
        'public_messages_cleaned': 0,
        'tokens_cleaned': 0
    }

    try:
        # 1. Ephemeral Images associated with expired messages or marked for deletion
        expired_images = MessageImage.query.join(Message).filter(
            (Message.expires_at <= now_utc) | (Message.is_deleted == True)
        ).filter(
            MessageImage.storage_path != None
        ).all()

        for img in expired_images:
            if img.storage_path and storage_service:
                storage_service.delete(img.storage_path)
                stats['images_deleted_from_disk'] += 1
            img.storage_path = None
            img.state = 'EXPIRED' if not img.seen_at else 'DELETED'
            img.deleted_at = now_utc

        # 2. Ephemeral Images that have been consumed or seen whose files should be deleted
        consumed_images = MessageImage.query.filter(
            MessageImage.state.in_(['CONSUMED', 'SEEN']),
            MessageImage.storage_path != None,
            MessageImage.consumed_at != None
        ).all()

        for img in consumed_images:
            if img.storage_path and storage_service:
                storage_service.delete(img.storage_path)
                stats['consumed_images_deleted'] += 1
            img.storage_path = None
            img.state = 'DELETED'
            img.deleted_at = now_utc

        # 3. Soft-delete or update content for expired private messages
        expired_messages = Message.query.filter(
            Message.expires_at <= now_utc,
            Message.is_deleted == False
        ).all()

        for msg in expired_messages:
            msg.is_deleted = True
            msg.deleted_at = now_utc
            msg.content = '[ Message expired ]'
            stats['expired_messages_cleaned'] += 1

        # 4. Expired public messages
        expired_public = PublicMessage.query.filter(
            PublicMessage.expires_at <= now_utc,
            PublicMessage.is_deleted == False
        ).all()

        for pmsg in expired_public:
            pmsg.is_deleted = True
            pmsg.deleted_at = now_utc
            pmsg.content = '[ Message expired ]'
            stats['public_messages_cleaned'] += 1

        # 5. Clean up expired tokens
        expired_tokens = AuthToken.query.filter(AuthToken.expires_at <= now_utc).all()
        for tok in expired_tokens:
            db.session.delete(tok)
            stats['tokens_cleaned'] += 1

        db.session.commit()
        logger.info("Ephemeral cleanup executed successfully: %s", stats)
    except Exception as e:
        db.session.rollback()
        logger.error("Error during ephemeral cleanup: %s", str(e))
        raise

    return stats
