import os
from app import create_app
from app.extensions import db

app = create_app(os.environ.get('FLASK_ENV', 'production'))

with app.app_context():
    try:
        db.create_all()
        from app.dating.services import seed_interests
        from app.public_chat.routes import seed_public_rooms
        seed_interests()
        seed_public_rooms()
    except Exception as e:
        app.logger.warning(f"Startup DB init check: {e}")

if __name__ == '__main__':
    app.run()
