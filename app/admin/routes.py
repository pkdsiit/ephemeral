from functools import wraps
from datetime import datetime, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user import User
from app.models.conversation import Conversation
from app.models.public_room import PublicRoom, PublicMessage
from app.models.report import Report
from app.models.message import Message

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash("Administrator privileges required.", "danger")
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/', methods=['GET'])
@admin_required
def dashboard():
    total_users = User.query.count()
    active_users = User.query.filter_by(is_suspended=False).count()
    suspended_users = User.query.filter_by(is_suspended=True).count()
    total_conversations = Conversation.query.count()
    total_reports = Report.query.count()
    pending_reports = Report.query.filter_by(status='PENDING').count()
    rooms = PublicRoom.query.all()

    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_reports = Report.query.order_by(Report.created_at.desc()).limit(10).all()

    stats = {
        'total_users': total_users,
        'active_users': active_users,
        'suspended_users': suspended_users,
        'total_conversations': total_conversations,
        'total_reports': total_reports,
        'pending_reports': pending_reports,
        'public_rooms_count': len(rooms)
    }

    return render_template(
        'admin/dashboard.html',
        stats=stats,
        recent_users=recent_users,
        recent_reports=recent_reports,
        rooms=rooms
    )


@admin_bp.route('/users', methods=['GET'])
@admin_required
def users_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('q', '').strip()
    
    query = User.query
    if search:
        clean_q = search.lstrip('@').lower()
        query = query.filter((User.username_lower.ilike(f"%{clean_q}%")) | (User.email.ilike(f"%{clean_q}%")))
    
    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return render_template('admin/users.html', pagination=pagination, search=search)


@admin_bp.route('/users/<user_id>/toggle-suspend', methods=['POST'])
@admin_required
def toggle_suspend(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("You cannot suspend your own account.", "warning")
        return redirect(url_for('admin.users_list'))

    user.is_suspended = not user.is_suspended
    db.session.commit()
    
    status = "suspended" if user.is_suspended else "reinstated"
    flash(f"User @{user.username} has been {status}.", "success")
    return redirect(request.referrer or url_for('admin.users_list'))


@admin_bp.route('/reports', methods=['GET'])
@admin_required
def reports_list():
    status_filter = request.args.get('status', 'PENDING')
    query = Report.query
    if status_filter != 'ALL':
        query = query.filter_by(status=status_filter)

    reports = query.order_by(Report.created_at.desc()).all()
    return render_template('admin/reports.html', reports=reports, status_filter=status_filter)


@admin_bp.route('/reports/<report_id>/update', methods=['POST'])
@admin_required
def update_report(report_id):
    report = Report.query.get_or_404(report_id)
    new_status = request.form.get('status', 'RESOLVED')
    admin_notes = request.form.get('admin_notes', '')

    report.status = new_status
    report.admin_notes = admin_notes
    report.resolved_at = datetime.now(timezone.utc)
    db.session.commit()

    flash("Report updated.", "success")
    return redirect(url_for('admin.reports_list'))


@admin_bp.route('/rooms', methods=['GET', 'POST'])
@admin_required
def rooms_management():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().lower().replace(' ', '-')
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if code and name:
            existing = PublicRoom.query.filter_by(code=code).first()
            if not existing:
                room = PublicRoom(code=code, name=name, description=description, is_active=True)
                db.session.add(room)
                db.session.commit()
                flash(f"Public room '{name}' created.", "success")
            else:
                flash("A room with that code already exists.", "danger")
        return redirect(url_for('admin.rooms_management'))

    rooms = PublicRoom.query.order_by(PublicRoom.created_at.asc()).all()
    return render_template('admin/rooms.html', rooms=rooms)


@admin_bp.route('/rooms/<room_id>/toggle', methods=['POST'])
@admin_required
def toggle_room(room_id):
    room = PublicRoom.query.get_or_404(room_id)
    room.is_active = not room.is_active
    db.session.commit()
    flash(f"Room status updated.", "success")
    return redirect(url_for('admin.rooms_management'))
