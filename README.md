# Ephemeral Chat & Ephemeral Dating 🚀

A production-ready, privacy-first, responsive web application engineered with **Python**, **Flask**, **PostgreSQL**, **SQLAlchemy**, and **Flask-SocketIO**. Designed for temporary, self-destructing text and media communication alongside an adult-only (18+) mutual compatibility dating ecosystem.

---

## 🌟 Core Architecture & Ephemeral Guarantee

1. **Strict Ephemeral Media Deletion Lifecycle**:
   - Ephemeral images are single-view / one-time accessible.
   - When a recipient views an ephemeral image and subsequently replies with a new message in that conversation, the server physically deletes the image file from disk storage and sets its database state to `DELETED`.
   - All private and public messages strictly expire after **7 days**.
2. **PostgreSQL Everywhere**:
   - Zero SQLite dependencies. PostgreSQL is used across development, testing, and production.
   - Relational integrity with Foreign Key constraints, UUID primary keys, and cascade rules.
3. **Privacy & Security First**:
   - All uploaded images have **EXIF and metadata stripped** before saving.
   - User usernames are uniquely normalized (`@username` case-insensitive).
   - Strict access controls on media endpoints: unauthorized users cannot access images even if they guess an ID.
   - Passwords hashed with modern PBKDF2/Scrypt algorithms.
   - Rate limiting on authentication and messaging endpoints (`Flask-Limiter`).
   - CSRF protection enabled on web forms (`Flask-WTF`).
4. **Real-time Synchronization**:
   - Real-time bidirectional WebSockets powered by `Flask-SocketIO` with HTTP long-polling fallback.

---

## 📁 Repository Structure

```
chatapp/
├── app/
│   ├── __init__.py            # Application factory with extensions & blueprints
│   ├── extensions.py        # SQLAlchemy, Migrate, Login, Limiter, SocketIO, Storage Proxy
│   ├── storage.py           # LocalStorageService & image sanitizer (EXIF stripping)
│   ├── utils.py             # UTC datetime helpers
│   ├── models/              # Relational schema
│   │   ├── user.py          # User accounts, auth, relationships
│   │   ├── conversation.py  # 1-to-1 Conversations & participants
│   │   ├── message.py       # Ephemeral Messages & MessageImage models
│   │   ├── friendship.py    # Friendships & Blocking
│   │   ├── dating.py        # DatingProfile, Interests, and association tables
│   │   ├── public_room.py   # Public chat rooms & messages
│   │   ├── report.py        # Abuse & harassment reports
│   │   └── token.py         # Password reset & verification tokens
│   ├── auth/                # Auth blueprint (Register, Login, Password Reset)
│   ├── users/               # Users blueprint (Profile, Search, Friends, Block)
│   ├── chat/                # 1-to-1 Chat blueprint & WebSockets
│   ├── dating/              # Opt-in adult dating (18+) & matching engine
│   ├── public_chat/         # Public rooms blueprint & WebSockets
│   ├── media/               # Protected ephemeral & avatar image delivery
│   ├── admin/               # Admin dashboard & moderation triage
│   ├── main/                # Landing page, dashboard, /healthz, /api/cleanup
│   ├── tasks/               # Background cleanup scheduler (APScheduler)
│   ├── static/              # CSS styling & Vanilla JavaScript frontends
│   │   ├── css/style.css    # Cyber-dark responsive design
│   │   └── js/              # app.js, chat.js, webcam.js, dating.js, public_chat.js
│   └── templates/           # Jinja2 responsive templates (Mobile & Desktop)
├── migrations/              # Alembic database migration scripts
├── tests/                   # Pytest test suite (22 tests, 100% passing)
├── config.py                # Environment configurations (Dev, Test, Prod)
├── run.py                   # Development entrypoint
├── wsgi.py                  # Production WSGI entrypoint
├── gunicorn_config.py       # Production Gunicorn worker configuration
├── Procfile                 # Process file for cloud deployment
├── render.yaml              # Render Cloud infrastructure blueprint
├── requirements.txt         # Pinned Python dependencies
└── README.md                # Documentation
```

---

## 🛠️ Local Development Setup

### 1. Prerequisites
- **Python 3.11+**
- **PostgreSQL 14+** running locally

### 2. Clone & Virtual Environment Setup
```bash
cd /Users/pk/Desktop/chatapp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Create PostgreSQL Databases
```bash
# Connect to PostgreSQL and create application & test databases
psql postgres -c "CREATE DATABASE ephemeral_chat_db;"
psql postgres -c "CREATE DATABASE ephemeral_chat_test_db;"
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and verify database credentials:
```bash
cp .env.example .env
```

Example `.env`:
```env
FLASK_APP=wsgi.py
FLASK_ENV=development
SECRET_KEY=your-super-secret-key-change-this-in-production
DATABASE_URL=postgresql://localhost:5432/ephemeral_chat_db
TEST_DATABASE_URL=postgresql://localhost:5432/ephemeral_chat_test_db
STORAGE_DIR=storage
RATELIMIT_STORAGE_URI=memory://
```

### 5. Run Database Migrations & Seed Initial Data
```bash
flask db upgrade
flask seed-interests
flask seed-rooms
```

*(Optional: Create an admin user)*
```bash
flask create-admin
```

### 6. Start Development Server
```bash
python run.py
```
Open your browser at **`http://127.0.0.1:5000`**.

---

## 🧪 Automated Testing

The project includes an extensive test suite verifying:
- Authentication, registration, and password recovery
- Case-insensitive unique username normalization
- 1-to-1 Messaging and authorization isolation
- Ephemeral image consumption and physical disk deletion on recipient's next reply
- Opt-in adult (18+) Dating verification and mutual compatibility scoring
- Abuse reporting, blocking, and admin moderation
- Background idempotent cleanup tasks

Run tests with `pytest`:
```bash
./venv/bin/pytest -v
```

---

## 🚀 Production Deployment (Render)

This application is fully optimized for one-click deployment on **Render** using the included `render.yaml`.

### Render Components
1. **Web Service (`ephemeral-chat-web`)**:
   - Python environment running `gunicorn --config gunicorn_config.py wsgi:app`
   - Real-time WebSockets with eventlet/simple-websocket worker compatibility
   - Persistent Disk mounted at `/var/data/ephemeral_storage`
2. **PostgreSQL Database (`ephemeral-chat-postgres`)**:
   - Managed PostgreSQL database instance
3. **Cron Job (`ephemeral-chat-cleanup-cron`)**:
   - Runs every 15 minutes (`*/15 * * * *`) executing `flask run-cleanup` to purge expired content

### Manual Render Setup Steps
1. Push this repository to GitHub / GitLab.
2. Log in to [Render Dashboard](https://dashboard.render.com).
3. Click **New +** -> **Blueprint** and connect your repository.
4. Render will automatically detect `render.yaml` and provision the web service, database, and scheduled cleanup job.

---

## 🔒 Security Best Practices Implemented

- **No Indexing on Dating Profiles**: Header `X-Robots-Tag: noindex, nofollow` prevents search engines from indexing private profiles.
- **Image Metadata Scrubbing**: All images uploaded via gallery or live camera/webcam are re-encoded through Pillow, stripping EXIF, GPS location, and camera hardware tags.
- **Direct Image Deletion**: Image files are physically unlinked from storage once consumed and replied to.
- **Secure Sessions**: HTTP-Only, SameSite cookies with CSRF validation across all state-mutating requests.
- **Rate Limiting**: Defends against brute-force password guessing and spam messaging.
