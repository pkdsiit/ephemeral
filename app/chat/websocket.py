import logging
from flask import request
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio, db
from app.models.conversation import Conversation
from app.chat.services import send_text_message

logger = logging.getLogger('ephemeral.websocket')


@socketio.on('connect')
def handle_connect():
    if not current_user.is_authenticated:
        return False  # Reject unauthenticated socket connections
    user_room = f"user_{current_user.id}"
    join_room(user_room)
    logger.debug(f"User {current_user.username} connected to socket (room: {user_room})")


@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        leave_room(f"user_{current_user.id}")


@socketio.on('join_conversation')
def handle_join_conversation(data):
    if not current_user.is_authenticated:
        return {'error': 'Unauthorized'}

    conversation_id = data.get('conversation_id')
    if not conversation_id:
        return {'error': 'Conversation ID required'}

    conv = db.session.get(Conversation, conversation_id)
    if not conv or not conv.is_participant(current_user.id):
        return {'error': 'Access denied'}

    room = f"conversation_{conversation_id}"
    join_room(room)
    return {'status': 'joined', 'room': room}


@socketio.on('leave_conversation')
def handle_leave_conversation(data):
    conversation_id = data.get('conversation_id')
    if conversation_id:
        leave_room(f"conversation_{conversation_id}")
    return {'status': 'left'}


@socketio.on('send_private_message')
def handle_socket_send_message(data):
    if not current_user.is_authenticated:
        return {'error': 'Unauthorized'}

    conversation_id = data.get('conversation_id')
    content = data.get('content')

    try:
        msg = send_text_message(
            sender_id=current_user.id,
            conversation_id=conversation_id,
            content=content
        )
        return {'status': 'ok', 'message_id': msg.id}
    except Exception as e:
        return {'error': str(e)}


@socketio.on('typing_start')
def handle_typing_start(data):
    if not current_user.is_authenticated:
        return
    conversation_id = data.get('conversation_id')
    if conversation_id:
        emit(
            'user_typing',
            {'user_id': current_user.id, 'username': current_user.username, 'conversation_id': conversation_id},
            to=f"conversation_{conversation_id}",
            include_self=False
        )


@socketio.on('typing_stop')
def handle_typing_stop(data):
    if not current_user.is_authenticated:
        return
    conversation_id = data.get('conversation_id')
    if conversation_id:
        emit(
            'user_stopped_typing',
            {'user_id': current_user.id, 'username': current_user.username, 'conversation_id': conversation_id},
            to=f"conversation_{conversation_id}",
            include_self=False
        )
