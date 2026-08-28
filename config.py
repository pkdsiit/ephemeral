import os
from datetime import timedelta
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


def normalize_db_url(url: str | None) -> str:
    """Normalize database URL for SQLAlchemy compatibility (e.g., postgres:// -> postgresql://)."""
    default_url = "postgresql://localhost/ephemeral_chat_db"
    if not url:
        return default_url
    
    url = str(url).strip()
    # Strip surrounding single or double quotes if copied with quotes
    if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
        url = url[1:-1].strip()

    if not url:
        return default_url

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if "sqlite" in url.lower():
        raise ValueError("SQLite is strictly prohibited. Use PostgreSQL exclusively.")

    # Validate that SQLAlchemy make_url can parse it; if not, return safe fallback
    try:
        import sqlalchemy.engine.url as sa_url
        sa_url.make_url(url)
        return url
    except Exception as e:
        print(f"[Config Notice] Invalid DATABASE_URL format: '{url}'. Falling back to default URL. ({e})")
        return default_url


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ephemeral-insecure-dev-key-must-change'
    
    # Database
    SQLALCHEMY_DATABASE_URI = normalize_db_url(os.environ.get('DATABASE_URL'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # Session & Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 't')
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # File Storage
    STORAGE_DIR = os.environ.get('STORAGE_DIR') or os.path.join(basedir, 'storage')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB maximum upload
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
    ALLOWED_IMAGE_MIMETYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}

    # Ephemeral Retention
    MESSAGE_RETENTION_DAYS = int(os.environ.get('MESSAGE_RETENTION_DAYS', 7))
    EPHEMERAL_IMAGE_VIEW_TIMEOUT_SECONDS = int(os.environ.get('EPHEMERAL_IMAGE_VIEW_TIMEOUT_SECONDS', 60))

    # Rate Limiting
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '300 per day;60 per hour')
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

    # Admin seed
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@ephemeral.local')
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'AdminSecurePassword123!')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = False
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = normalize_db_url(
        os.environ.get('TEST_DATABASE_URL') or 'postgresql://pk@localhost:5432/ephemeral_chat_test_db'
    )
    RATELIMIT_ENABLED = False
    STORAGE_DIR = os.path.join(basedir, 'storage_test')


class ProductionConfig(Config):
    """Production configuration for Render and cloud hosts."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    RATELIMIT_STORAGE_URI = os.environ.get('REDIS_URL', 'memory://')


config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
