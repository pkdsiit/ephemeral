import logging
from flask import request
from flask_login import current_user
from flask_socketio import emit, join_room, leave_room
from app.extensions import socketio, db
from app.models.public_room import PublicRoom, PublicMessage
from datetime import datetime, timedelta
from app.utils import utcnow

logger = logging.getLogger('ephemeral.public_websocket')


@socketio.on('join_public_room')
def handle_join_public(data):
    if not current_user.is_authenticated:
        return {'error': 'Unauthorized'}

    room_code = data.get('room_code')
    if not room_code:
        return {'error': 'Room code required'}

    room = PublicRoom.query.filter_by(code=room_code, is_active=True).first()
    if not room:
        return {'error': 'Room not found'}

    socket_room = f"public_room_{room_code}"
    join_room(socket_room)
    return {'status': 'joined', 'room': socket_room}


@socketio.on('leave_public_room')
def handle_leave_public(data):
    room_code = data.get('room_code')
    if room_code:
        leave_room(f"public_room_{room_code}")
    return {'status': 'left'}


@socketio.on('send_public_message')
def handle_send_public_message(data):
    if not current_user.is_authenticated:
        return {'error': 'Unauthorized'}

    room_code = data.get('room_code')
    content = (data.get('content') or '').strip()

    if not room_code or not content:
        return {'error': 'Room code and content required'}

    room = PublicRoom.query.filter_by(code=room_code, is_active=True).first()
    if not room:
        return {'error': 'Room not found'}

    now_utc = utcnow()
    msg = PublicMessage(
        room_id=room.id,
        user_id=current_user.id,
        content=content,
        created_at=now_utc,
        expires_at=now_utc + timedelta(days=7)
    )
    db.session.add(msg)
    db.session.commit()

    socket_room = f"public_room_{room_code}"
    emit(
        'new_public_message',
        msg.to_dict(current_user_id=None),
        to=socket_room
    )

    return {'status': 'ok', 'message_id': msg.id}
