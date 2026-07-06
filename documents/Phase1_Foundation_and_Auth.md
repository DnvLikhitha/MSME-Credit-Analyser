# Phase 1 — Foundation & Authentication

**Status:** ✅ Complete | **Commit:** `Phase 1 — Foundation Setup`
**Branch:** `main` | **Tests:** 13/13 passing

---

## Overview

Phase 1 establishes the entire backend foundation of the MSME Credit Intelligence Agent. It sets up the project structure, database schema, JWT-based user authentication, file upload pipeline, and the infrastructure needed to run the project locally and deploy it later. No AI or scoring logic is included yet — this phase is purely about creating a rock-solid base that every future phase builds on.

---

## What Was Built

### 1. Project Structure

```
msme/
├── backend/                  # FastAPI application
│   ├── config.py             # Centralized settings (reads from .env)
│   ├── database.py           # SQLAlchemy engine + session factory
│   ├── main.py               # App entry point, lifespan manager
│   ├── models/               # SQLAlchemy ORM table definitions
│   │   ├── user.py
│   │   ├── document.py
│   │   ├── extracted_metrics.py
│   │   ├── risk_score.py
│   │   ├── loan_recommendation.py
│   │   └── report.py
│   ├── schemas/              # Pydantic request/response schemas
│   │   ├── user.py
│   │   └── document.py
│   ├── routers/              # API route handlers
│   │   ├── auth.py
│   │   └── upload.py
│   ├── utils/
│   │   └── security.py       # Password hashing + JWT token logic
│   └── tests/
│       ├── conftest.py       # Test DB setup (SQLite in-memory)
│       ├── test_auth.py      # Auth endpoint tests
│       └── test_upload.py    # Upload endpoint tests
├── infra/
│   ├── migrations/
│   │   └── 001_initial_schema.sql   # Full Postgres schema
│   └── apply_migration.py           # Script to apply SQL to DB
├── docker-compose.yml        # Local RabbitMQ + Postgres containers
├── .env                      # Local environment variables (git-ignored)
├── .env.example              # Blueprint for new developers
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Pytest + tooling config
└── README.md
```

---

### 2. Database Schema (`001_initial_schema.sql`)

Six tables were created in Postgres to support the full document-to-recommendation pipeline:

| Table | Purpose |
|---|---|
| `users` | Stores registered users (email, hashed password, name) |
| `documents` | Tracks every uploaded financial document + processing status |
| `extracted_metrics` | Stores 17 financial metrics extracted by Gemini AI |
| `risk_scores` | Stores the credit risk score and band (LOW/MEDIUM/HIGH) |
| `loan_recommendations` | Stores ranked government loan scheme recommendations |
| `reports` | Tracks generated PDF credit reports |

#### Document Status Pipeline
Every document flows through a lifecycle tracked in the `status` column:
```
PENDING → EXTRACTING → SCORING → RECOMMENDING → REPORTING → COMPLETE
                                                              ↑
                                                            FAILED (at any stage)
```

#### Key Design Decisions
- **UUID primary keys** everywhere — safe for distributed systems, no sequential ID leaks.
- **`content_hash` (SHA-256)** on documents — prevents duplicate uploads of the same file.
- **`ON DELETE CASCADE`** foreign keys — deleting a user removes all their data cleanly.
- **`updated_at` auto-trigger** — a PL/pgSQL trigger automatically updates the timestamp on any row change.

---

### 3. Configuration (`backend/config.py`)

All environment variables are loaded through a single Pydantic `Settings` class. This means:
- No hardcoded secrets anywhere in code.
- One place to add new config variables.
- Automatic type validation (e.g. PORT must be an int).

Key settings loaded from `.env`:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | Signs JWT tokens |
| `GOOGLE_API_KEY` | Gemini API access |
| `RABBITMQ_URL` | Message queue connection |
| `UPLOAD_DIR` | Where uploaded files are stored locally |

---

### 4. Authentication System (`backend/routers/auth.py`)

The auth system uses **JWT (JSON Web Token) Bearer tokens** — the industry standard for stateless API authentication.

#### How it works:

**Registration** (`POST /auth/register`):
1. User sends `{ email, password, full_name }`.
2. Password is validated (min 8 chars, at least one number).
3. Password is hashed using `bcrypt` (via `passlib`) — the plain text is never stored.
4. User row is created in the `users` table.
5. An access token is returned immediately.

**Login** (`POST /auth/login`):
1. User sends `username` (email) + `password` via form data (OAuth2 standard).
2. User is looked up in DB. If not found → 401.
3. Submitted password is verified against the stored `bcrypt` hash.
4. A JWT is generated containing `{ sub: email, exp: expiry_timestamp }`.
5. Token is returned. Valid for `ACCESS_TOKEN_EXPIRE_MINUTES` (default: 1440 = 24 hours).

**Protected routes** (`GET /auth/me`):
1. Client sends `Authorization: Bearer <token>` header.
2. FastAPI's `OAuth2PasswordBearer` dependency extracts the token.
3. `get_current_user()` decodes and validates the JWT.
4. User is fetched from DB and returned.

#### Security Details
- **bcrypt** hashing with automatic salt — industry standard, resistant to rainbow tables.
- **HS256** JWT signing — uses the `SECRET_KEY` env variable.
- **FastAPI dependency injection** — `get_current_user` is a reusable dependency that any future route can use to require authentication in one line.

---

### 5. File Upload (`backend/routers/upload.py`)

**Endpoint:** `POST /documents/upload`
**Auth:** Required (Bearer token)

#### What happens on upload:
1. File is validated — only PDF, JPEG, PNG allowed (checked by MIME type).
2. File size is checked (max 10MB by default).
3. A **SHA-256 hash** of the file content is computed.
4. The hash is checked against existing documents for that user — **duplicate files are rejected** with a `409 Conflict` response.
5. A UUID filename is generated and the file is saved to `UPLOAD_DIR`.
6. A `Document` row is created in the DB with `status = PENDING`.
7. A message `{ document_id }` is published to the RabbitMQ queue for async processing.
8. The API responds immediately with `201 Created` — the client doesn't wait for extraction.

---

### 6. Infrastructure (`docker-compose.yml`)

For local development, two services run in Docker:

| Service | Port | Purpose |
|---|---|---|
| **RabbitMQ** | 5672 (AMQP), 15672 (Web UI) | Message queue for async document processing |
| **Postgres** | 5433 | Local database (mirrors production schema) |

> **Note:** We use port `5433` for Postgres locally to avoid conflicts with any native Postgres installation on Windows.

---

### 7. Testing (`backend/tests/`)

13 automated tests cover all critical paths:

| Test | What it checks |
|---|---|
| `test_root` | `GET /` returns 200 |
| `test_health` | `GET /health` returns DB status |
| `test_register_success` | Valid registration creates a user |
| `test_register_weak_password` | Short passwords are rejected |
| `test_register_invalid_email` | Malformed emails are rejected |
| `test_login_invalid_credentials` | Wrong password returns 401 |
| `test_login_success_and_me` | Login returns token; `/me` returns user profile |
| `test_me_without_token` | Protected route without token returns 401 |
| `test_upload_pdf` | Upload succeeds with a valid PDF + token |
| `test_list_documents` | Uploaded documents are retrievable |

Tests use an **SQLite in-memory database** (via `conftest.py`) — no Docker or external services needed to run them.

**Run tests:**
```powershell
.venv\Scripts\python -m pytest backend/tests/ -v
```

---

## How to Run Phase 1

### Prerequisites
- Python 3.11+ with venv activated
- Docker Desktop running

### Steps

```powershell
# 1. Start infrastructure
docker-compose up -d

# 2. Apply database schema
.venv\Scripts\python infra\apply_migration.py

# 3. Start API server
.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000
```

Open **http://127.0.0.1:8000/docs** to explore the API.

---

## Key Libraries Used

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | 0.111 | Web framework |
| `uvicorn` | 0.30 | ASGI server |
| `sqlalchemy` | 2.0 | ORM + DB connection |
| `psycopg2-binary` | 2.9 | Postgres driver |
| `pydantic` | 2.7 | Data validation + settings |
| `python-jose` | 3.3 | JWT encoding/decoding |
| `passlib[bcrypt]` | 1.7 | Password hashing |
| `python-multipart` | 0.0.9 | File upload parsing |
| `python-dotenv` | 1.0 | `.env` file loading |
| `pytest` | 8.2 | Testing framework |
| `httpx` | 0.27 | Async HTTP client for tests |

---

## API Endpoints (Phase 1)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | No | Root — returns app name + version |
| `GET` | `/health` | No | Health check — DB connectivity |
| `POST` | `/auth/register` | No | Register a new user |
| `POST` | `/auth/login` | No | Login, returns JWT token |
| `GET` | `/auth/me` | Yes | Get current user profile |
| `POST` | `/documents/upload` | Yes | Upload a financial document |
| `GET` | `/documents/` | Yes | List all documents for current user |
