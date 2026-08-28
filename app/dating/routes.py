from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.dating import DatingProfile, Interest
from app.dating.forms import DatingPreferencesForm
from app.dating.services import get_dating_matches, seed_interests
from app.utils import utcnow

dating_bp = Blueprint('dating', __name__)


@dating_bp.route('/dating', methods=['GET'])
@login_required
def index():
    profile = current_user.dating_profile
    if not profile or not profile.enabled:
        return render_template('dating/opt_in.html', profile=profile)

    matches = get_dating_matches(current_user.id)
    return render_template('dating/index.html', profile=profile, matches=matches)


@dating_bp.route('/dating/preferences', methods=['GET', 'POST'])
@login_required
def preferences():
    seed_interests()
    all_interests = Interest.query.order_by(Interest.category, Interest.name).all()

    profile = current_user.dating_profile
    if not profile:
        profile = DatingProfile(user=current_user)
        db.session.add(profile)
        db.session.commit()

    form = DatingPreferencesForm()
    form.interests.choices = [(i.id, i.name) for i in all_interests]

    if form.validate_on_submit():
        profile.enabled = form.enabled.data
        profile.age = form.age.data
        profile.gender = form.gender.data
        profile.interested_in = form.interested_in.data
        profile.min_age_pref = form.min_age_pref.data or 18
        profile.max_age_pref = form.max_age_pref.data or 99
        profile.show_gender = form.show_gender.data
        profile.bio = form.bio.data.strip() if form.bio.data else None
        profile.updated_at = utcnow()

        # Update selected interests
        selected_ids = form.interests.data or []
        profile.interests = Interest.query.filter(Interest.id.in_(selected_ids)).all()

        db.session.commit()
        flash("Dating preferences saved successfully!", "success")
        return redirect(url_for('dating.index'))

    elif request.method == 'GET':
        form.enabled.data = profile.enabled
        form.age.data = profile.age
        form.gender.data = profile.gender
        form.interested_in.data = profile.interested_in or 'everyone'
        form.min_age_pref.data = profile.min_age_pref
        form.max_age_pref.data = profile.max_age_pref
        form.show_gender.data = profile.show_gender
        form.bio.data = profile.bio
        form.interests.data = [i.id for i in profile.interests]

    return render_template('dating/preferences.html', form=form, all_interests=all_interests, profile=profile)


@dating_bp.route('/dating/matches', methods=['GET'])
@login_required
def matches():
    profile = current_user.dating_profile
    if not profile or not profile.enabled:
        return redirect(url_for('dating.index'))

    match_list = get_dating_matches(current_user.id)
    return render_template('dating/matches.html', matches=match_list, profile=profile)


# ---------------- API Endpoints ----------------

@dating_bp.route('/api/dating/profile', methods=['GET'])
@login_required
def api_get_profile():
    profile = current_user.dating_profile
    if not profile:
        return jsonify({'profile': None}), 200
    return jsonify({'profile': profile.to_dict()}), 200


@dating_bp.route('/api/dating/profile', methods=['PATCH'])
@login_required
def api_update_profile():
    profile = current_user.dating_profile
    if not profile:
        profile = DatingProfile(user=current_user)
        db.session.add(profile)

    data = request.get_json() or {}
    
    if 'enabled' in data:
        profile.enabled = bool(data['enabled'])
    
    if 'age' in data:
        age_val = data['age']
        if age_val is not None and int(age_val) < 18:
            return jsonify({'error': 'You must be at least 18 years old to use dating.'}), 400
        profile.age = int(age_val) if age_val is not None else None

    if 'gender' in data:
        profile.gender = data['gender']
    if 'interested_in' in data:
        profile.interested_in = data['interested_in']
    if 'min_age_pref' in data:
        profile.min_age_pref = max(18, int(data['min_age_pref']))
    if 'max_age_pref' in data:
        profile.max_age_pref = max(profile.min_age_pref, int(data['max_age_pref']))
    if 'bio' in data:
        profile.bio = data['bio']
    if 'show_gender' in data:
        profile.show_gender = bool(data['show_gender'])

    if 'interest_ids' in data:
        ids = data['interest_ids']
        profile.interests = Interest.query.filter(Interest.id.in_(ids)).all()
    elif 'interests' in data:
        names = data['interests']
        profile.interests = Interest.query.filter(Interest.name.in_(names)).all()

    profile.updated_at = utcnow()
    db.session.commit()

    return jsonify({
        'message': 'Dating profile updated',
        'profile': profile.to_dict()
    }), 200


@dating_bp.route('/api/dating/matches', methods=['GET'])
@login_required
def api_get_matches():
    matches_data = get_dating_matches(current_user.id)
    return jsonify({'matches': matches_data}), 200


@dating_bp.route('/api/dating/interests', methods=['GET'])
@login_required
def api_get_interests():
    seed_interests()
    interests = Interest.query.order_by(Interest.category, Interest.name).all()
    return jsonify({'interests': [i.to_dict() for i in interests]}), 200
