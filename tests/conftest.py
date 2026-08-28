import os
import shutil
import pytest
from app import create_app
from app.extensions import db, storage_service
from app.storage import LocalStorageService
from app.models.user import User
from app.dating.services import seed_interests
from app.public_chat.routes import seed_public_rooms


@pytest.fixture(scope='session')
def app():
    os.environ['FLASK_ENV'] = 'testing'
    app = create_app('testing')
    
    test_storage_dir = app.config['STORAGE_DIR']
    os.makedirs(test_storage_dir, exist_ok=True)
    storage_service.init_app(app)

    with app.app_context():
        db.create_all()
        seed_interests()
        seed_public_rooms()
        yield app
        db.session.remove()
        db.drop_all()

    # Clean up test storage directory
    if os.path.exists(test_storage_dir):
        shutil.rmtree(test_storage_dir, ignore_errors=True)


@pytest.fixture(scope='function')
def db_session(app):
    with app.app_context():
        # Clear tables before each test
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        seed_interests()
        seed_public_rooms()
        yield db.session
        db.session.rollback()


@pytest.fixture
def client(app, db_session):
    return app.test_client()


@pytest.fixture
def create_test_user(app, db_session):
    def _create_user(username="testuser", email="test@example.com", password="Password123!", is_admin=False):
        user = User(
            username=username,
            username_lower=username.lower(),
            email=email.lower(),
            display_name=username,
            is_admin=is_admin,
            email_verified=True
        )
        user.set_password(password)
        from app.models.dating import DatingProfile
        dating_profile = DatingProfile(user=user, enabled=False, min_age_pref=18, max_age_pref=99)
        db.session.add(user)
        db.session.add(dating_profile)
        db.session.commit()
        return user
    return _create_user
