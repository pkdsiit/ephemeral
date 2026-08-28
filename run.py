import os
from app import create_app
from app.extensions import socketio, db

app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    with app.app_context():
        # Ensure database tables exist
        db.create_all()
        
        # Auto seed default interests and public rooms in dev mode
        from app.dating.services import seed_interests
        from app.public_chat.routes import seed_public_rooms
        seed_interests()
        seed_public_rooms()

    port = int(os.environ.get('PORT', 5001))
    print(f"Starting Ephemeral Chat server on port {port}...")
    socketio.run(app, host='0.0.0.0', port=port, debug=app.config.get('DEBUG', False), allow_unsafe_werkzeug=True)
