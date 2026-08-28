from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db, limiter, socketio
from app.models.public_room import PublicRoom, PublicMessage
from app.utils import utcnow

public_chat_bp = Blueprint('public_chat', __name__)

DEFAULT_ROOMS = [
    ('general', 'General Chat', 'The main public square for all ephemeral community conversations.'),
    ('random', 'Random Thoughts', 'Spontaneous musings, jokes, and ephemeral daily banter.'),
    ('dating-discussion', 'Dating Discussion', 'Respectful discussions around modern dating, advice, and tips.')
]


def seed_public_rooms():
    """Ensure default public chat rooms exist in database."""
    for code, name, desc in DEFAULT_ROOMS:
        if not PublicRoom.query.filter_by(code=code).first():
            room = PublicRoom(code=code, name=name, description=desc, is_active=True)
            db.session.add(room)
    db.session.commit()


@public_chat_bp.route('/public', methods=['GET'])
@login_required
def index():
    seed_public_rooms()
    rooms = PublicRoom.query.filter_by(is_active=True).all()
    return render_template('public_chat/index.html', rooms=rooms)


@public_chat_bp.route('/public/<room_code>', methods=['GET'])
@login_required
def room_view(room_code):
    seed_public_rooms()
    room = PublicRoom.query.filter_by(code=room_code, is_active=True).first_or_404()
    
    # Recent non-expired messages
    now_utc = utcnow()
    messages = room.messages.filter(
        PublicMessage.is_deleted == False,
        PublicMessage.expires_at > now_utc
    ).order_by(PublicMessage.created_at.asc()).limit(100).all()

    return render_template('public_chat/room.html', room=room, messages=messages)


# ---------------- API Endpoints ----------------

@public_chat_bp.route('/api/public/rooms', methods=['GET'])
@login_required
def api_get_rooms():
    seed_public_rooms()
    rooms = PublicRoom.query.filter_by(is_active=True).all()
    return jsonify({'rooms': [r.to_dict() for r in rooms]}), 200


@public_chat_bp.route('/api/public/rooms/<room_code>/messages', methods=['GET'])
@login_required
def api_get_room_messages(room_code):
    room = PublicRoom.query.filter_by(code=room_code, is_active=True).first_or_404()
    now_utc = utcnow()
    messages = room.messages.filter(
        PublicMessage.is_deleted == False,
        PublicMessage.expires_at > now_utc
    ).order_by(PublicMessage.created_at.asc()).limit(100).all()

    return jsonify({'messages': [m.to_dict(current_user.id) for m in messages]}), 200


@public_chat_bp.route('/api/public/rooms/<room_code>/messages', methods=['POST'])
@login_required
@limiter.limit("60 per minute")
def api_send_room_message(room_code):
    room = PublicRoom.query.filter_by(code=room_code, is_active=True).first_or_404()
    data = request.get_json() or {}
    content = (data.get('content') or '').strip()

    if not content:
        return jsonify({'error': 'Message content is required.'}), 400

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

    # Emit socket broadcast
    try:
        socketio.emit(
            'new_public_message',
            msg.to_dict(current_user_id=None),
            to=f"public_room_{room.code}"
        )
    except Exception as e:
        pass

    return jsonify({
        'message': 'Sent',
        'data': msg.to_dict(current_user.id)
    }), 201


@public_chat_bp.route('/api/public/messages/<message_id>', methods=['DELETE'])
@login_required
def api_delete_public_message(message_id):
    msg = PublicMessage.query.get_or_404(message_id)
    if msg.user_id != current_user.id and not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    msg.is_deleted = True
    msg.deleted_at = utcnow()
    db.session.commit()

    try:
        socketio.emit(
            'public_message_deleted',
            {'message_id': message_id, 'room_code': msg.room.code},
            to=f"public_room_{msg.room.code}"
        )
    except Exception:
        pass

    return jsonify({'message': 'Public message deleted.'}), 200
