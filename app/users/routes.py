import re
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user, logout_user
from sqlalchemy.exc import IntegrityError
from app.extensions import db, limiter, storage_service
from app.models.user import User
from app.models.friendship import Friendship, Block
from app.models.report import Report
from app.storage import sanitize_and_process_image
from app.users.forms import UpdateUsernameForm, UpdateProfileForm, ReportUserForm
from app.auth.forms import ChangePasswordForm

users_bp = Blueprint('users', __name__)


@users_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = UpdateProfileForm()
    if form.validate_on_submit():
        current_user.display_name = form.display_name.data.strip() if form.display_name.data else None
        current_user.bio = form.bio.data.strip() if form.bio.data else None

        if form.avatar.data:
            try:
                cleaned_bytes, ext, mime = sanitize_and_process_image(form.avatar.data.stream, is_avatar=True)
                # Delete old avatar if exists
                if current_user.avatar_path and storage_service:
                    storage_service.delete(current_user.avatar_path)

                storage_path = storage_service.save(cleaned_bytes, f"avatar_{current_user.id}{ext}", subfolder='avatars')
                current_user.avatar_path = storage_path
            except ValueError as e:
                flash(f"Avatar upload failed: {str(e)}", "danger")
                return render_template('users/profile.html', form=form)

        db.session.commit()
        flash("Profile updated successfully!", "success")
        return redirect(url_for('users.profile'))

    elif request.method == 'GET':
        form.display_name.data = current_user.display_name
        form.bio.data = current_user.bio

    return render_template('users/profile.html', form=form)


@users_bp.route('/profile/<username>')
@login_required
def view_user_profile(username):
    target_user = User.query.filter_by(username_lower=username.lower()).first_or_404()
    if target_user.id == current_user.id:
        return redirect(url_for('users.profile'))

    is_blocked = current_user.has_blocked(target_user.id)
    is_blocked_by = current_user.is_blocked_by(target_user.id)
    
    # Friendship status
    friendship = Friendship.query.filter(
        ((Friendship.requester_id == current_user.id) & (Friendship.addressee_id == target_user.id)) |
        ((Friendship.requester_id == target_user.id) & (Friendship.addressee_id == current_user.id))
    ).first()

    report_form = ReportUserForm()
    return render_template(
        'users/user_profile.html',
        user=target_user,
        is_blocked=is_blocked,
        is_blocked_by=is_blocked_by,
        friendship=friendship,
        report_form=report_form
    )


@users_bp.route('/settings', methods=['GET'])
@login_required
def settings():
    username_form = UpdateUsernameForm(username=current_user.username)
    password_form = ChangePasswordForm()
    return render_template('users/settings.html', username_form=username_form, password_form=password_form)


@users_bp.route('/settings/username', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def update_username():
    form = UpdateUsernameForm()
    password_form = ChangePasswordForm()
    if form.validate_on_submit():
        new_username = form.username.data.strip()
        new_username_lower = new_username.lower()

        if new_username_lower == current_user.username_lower:
            flash("Username unchanged.", "info")
            return redirect(url_for('users.settings'))

        # Atomic database update with unique check
        try:
            current_user.username = new_username
            current_user.username_lower = new_username_lower
            current_user.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            flash(f"Your username has been changed to @{new_username}.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("Username is already taken.", "danger")
        return redirect(url_for('users.settings'))

    return render_template('users/settings.html', username_form=form, password_form=password_form)


@users_bp.route('/settings/password', methods=['POST'])
@login_required
def update_password():
    username_form = UpdateUsernameForm(username=current_user.username)
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
            return render_template('users/settings.html', username_form=username_form, password_form=form)

        current_user.set_password(form.new_password.data)
        current_user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash("Password updated successfully.", "success")
        return redirect(url_for('users.settings'))

    return render_template('users/settings.html', username_form=username_form, password_form=form)


@users_bp.route('/settings/privacy', methods=['POST'])
@login_required
def update_privacy_settings():
    show_username = bool(request.form.get('show_username_in_public_chat'))
    current_user.show_username_in_public_chat = show_username
    current_user.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    flash(f"Public chat privacy updated: Username is now {'visible' if show_username else 'hidden (Anonymous)'} in public rooms.", "success")
    return redirect(url_for('users.settings'))


@users_bp.route('/api/settings/privacy', methods=['POST'])
@login_required
def api_update_privacy():
    data = request.get_json(silent=True) or request.form or {}
    show_username = data.get('show_username_in_public_chat')
    if isinstance(show_username, str):
        show_username = show_username.lower() in ('true', '1', 'on', 'yes', 'y')
    else:
        show_username = bool(show_username)

    current_user.show_username_in_public_chat = show_username
    current_user.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({
        'message': 'Privacy setting updated successfully',
        'show_username_in_public_chat': current_user.show_username_in_public_chat
    }), 200


@users_bp.route('/settings/delete-avatar', methods=['POST'])
@login_required
def delete_avatar():
    if current_user.avatar_path and storage_service:
        storage_service.delete(current_user.avatar_path)
    current_user.avatar_path = None
    db.session.commit()
    flash("Profile picture removed.", "info")
    return redirect(url_for('users.profile'))


@users_bp.route('/settings/delete-account', methods=['POST'])
@login_required
def delete_account():
    # Remove avatar file
    if current_user.avatar_path and storage_service:
        storage_service.delete(current_user.avatar_path)

    user_id = current_user.id
    logout_user()
    user = db.session.get(User, user_id)
    if user:
        db.session.delete(user)
        db.session.commit()

    flash("Your account and associated data have been permanently deleted.", "info")
    return redirect(url_for('main.index'))


@users_bp.route('/users/search', methods=['GET'])
@login_required
def search_page():
    query = request.args.get('q', '').strip()
    results = []
    if query:
        # Filter out current user and blocked users
        blocked_subquery = db.session.query(Block.blocked_id).filter(Block.blocker_id == current_user.id)
        blocker_subquery = db.session.query(Block.blocker_id).filter(Block.blocked_id == current_user.id)

        clean_q = query.lstrip('@')
        results = User.query.filter(
            User.id != current_user.id,
            User.is_active_account == True,
            User.is_suspended == False,
            (User.username_lower.ilike(f"%{clean_q.lower()}%")) | (User.display_name.ilike(f"%{clean_q}%")),
            ~User.id.in_(blocked_subquery),
            ~User.id.in_(blocker_subquery)
        ).limit(30).all()

    return render_template('users/search.html', query=query, results=results)


@users_bp.route('/friends', methods=['GET'])
@login_required
def friends_page():
    # Accepted friendships
    accepted_sent = Friendship.query.filter_by(requester_id=current_user.id, status='ACCEPTED').all()
    accepted_recv = Friendship.query.filter_by(addressee_id=current_user.id, status='ACCEPTED').all()
    friends = [f.addressee for f in accepted_sent] + [f.requester for f in accepted_recv]

    # Pending received requests
    pending_received = Friendship.query.filter_by(addressee_id=current_user.id, status='PENDING').all()
    # Pending sent requests
    pending_sent = Friendship.query.filter_by(requester_id=current_user.id, status='PENDING').all()
    # Blocked list
    blocked_list = Block.query.filter_by(blocker_id=current_user.id).all()

    return render_template(
        'users/friends.html',
        friends=friends,
        pending_received=pending_received,
        pending_sent=pending_sent,
        blocked_list=blocked_list
    )


# ---------------- API Endpoints ----------------

@users_bp.route('/api/users/search', methods=['GET'])
@login_required
def api_search_users():
    query = request.args.get('q', '').strip().lstrip('@')
    if not query:
        return jsonify({'users': []}), 200

    blocked_subquery = db.session.query(Block.blocked_id).filter(Block.blocker_id == current_user.id)
    blocker_subquery = db.session.query(Block.blocker_id).filter(Block.blocked_id == current_user.id)

    users = User.query.filter(
        User.id != current_user.id,
        User.is_active_account == True,
        User.is_suspended == False,
        (User.username_lower.ilike(f"%{query.lower()}%")) | (User.display_name.ilike(f"%{query}%")),
        ~User.id.in_(blocked_subquery),
        ~User.id.in_(blocker_subquery)
    ).limit(20).all()

    return jsonify({'users': [u.get_public_profile() for u in users]}), 200


@users_bp.route('/api/users/<username>', methods=['GET'])
@login_required
def api_get_user(username):
    clean_username = username.strip().lstrip('@').lower()
    target_user = User.query.filter_by(username_lower=clean_username).first()
    if not target_user or not target_user.is_active:
        return jsonify({'error': 'User not found.'}), 404

    if current_user.is_mutually_blocked(target_user.id):
        return jsonify({'error': 'User not found.'}), 404

    return jsonify({'user': target_user.get_public_profile()}), 200


@users_bp.route('/api/users/me/username', methods=['PATCH'])
@login_required
@limiter.limit("10 per hour")
def api_update_username():
    data = request.get_json() or {}
    new_username = (data.get('username') or '').strip()

    if not new_username or len(new_username) < 3 or len(new_username) > 30:
        return jsonify({'error': 'Username must be between 3 and 30 characters.'}), 400

    if not re.match(r'^[a-zA-Z0-9_]+$', new_username):
        return jsonify({'error': 'Username may only contain letters, numbers, and underscores.'}), 400

    new_lower = new_username.lower()
    if new_lower == current_user.username_lower:
        return jsonify({'message': 'Username unchanged', 'user': current_user.get_public_profile()}), 200

    existing = User.query.filter_by(username_lower=new_lower).first()
    if existing and existing.id != current_user.id:
        return jsonify({'error': 'Username is already taken.'}), 409

    try:
        current_user.username = new_username
        current_user.username_lower = new_lower
        current_user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Username is already taken.'}), 409

    return jsonify({
        'message': 'Username updated successfully',
        'user': current_user.get_public_profile()
    }), 200


@users_bp.route('/api/friends', methods=['GET'])
@login_required
def api_get_friends():
    friends = current_user.get_friends()
    pending_sent = current_user.get_pending_friend_requests_sent()
    pending_received = current_user.get_pending_friend_requests_received()

    return jsonify({
        'friends': [f.get_public_profile() for f in friends],
        'pending_sent': [r.to_dict(current_user.id) for r in pending_sent],
        'pending_received': [r.to_dict(current_user.id) for r in pending_received]
    }), 200


@users_bp.route('/api/friends/request', methods=['POST'])
@login_required
def api_send_friend_request():
    data = request.get_json() or {}
    target_username = (data.get('username') or '').strip().lstrip('@').lower()
    target_id = data.get('user_id')

    if target_id:
        target_user = db.session.get(User, target_id)
    elif target_username:
        target_user = User.query.filter_by(username_lower=target_username).first()
    else:
        return jsonify({'error': 'Recipient identifier is required.'}), 400

    if not target_user or target_user.id == current_user.id:
        return jsonify({'error': 'Invalid target user.'}), 400

    if current_user.is_mutually_blocked(target_user.id):
        return jsonify({'error': 'Cannot connect with this user.'}), 403

    # Check existing friendship or request
    existing = Friendship.query.filter(
        ((Friendship.requester_id == current_user.id) & (Friendship.addressee_id == target_user.id)) |
        ((Friendship.requester_id == target_user.id) & (Friendship.addressee_id == current_user.id))
    ).first()

    if existing:
        if existing.status == 'ACCEPTED':
            return jsonify({'message': 'Already connected.', 'status': 'ACCEPTED'}), 200
        elif existing.status == 'PENDING':
            if existing.requester_id == current_user.id:
                return jsonify({'message': 'Friend request already pending.', 'status': 'PENDING'}), 200
            else:
                # Target already requested current user; accept automatically
                existing.status = 'ACCEPTED'
                db.session.commit()
                return jsonify({'message': 'Friend request accepted.', 'status': 'ACCEPTED'}), 200
        elif existing.status == 'REJECTED':
            existing.status = 'PENDING'
            existing.requester_id = current_user.id
            existing.addressee_id = target_user.id
            db.session.commit()
            return jsonify({'message': 'Friend request sent.', 'status': 'PENDING'}), 200

    new_friendship = Friendship(
        requester_id=current_user.id,
        addressee_id=target_user.id,
        status='PENDING'
    )
    db.session.add(new_friendship)
    db.session.commit()

    return jsonify({'message': 'Friend request sent successfully.', 'status': 'PENDING'}), 201


@users_bp.route('/api/friends/<friendship_id>/accept', methods=['POST'])
@login_required
def api_accept_friend_request(friendship_id):
    req = Friendship.query.get_or_404(friendship_id)
    if req.addressee_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    req.status = 'ACCEPTED'
    db.session.commit()
    return jsonify({'message': 'Friend request accepted.', 'friendship': req.to_dict(current_user.id)}), 200


@users_bp.route('/api/friends/<friendship_id>/reject', methods=['POST'])
@login_required
def api_reject_friend_request(friendship_id):
    req = Friendship.query.get_or_404(friendship_id)
    if req.addressee_id != current_user.id and req.requester_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.delete(req)
    db.session.commit()
    return jsonify({'message': 'Friend request rejected/removed.'}), 200


@users_bp.route('/api/friends/<friendship_id>/remove', methods=['POST', 'DELETE'])
@login_required
def api_remove_friend(friendship_id):
    req = Friendship.query.get_or_404(friendship_id)
    if req.addressee_id != current_user.id and req.requester_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    db.session.delete(req)
    db.session.commit()
    return jsonify({'message': 'Friend removed successfully.'}), 200


@users_bp.route('/api/users/<user_id>/block', methods=['POST'])
@login_required
def api_block_user(user_id):
    if user_id == current_user.id:
        return jsonify({'error': 'Cannot block yourself.'}), 400

    target_user = User.query.get_or_404(user_id)

    # Check if already blocked
    existing_block = Block.query.filter_by(blocker_id=current_user.id, blocked_id=target_user.id).first()
    if not existing_block:
        block = Block(blocker_id=current_user.id, blocked_id=target_user.id)
        db.session.add(block)

    # Clean up friendship if any
    Friendship.query.filter(
        ((Friendship.requester_id == current_user.id) & (Friendship.addressee_id == target_user.id)) |
        ((Friendship.requester_id == target_user.id) & (Friendship.addressee_id == current_user.id))
    ).delete()

    db.session.commit()
    return jsonify({'message': f"@{target_user.username} has been blocked."}), 200


@users_bp.route('/api/users/<user_id>/unblock', methods=['POST'])
@login_required
def api_unblock_user(user_id):
    block = Block.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    if block:
        db.session.delete(block)
        db.session.commit()
    return jsonify({'message': 'User unblocked successfully.'}), 200


@users_bp.route('/api/users/<user_id>/report', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def api_report_user(user_id):
    target_user = User.query.get_or_404(user_id)
    data = request.get_json() or {}
    reason = (data.get('reason') or '').strip()
    details = (data.get('details') or '').strip()
    message_id = data.get('message_id')
    public_message_id = data.get('public_message_id')

    if not reason:
        return jsonify({'error': 'Reason is required for report.'}), 400

    report = Report(
        reporter_id=current_user.id,
        reported_user_id=target_user.id,
        message_id=message_id,
        public_message_id=public_message_id,
        reason=reason,
        details=details
    )
    db.session.add(report)
    db.session.commit()

    return jsonify({'message': 'Report submitted to moderators. Thank you for keeping Ephemeral safe.'}), 201
