from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db, limiter
from app.models.user import User
from app.models.dating import DatingProfile
from app.models.token import AuthToken
from app.auth.forms import (
    RegistrationForm, LoginForm, ChangePasswordForm,
    ForgotPasswordForm, ResetPasswordForm
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("20 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = RegistrationForm()
    if form.validate_on_submit():
        raw_email = form.email.data.strip().lower()
        raw_username = form.username.data.strip()

        # Create user
        user = User(
            email=raw_email,
            username=raw_username,
            username_lower=raw_username.lower(),
            display_name=raw_username
        )
        user.set_password(form.password.data)

        # Create initial dating profile linked to user (disabled by default)
        dating_profile = DatingProfile(
            user=user,
            enabled=False,
            min_age_pref=18,
            max_age_pref=99
        )

        db.session.add(user)
        db.session.add(dating_profile)
        db.session.commit()

        login_user(user)
        flash("Welcome to Ephemeral! Your privacy-first account has been created.", "success")
        return redirect(url_for('main.dashboard'))

    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("15 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        login_id = form.login_id.data.strip()
        password = form.password.data

        # Search by email or case-insensitive username
        user = User.query.filter(
            (User.email.ilike(login_id.lower())) | (User.username_lower == login_id.lower())
        ).first()

        if user and user.check_password(password):
            if user.is_suspended:
                flash("Your account has been suspended by an administrator.", "danger")
                return render_template('auth/login.html', form=form), 403
            
            user.last_seen_at = datetime.now(timezone.utc)
            db.session.commit()

            login_user(user, remember=form.remember.data)
            flash(f"Welcome back, @{user.username}!", "success")
            
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))
        else:
            flash("Invalid email/username or password. Please check your credentials.", "danger")

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been signed out securely.", "info")
    return redirect(url_for('main.index'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = ForgotPasswordForm()
    reset_link = None

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter(User.email.ilike(email)).first()
        
        if user:
            token_obj, raw_token = AuthToken.create_token(user_id=user.id, token_type='PASSWORD_RESET', expires_in_minutes=60)
            db.session.commit()
            reset_link = url_for('auth.reset_password', token=raw_token, _external=True)
            current_app.logger.info(f"Password reset requested for user {user.id}")

        flash("If an account matches that email, a password reset link has been generated.", "info")
        return render_template('auth/forgot_password.html', form=form, reset_link=reset_link)

    return render_template('auth/forgot_password.html', form=form, reset_link=reset_link)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    token_obj = AuthToken.verify_token(token, token_type='PASSWORD_RESET')
    if not token_obj:
        flash("The password reset link is invalid or has expired.", "danger")
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = token_obj.user
        user.set_password(form.new_password.data)
        token_obj.used_at = datetime.now(timezone.utc)
        db.session.commit()

        flash("Your password has been successfully reset. Please sign in.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form, token=token)


# ---------------- API Endpoints ----------------

@auth_bp.route('/api/auth/register', methods=['POST'])
@limiter.limit("20 per hour")
def api_register():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not email or not username or not password:
        return jsonify({'error': 'Email, username, and password are required.'}), 400

    if len(username) < 3 or len(username) > 30:
        return jsonify({'error': 'Username must be between 3 and 30 characters.'}), 400

    import re
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return jsonify({'error': 'Username may only contain letters, numbers, and underscores.'}), 400

    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters long.'}), 400

    if User.query.filter(User.email.ilike(email)).first():
        return jsonify({'error': 'An account with this email already exists.'}), 409

    if User.query.filter_by(username_lower=username.lower()).first():
        return jsonify({'error': 'Username is already taken.'}), 409

    user = User(
        email=email,
        username=username,
        username_lower=username.lower(),
        display_name=username
    )
    user.set_password(password)

    dating_profile = DatingProfile(user=user, enabled=False)
    db.session.add(user)
    db.session.add(dating_profile)
    db.session.commit()

    login_user(user)
    return jsonify({
        'message': 'Account created successfully',
        'user': user.get_public_profile()
    }), 201


@auth_bp.route('/api/auth/login', methods=['POST'])
@limiter.limit("15 per minute")
def api_login():
    data = request.get_json() or {}
    login_id = (data.get('login_id') or data.get('email') or data.get('username') or '').strip()
    password = data.get('password') or ''

    if not login_id or not password:
        return jsonify({'error': 'Username/email and password are required.'}), 400

    user = User.query.filter(
        (User.email.ilike(login_id.lower())) | (User.username_lower == login_id.lower())
    ).first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials.'}), 401

    if user.is_suspended:
        return jsonify({'error': 'Account is suspended.'}), 403

    user.last_seen_at = datetime.now(timezone.utc)
    db.session.commit()
    login_user(user, remember=data.get('remember', False))

    return jsonify({
        'message': 'Logged in successfully',
        'user': user.get_public_profile()
    }), 200


@auth_bp.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/api/auth/me', methods=['GET'])
@login_required
def api_me():
    return jsonify({
        'user': current_user.get_public_profile(),
        'email': current_user.email,
        'is_admin': current_user.is_admin
    }), 200
