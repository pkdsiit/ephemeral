import os
import logging
from flask import Flask, render_template, request, jsonify
from config import config_by_name, Config
import app.extensions as ext
from app.storage import LocalStorageService
from app.models.user import User


def create_app(config_name: str = None) -> Flask:
    """Application factory for Ephemeral Chat."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name['default']))

    # Configure logging
    logging.basicConfig(
        level=logging.INFO if not app.config.get('DEBUG') else logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    # Initialize extensions
    ext.db.init_app(app)
    ext.migrate.init_app(app, ext.db)
    ext.login_manager.init_app(app)
    ext.login_manager.login_view = 'auth.login'
    ext.login_manager.login_message = "Please sign in to access this page."
    ext.login_manager.login_message_category = "info"
    ext.csrf.init_app(app)
    ext.limiter.init_app(app)
    
    # Initialize SocketIO with multithreading support
    ext.socketio.init_app(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        manage_session=False,
        ping_timeout=20,
        ping_interval=25
    )

    # Initialize storage service
    ext.storage_service.init_app(app)

    # User loader for Flask-Login
    @ext.login_manager.user_loader
    def load_user(user_id):
        return ext.db.session.get(User, user_id)

    # Context processors
    @app.context_processor
    def inject_global_vars():
        return {
            'app_name': 'Ephemeral',
            'app_tagline': "Messages that don't have to stay forever.",
        }

    # Security Headers Middleware
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        if not app.config.get('DEBUG'):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # Register blueprints
    from app.auth.routes import auth_bp
    from app.users.routes import users_bp
    from app.chat.routes import chat_bp
    from app.dating.routes import dating_bp
    from app.public_chat.routes import public_chat_bp
    from app.media.routes import media_bp
    from app.admin.routes import admin_bp
    from app.main.routes import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(dating_bp)
    app.register_blueprint(public_chat_bp)
    app.register_blueprint(media_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)

    # Register error handlers
    register_error_handlers(app)

    # Exempt API JSON endpoints from CSRF (protected by session auth, login_required & rate limiter)
    for endpoint, view in list(app.view_functions.items()):
        if 'api' in endpoint:
            ext.csrf.exempt(view)

    # Register CLI commands
    register_cli_commands(app)

    return app


def register_error_handlers(app: Flask):
    def handle_error(status_code, message):
        is_api = request.path.startswith('/api/') or request.is_json or (
            request.accept_mimetypes.best == 'application/json' and request.accept_mimetypes['text/html'] < request.accept_mimetypes['application/json']
        )
        if is_api:
            return jsonify({'error': message, 'status_code': status_code}), status_code
        try:
            return render_template(f'errors/{status_code}.html', error_message=message), status_code
        except Exception:
            return render_template('errors/generic.html', status_code=status_code, error_message=message), status_code

    @app.errorhandler(400)
    def bad_request(e):
        return handle_error(400, "Bad Request. The server could not process your submission.")

    @app.errorhandler(401)
    def unauthorized(e):
        return handle_error(401, "Authentication required to access this resource.")

    @app.errorhandler(403)
    def forbidden(e):
        return handle_error(403, "Access forbidden. You are not authorized to view this.")

    @app.errorhandler(404)
    def not_found(e):
        return handle_error(404, "Page or resource not found.")

    @app.errorhandler(409)
    def conflict(e):
        return handle_error(409, "Conflict occurred. The requested resource already exists.")

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return handle_error(413, "Uploaded file is too large. Maximum size is 10MB.")

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return handle_error(429, "Rate limit exceeded. Please slow down your requests.")

    @app.errorhandler(500)
    def internal_server_error(e):
        app.logger.error(f"Internal server error: {e}")
        return handle_error(500, "An internal server error occurred.")


def register_cli_commands(app: Flask):
    @app.cli.command("seed-interests")
    def seed_interests_cmd():
        """Seed default structured interest tags for dating matching."""
        from app.dating.services import seed_interests
        seed_interests()
        print("Default dating interests seeded successfully.")

    @app.cli.command("seed-rooms")
    def seed_rooms_cmd():
        """Seed default public chat rooms."""
        from app.public_chat.routes import seed_public_rooms
        seed_public_rooms()
        print("Default public chat rooms seeded successfully.")

    @app.cli.command("seed-admin")
    @app.cli.command("create-admin")
    def seed_admin():
        """Create or update admin account from environment settings."""
        admin_email = app.config.get('ADMIN_EMAIL', 'admin@ephemeral.local')
        admin_username = app.config.get('ADMIN_USERNAME', 'admin')
        admin_password = app.config.get('ADMIN_PASSWORD', 'AdminSecurePassword123!')

        user = User.query.filter_by(email=admin_email).first()
        if not user:
            user = User(
                email=admin_email,
                username=admin_username,
                username_lower=admin_username.lower(),
                display_name="System Admin",
                is_admin=True,
                email_verified=True
            )
            user.set_password(admin_password)
            ext.db.session.add(user)
            ext.db.session.commit()
            print(f"Admin account @{admin_username} created successfully (Password: {admin_password}).")
        else:
            user.is_admin = True
            ext.db.session.commit()
            print(f"User @{user.username} is confirmed as admin.")

    @app.cli.command("seed-all")
    def seed_all():
        """Seed admin account, interests, and public rooms."""
        from app.dating.services import seed_interests
        from app.public_chat.routes import seed_public_rooms
        seed_interests()
        seed_public_rooms()
        print("Default interests and public chat rooms seeded.")

    @app.cli.command("run-cleanup")
    @app.cli.command("cleanup-expired")
    def cleanup_expired():
        """Run idempotent expired messages and ephemeral images cleanup."""
        from app.tasks.cleanup import cleanup_expired_content
        stats = cleanup_expired_content()
        print(f"Ephemeral cleanup completed: {stats}")
