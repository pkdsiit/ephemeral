import os
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, current_app
from flask_login import login_required, current_user
from app.models.conversation import ConversationParticipant
from app.models.friendship import Friendship
from app.models.public_room import PublicRoom
from app.models.message import Message
from app.dating.services import get_dating_matches
from app.tasks.cleanup import cleanup_expired_content

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('main/index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Fetch recent conversations
    participants = ConversationParticipant.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).all()

    convs = []
    total_unread = 0
    for p in participants:
        conv = p.conversation
        if conv:
            data = conv.to_dict(current_user.id)
            if data.get('other_user'):
                convs.append(data)
                total_unread += data.get('unread_count', 0)

    convs.sort(key=lambda x: x.get('last_message_at') or '', reverse=True)
    recent_convs = convs[:5]

    # Incoming friend requests count
    pending_requests_count = Friendship.query.filter_by(
        addressee_id=current_user.id,
        status='PENDING'
    ).count()

    # Public rooms
    from app.public_chat.routes import seed_public_rooms
    seed_public_rooms()
    public_rooms = PublicRoom.query.filter_by(is_active=True).all()

    # Dating suggestions preview
    dating_matches = []
    if current_user.dating_profile and current_user.dating_profile.enabled:
        dating_matches = get_dating_matches(current_user.id, limit=3)

    return render_template(
        'main/dashboard.html',
        recent_conversations=recent_convs,
        total_conversations_count=len(convs),
        total_unread=total_unread,
        pending_requests_count=pending_requests_count,
        public_rooms=public_rooms,
        dating_matches=dating_matches,
        user=current_user
    )


@main_bp.route('/healthz')
def health_check():
    return jsonify({
        'status': 'healthy',
        'app': 'Ephemeral Chat',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 200


@main_bp.route('/api/cleanup', methods=['POST'])
def trigger_cleanup():
    """
    Cleanup endpoint suitable for Render cron jobs / external scheduled workers.
    Protected by SECRET_KEY header or admin session.
    """
    secret = request.headers.get('X-Cleanup-Secret') or request.args.get('secret')
    is_authorized = (secret and secret == current_app.config['SECRET_KEY']) or (current_user.is_authenticated and current_user.is_admin)

    if not is_authorized:
        return jsonify({'error': 'Unauthorized'}), 401

    stats = cleanup_expired_content()
    return jsonify({
        'message': 'Ephemeral cleanup executed successfully',
        'stats': stats
    }), 200
