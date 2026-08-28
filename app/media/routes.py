import io
import os
from flask import Blueprint, Response, abort, send_file, current_app, jsonify
from flask_login import login_required, current_user
from app.extensions import storage_service, db
from app.models.user import User
from app.models.message import MessageImage
from app.chat.services import view_ephemeral_image

media_bp = Blueprint('media', __name__)


@media_bp.route('/media/ephemeral/<image_id>', methods=['GET'])
@login_required
def get_ephemeral_image(image_id):
    """
    Access-controlled ephemeral image retrieval.
    Strict authorization: User must be conversation participant, image must not be expired/deleted.
    When viewed by the recipient, state transitions to CONSUMED.
    """
    try:
        image_bytes, mime_type = view_ephemeral_image(current_user.id, image_id)
        
        response = Response(image_bytes, mimetype=mime_type)
        # Prevent any client or intermediary caching
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
    except PermissionError:
        abort(403)
    except FileNotFoundError:
        abort(404)
    except Exception as e:
        current_app.logger.error(f"Error serving ephemeral image {image_id}: {e}")
        abort(500)


@media_bp.route('/media/avatar/<user_id>', methods=['GET'])
def get_avatar(user_id):
    """Public avatar serving."""
    user = User.query.get_or_404(user_id)
    if user.avatar_path and storage_service:
        avatar_bytes = storage_service.get(user.avatar_path)
        if avatar_bytes:
            # Determine mime from extension
            ext = os.path.splitext(user.avatar_path)[1].lower()
            mime = 'image/png' if ext == '.png' else ('image/webp' if ext == '.webp' else 'image/jpeg')
            resp = Response(avatar_bytes, mimetype=mime)
            resp.headers['Cache-Control'] = 'public, max-age=86400'
            return resp

    # Fallback to default SVG avatar
    default_avatar_path = os.path.join(current_app.root_path, 'static', 'images', 'default-avatar.svg')
    if os.path.isfile(default_avatar_path):
        return send_file(default_avatar_path, mimetype='image/svg+xml')
    
    abort(404)


@media_bp.route('/api/images/<image_id>/view', methods=['POST'])
@login_required
def api_record_image_view(image_id):
    """Explicit endpoint to record view status."""
    try:
        image = MessageImage.query.get_or_404(image_id)
        msg = image.message
        if not msg or not msg.conversation.is_participant(current_user.id):
            return jsonify({'error': 'Unauthorized'}), 403

        # Call service to mark seen
        view_ephemeral_image(current_user.id, image_id)
        return jsonify({'message': 'Image marked as viewed/consumed', 'state': image.state}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400
