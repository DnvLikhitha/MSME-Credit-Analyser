# MSME Credit Intelligence Agent

An AI-powered platform that ingests financial documents (GST returns, bank statements, ITRs) from MSMEs and produces an explainable creditworthiness assessment, risk score, and loan scheme recommendation.

---

## Architecture

```
Frontend (Next.js) ──▶ FastAPI (API Gateway)
                              │
                        RabbitMQ Queue
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
     Extraction Worker  Risk Scoring    Recommendation
     (OCR + Gemini)     Service         Service (RAG)
              │               │               │
         Postgres          Redis           ChromaDB
              │
         Report Worker ──▶ PDF ──▶ Storage
```

---

## Tech Stack

| Layer | Technology | Cost |
|-------|-----------|------|
| API | FastAPI (Python) | Free |
| Database | Supabase Postgres | Free tier |
| Queue | RabbitMQ (Docker) / CloudAMQP | Free tier |
| Cache | Redis (Docker) / Upstash | Free tier |
| Vector DB | ChromaDB (self-hosted) | Free |
| LLM | Gemini Flash | Free tier |
| Frontend | Next.js + Tailwind | Free |
| Deploy | GCP Cloud Run | Free tier |
| CI/CD | GitHub Actions | Free tier |

---

## Project Structure

```
msme/
├── .env.example          # Blueprint — copy to .env
├── .gitignore
├── requirements.txt      # All backend dependencies
├── pyproject.toml        # Pytest config
├── README.md
│
├── backend/
│   ├── main.py           # FastAPI app entry point
│   ├── config.py         # Settings (pydantic-settings)
│   ├── database.py       # SQLAlchemy engine + session
│   ├── models/           # ORM models
│   ├── schemas/          # Pydantic request/response schemas
│   ├── routers/          # API route handlers
│   ├── services/         # Business logic (Phase 2+)
│   ├── workers/          # Async job consumers (Phase 2+)
│   └── tests/            # pytest tests
│
├── frontend/             # Next.js dashboard (Phase 5)
├── infra/                # Docker Compose + GCP configs (Phase 6+)
└── docs/
    └── schemes/          # Loan scheme docs for RAG (Phase 4)
```

---

## Setup

### Prerequisites
- Python 3.11+
- Git

### 1. Clone & Activate venv

```bash
git clone <your-repo-url>
cd msme
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
copy .env.example .env     # Windows
# cp .env.example .env     # macOS/Linux
```

Edit `.env` and fill in:
- `DATABASE_URL` — your Supabase connection string (Transaction pooler, port 6543)
- `SECRET_KEY` — generate with `python -c "import secrets; print(secrets.token_hex(32))"`
- `GOOGLE_API_KEY` — from [Google AI Studio](https://aistudio.google.com/app/apikey)

### 4. Run the API

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health**: http://localhost:8000/health

### 5. Run Tests

```bash
pytest
```

---

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Complete | Scaffold + Upload API + Auth |
| 2 | 🔜 Next | RabbitMQ + Extraction Worker (OCR + Gemini) |
| 3 | 🔜 | Risk Scoring Engine |
| 4 | 🔜 | RAG Loan Recommendation (ChromaDB) |
| 5 | 🔜 | WebSocket + PDF Report + Next.js Dashboard |
| 6 | 🔜 | Docker Compose + Redis caching |
| 7 | 🔜 | CI/CD + GCP Cloud Run deploy |
| 8 | 🔜 | Prometheus + Grafana observability |

---

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register new user |
| POST | `/auth/login` | Login, returns JWT token |
| GET | `/auth/me` | Get current user profile |

### Documents
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/documents/upload` | Upload PDF/image document |
| GET | `/documents/` | List user's documents |
| GET | `/documents/{id}` | Get document status |
| DELETE | `/documents/{id}` | Delete document |

---

## Environment Variables Reference

See [`.env.example`](.env.example) for the full list with descriptions.

---

## Contributing

Each phase is a separate commit. Branch naming: `phase/<n>-description`.
