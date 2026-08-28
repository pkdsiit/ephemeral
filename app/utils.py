from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return current naive UTC datetime for consistent SQLAlchemy storage and comparison."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
