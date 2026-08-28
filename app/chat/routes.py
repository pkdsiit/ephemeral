from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db, limiter
from app.models.user import User
from app.models.conversation import Conversation, ConversationParticipant
from app.models.message import Message
from app.chat.services import (
    get_or_create_direct_conversation,
    send_text_message,
    send_image_message,
    delete_message,
    delete_conversation
)

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/chats', methods=['GET'])
@login_required
def index():
    # Fetch active conversations
    participants = ConversationParticipant.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()

    conv_list = []
    for p in participants:
        conv = p.conversation
        if conv:
            conv_data = conv.to_dict(current_user.id)
            if conv_data.get('other_user'):
                conv_list.append(conv_data)

    # Sort by last message time
    conv_list.sort(key=lambda x: x.get('last_message_at') or '', reverse=True)
    return render_template('chat/index.html', conversations=conv_list)


@chat_bp.route('/chat/<username>', methods=['GET'])
@login_required
def chat_with_user(username):
    clean_username = username.strip().lstrip('@').lower()
    target_user = User.query.filter_by(username_lower=clean_username).first_or_404()

    if target_user.id == current_user.id:
        flash("You cannot start a chat with yourself.", "warning")
        return redirect(url_for('chat.index'))

    if current_user.is_mutually_blocked(target_user.id):
        flash("Cannot open conversation due to block settings.", "danger")
        return redirect(url_for('chat.index'))

    conv = get_or_create_direct_conversation(current_user.id, target_user.id)
    return redirect(url_for('chat.conversation_view', conversation_id=conv.id))


@chat_bp.route('/chat/c/<conversation_id>', methods=['GET'])
@login_required
def conversation_view(conversation_id):
    conv = Conversation.query.get_or_404(conversation_id)
    if not conv.is_participant(current_user.id):
        flash("You are not authorized to access this conversation.", "danger")
        return redirect(url_for('chat.index'))

    other_user = conv.get_other_participant(current_user.id)
    if not other_user:
        flash("Recipient no longer available.", "danger")
        return redirect(url_for('chat.index'))

    # Mark as read
    participant = conv.get_participant_record(current_user.id)
    if participant:
        participant.last_read_at = datetime.now(timezone.utc)
        db.session.commit()

    return render_template('chat/conversation.html', conversation=conv, other_user=other_user)


# ---------------- REST API Endpoints ----------------

@chat_bp.route('/api/chats', methods=['GET'])
@login_required
def api_get_conversations():
    participants = ConversationParticipant.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()

    convs = []
    for p in participants:
        conv = p.conversation
        if conv:
            data = conv.to_dict(current_user.id)
            if data.get('other_user'):
                convs.append(data)

    convs.sort(key=lambda x: x.get('last_message_at') or '', reverse=True)
    return jsonify({'conversations': convs}), 200


@chat_bp.route('/api/chats', methods=['POST'])
@login_required
def api_start_conversation():
    data = request.get_json() or {}
    target_username = (data.get('username') or '').strip().lstrip('@').lower()
    target_id = data.get('user_id')

    if target_id:
        target_user = db.session.get(User, target_id)
    elif target_username:
        target_user = User.query.filter_by(username_lower=target_username).first()
    else:
        return jsonify({'error': 'Target user is required.'}), 400

    if not target_user or target_user.id == current_user.id:
        return jsonify({'error': 'Invalid target user.'}), 400

    try:
        conv = get_or_create_direct_conversation(current_user.id, target_user.id)
        return jsonify({
            'message': 'Conversation ready',
            'conversation': conv.to_dict(current_user.id)
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@chat_bp.route('/api/chats/<conversation_id>/messages', methods=['GET'])
@login_required
def api_get_messages(conversation_id):
    conv = Conversation.query.get_or_404(conversation_id)
    if not conv.is_participant(current_user.id):
        return jsonify({'error': 'Unauthorized to access this conversation.'}), 403

    participant = conv.get_participant_record(current_user.id)
    now_utc = datetime.now(timezone.utc)

    query = conv.messages.filter(
        Message.is_deleted == False,
        Message.expires_at > now_utc
    )

    if participant and participant.cleared_history_at:
        query = query.filter(Message.created_at > participant.cleared_history_at)

    messages = query.all()
    
    # Mark read timestamp
    if participant:
        participant.last_read_at = now_utc
        db.session.commit()

    return jsonify({
        'messages': [m.to_dict(current_user_id=current_user.id) for m in messages]
    }), 200


@chat_bp.route('/api/chats/<conversation_id>/messages', methods=['POST'])
@login_required
@limiter.limit("120 per minute")
def api_send_message(conversation_id):
    data = request.get_json() or {}
    content = (data.get('content') or '').strip()

    if not content:
        return jsonify({'error': 'Message content is required.'}), 400

    try:
        msg = send_text_message(
            sender_id=current_user.id,
            conversation_id=conversation_id,
            content=content
        )
        return jsonify({
            'message': 'Sent',
            'data': msg.to_dict(current_user_id=current_user.id)
        }), 201
    except (ValueError, PermissionError) as e:
        return jsonify({'error': str(e)}), 400


@chat_bp.route('/api/chats/<conversation_id>/images', methods=['POST'])
@login_required
@limiter.limit("30 per minute")
def api_upload_image(conversation_id):
    if 'image' not in request.files:
        return jsonify({'error': 'No image file uploaded.'}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'No selected file.'}), 400

    try:
        msg = send_image_message(
            sender_id=current_user.id,
            conversation_id=conversation_id,
            file_stream_or_bytes=file.stream,
            original_filename=file.filename
        )
        return jsonify({
            'message': 'Ephemeral image sent successfully',
            'data': msg.to_dict(current_user_id=current_user.id)
        }), 201
    except ValueError as e:
        return jsonify({'error': f"Invalid image: {str(e)}"}), 400
    except (PermissionError, Exception) as e:
        return jsonify({'error': str(e)}), 400


@chat_bp.route('/api/messages/<message_id>', methods=['DELETE'])
@login_required
def api_delete_message(message_id):
    try:
        delete_message(current_user.id, message_id)
        return jsonify({'message': 'Message deleted.'}), 200
    except (ValueError, PermissionError) as e:
        return jsonify({'error': str(e)}), 403


@chat_bp.route('/api/chats/<conversation_id>', methods=['DELETE'])
@login_required
def api_delete_conversation(conversation_id):
    try:
        delete_conversation(current_user.id, conversation_id)
        return jsonify({'message': 'Conversation cleared.'}), 200
    except PermissionError as e:
        return jsonify({'error': str(e)}), 403


@chat_bp.route('/api/chats/<conversation_id>/read', methods=['POST'])
@login_required
def api_mark_read(conversation_id):
    conv = Conversation.query.get_or_404(conversation_id)
    if not conv.is_participant(current_user.id):
        return jsonify({'error': 'Unauthorized'}), 403

    p = conv.get_participant_record(current_user.id)
    if p:
        p.last_read_at = datetime.now(timezone.utc)
        db.session.commit()
    return jsonify({'message': 'Conversation marked as read'}), 200
