import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, List
from app.extensions import db, storage_service, socketio
from app.models.user import User
from app.models.conversation import Conversation, ConversationParticipant
from app.models.message import Message, MessageImage
from app.storage import sanitize_and_process_image
from app.utils import utcnow

logger = logging.getLogger('ephemeral.chat')


def get_or_create_direct_conversation(user1_id: str, user2_id: str) -> Conversation:
    """Find or create a 1-to-1 conversation between two users."""
    if user1_id == user2_id:
        raise ValueError("Cannot create a conversation with yourself.")

    user1 = db.session.get(User, user1_id)
    user2 = db.session.get(User, user2_id)
    if not user1 or not user2:
        raise ValueError("One or both users do not exist.")

    if user1.is_mutually_blocked(user2_id):
        raise ValueError("Cannot initiate conversation due to user block settings.")

    # Find conversation where both users are participants
    conv_ids_1 = db.session.query(ConversationParticipant.conversation_id).filter_by(user_id=user1_id)
    common_conv = db.session.query(Conversation).join(
        ConversationParticipant
    ).filter(
        ConversationParticipant.user_id == user2_id,
        Conversation.id.in_(conv_ids_1),
        Conversation.is_group == False
    ).first()

    if common_conv:
        # Re-activate participants if inactive
        for p in common_conv.participants:
            p.is_active = True
        db.session.commit()
        return common_conv

    # Create new conversation
    conv = Conversation(is_group=False)
    db.session.add(conv)
    db.session.flush()

    p1 = ConversationParticipant(conversation_id=conv.id, user_id=user1_id)
    p2 = ConversationParticipant(conversation_id=conv.id, user_id=user2_id)
    db.session.add_all([p1, p2])
    db.session.commit()

    return conv


def check_and_delete_consumed_images_on_new_message(sender_id: str, conversation_id: str) -> int:
    """
    CRITICAL EPHEMERAL REQUIREMENT:
    When a recipient has viewed/consumed an ephemeral image and subsequently sends a NEW message
    in that conversation, the server physically deletes the viewed ephemeral image(s) from storage.
    """
    now_utc = utcnow()
    # Find images sent by the OTHER user in this conversation that were viewed/consumed
    consumed_images = MessageImage.query.join(Message).filter(
        Message.conversation_id == conversation_id,
        Message.sender_id != sender_id,  # sent by other participant
        MessageImage.state.in_(['SEEN', 'CONSUMED']),
        MessageImage.storage_path != None
    ).all()

    deleted_count = 0
    for img in consumed_images:
        if img.storage_path and storage_service:
            storage_service.delete(img.storage_path)
            deleted_count += 1

        img.storage_path = None
        img.state = 'DELETED'
        img.deleted_at = now_utc

        # Emit live socket update for this deleted image
        try:
            socketio.emit(
                'image_deleted',
                {
                    'image_id': img.id,
                    'message_id': img.message_id,
                    'conversation_id': conversation_id,
                    'reason': 'consumed_on_reply'
                },
                to=f"conversation_{conversation_id}"
            )
        except Exception as e:
            logger.warning(f"Socket emit failed: {e}")

    return deleted_count


def send_text_message(sender_id: str, conversation_id: str, content: str) -> Message:
    """Send a text message and trigger ephemeral image cleanup for previously viewed images."""
    if not content or not content.strip():
        raise ValueError("Message content cannot be empty.")

    conv = db.session.get(Conversation, conversation_id)
    if not conv:
        raise ValueError("Conversation not found.")

    if not conv.is_participant(sender_id):
        raise PermissionError("You are not a participant in this conversation.")

    other_user = conv.get_other_participant(sender_id)
    if other_user and db.session.get(User, sender_id).is_mutually_blocked(other_user.id):
        raise PermissionError("Cannot send message: communication is blocked.")

    # 1. Trigger deletion of any previously consumed ephemeral images in this conversation
    check_and_delete_consumed_images_on_new_message(sender_id, conversation_id)

    # 2. Create new message
    now_utc = utcnow()
    expires_at = now_utc + timedelta(days=7)

    message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        message_type='TEXT',
        content=content.strip(),
        created_at=now_utc,
        expires_at=expires_at
    )
    db.session.add(message)

    # Update conversation last message timestamp
    conv.last_message_at = now_utc
    conv.updated_at = now_utc

    # Reactivate participant if previously cleared
    sender_participant = conv.get_participant_record(sender_id)
    if sender_participant:
        sender_participant.is_active = True
        sender_participant.last_read_at = now_utc

    other_participant = conv.get_participant_record(other_user.id) if other_user else None
    if other_participant:
        other_participant.is_active = True

    db.session.commit()

    # Emit real-time message event via SocketIO
    try:
        socketio.emit(
            'new_message',
            message.to_dict(current_user_id=None),
            to=f"conversation_{conversation_id}"
        )
    except Exception as e:
        logger.warning(f"Socket emit failed: {e}")

    return message


def send_image_message(sender_id: str, conversation_id: str, file_stream_or_bytes, original_filename: str) -> Message:
    """Upload and send an ephemeral image message."""
    conv = db.session.get(Conversation, conversation_id)
    if not conv:
        raise ValueError("Conversation not found.")

    if not conv.is_participant(sender_id):
        raise PermissionError("You are not a participant in this conversation.")

    other_user = conv.get_other_participant(sender_id)
    if other_user and db.session.get(User, sender_id).is_mutually_blocked(other_user.id):
        raise PermissionError("Cannot send image: communication is blocked.")

    # 1. Trigger deletion of any previously consumed ephemeral images
    check_and_delete_consumed_images_on_new_message(sender_id, conversation_id)

    # 2. Sanitize and save image
    cleaned_bytes, ext, mime_type = sanitize_and_process_image(file_stream_or_bytes, is_avatar=False)
    storage_path = storage_service.save(cleaned_bytes, original_filename, subfolder='private_images')

    now_utc = utcnow()
    expires_at = now_utc + timedelta(days=7)

    message = Message(
        conversation_id=conversation_id,
        sender_id=sender_id,
        message_type='IMAGE',
        content='[ Ephemeral Image ]',
        created_at=now_utc,
        expires_at=expires_at
    )
    db.session.add(message)
    db.session.flush()

    message_image = MessageImage(
        message=message,
        storage_path=storage_path,
        original_filename=original_filename,
        mime_type=mime_type,
        file_size=len(cleaned_bytes),
        state='UPLOADED'
    )
    db.session.add(message_image)

    conv.last_message_at = now_utc
    conv.updated_at = now_utc

    sender_participant = conv.get_participant_record(sender_id)
    if sender_participant:
        sender_participant.is_active = True
        sender_participant.last_read_at = now_utc

    other_participant = conv.get_participant_record(other_user.id) if other_user else None
    if other_participant:
        other_participant.is_active = True

    db.session.commit()

    # Emit real-time message event
    try:
        socketio.emit(
            'new_message',
            message.to_dict(current_user_id=None),
            to=f"conversation_{conversation_id}"
        )
    except Exception as e:
        logger.warning(f"Socket emit failed: {e}")

    return message


def view_ephemeral_image(user_id: str, image_id: str) -> Tuple[bytes, str]:
    """
    Access-controlled retrieval of ephemeral image.
    Marks the image as SEEN / CONSUMED.
    """
    image = db.session.get(MessageImage, image_id)
    if not image or not image.storage_path:
        raise FileNotFoundError("This image is no longer available or has expired.")

    message = image.message
    if not message or message.is_deleted or message.is_expired:
        raise FileNotFoundError("This image has expired or was deleted.")

    conv = message.conversation
    if not conv or not conv.is_participant(user_id):
        raise PermissionError("You are not authorized to view this image.")

    if image.state in ('DELETED', 'EXPIRED'):
        raise FileNotFoundError("This image has already been consumed and deleted.")

    # Retrieve bytes from storage
    image_bytes = storage_service.get(image.storage_path)
    if not image_bytes:
        raise FileNotFoundError("Image file is missing from storage.")

    now_utc = utcnow()

    # If the viewer is the recipient (not the sender)
    if user_id != message.sender_id:
        image.state = 'CONSUMED'
        if not image.seen_at:
            image.seen_at = now_utc
        image.consumed_at = now_utc
        image.view_count += 1
        
        message.is_seen = True
        message.seen_at = now_utc

        db.session.commit()

        # Emit real-time seen event
        try:
            socketio.emit(
                'image_seen',
                {
                    'image_id': image.id,
                    'message_id': message.id,
                    'conversation_id': conv.id,
                    'seen_at': now_utc.isoformat()
                },
                to=f"conversation_{conv.id}"
            )
        except Exception as e:
            logger.warning(f"Socket emit failed: {e}")

    return image_bytes, image.mime_type


def delete_message(user_id: str, message_id: str) -> bool:
    """Delete an individual message (sender or conversation participant)."""
    message = db.session.get(Message, message_id)
    if not message:
        raise ValueError("Message not found.")

    if message.sender_id != user_id:
        raise PermissionError("You can only delete messages sent by you.")

    now_utc = utcnow()
    conv_id = message.conversation_id

    # If image message, remove physical file
    if message.image and message.image.storage_path:
        storage_service.delete(message.image.storage_path)
        message.image.storage_path = None
        message.image.state = 'DELETED'
        message.image.deleted_at = now_utc

    message.is_deleted = True
    message.deleted_at = now_utc
    message.content = '[ Message deleted by sender ]'
    db.session.commit()

    try:
        socketio.emit(
            'message_deleted',
            {'message_id': message_id, 'conversation_id': conv_id},
            to=f"conversation_{conv_id}"
        )
    except Exception as e:
        logger.warning(f"Socket emit failed: {e}")

    return True


def delete_conversation(user_id: str, conversation_id: str) -> bool:
    """Clear conversation history on user's end, and physically clean files if all participants clear."""
    conv = db.session.get(Conversation, conversation_id)
    if not conv or not conv.is_participant(user_id):
        raise PermissionError("Unauthorized to delete this conversation.")

    participant = conv.get_participant_record(user_id)
    now_utc = utcnow()
    if participant:
        participant.is_active = False
        participant.cleared_history_at = now_utc

    # Check if all participants cleared history
    all_inactive = all(not p.is_active for p in conv.participants)
    if all_inactive:
        # Delete all physical images in this conversation
        images = MessageImage.query.join(Message).filter(
            Message.conversation_id == conversation_id,
            MessageImage.storage_path != None
        ).all()
        for img in images:
            if img.storage_path and storage_service:
                storage_service.delete(img.storage_path)
            img.storage_path = None
            img.state = 'DELETED'
            img.deleted_at = now_utc

        # Hard delete or soft delete messages
        for msg in conv.messages:
            msg.is_deleted = True
            msg.deleted_at = now_utc

    db.session.commit()
    return True
