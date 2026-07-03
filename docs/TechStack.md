# MSME Credit Intelligence Agent
## Tech Stack & Architecture Document

All choices below are free at portfolio scale (self-hosted via Docker, or
generous free tiers). The only real cost is LLM inference, and free-tier
models (Gemini Flash, Groq) can cover build/test.

---

## 1. High-Level Architecture

```
                        ┌──────────────┐
                        │   Frontend   │  Next.js / React
                        │  (Dashboard) │  WebSocket client
                        └──────┬───────┘
                               │ REST + WS
                        ┌──────▼───────┐
                        │   API Gateway│  FastAPI
                        │   Service    │  (auth, upload, WS server)
                        └──────┬───────┘
                               │ publish job
                        ┌──────▼───────┐
                        │   RabbitMQ   │  job queue
                        └──────┬───────┘
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌────────────────┐ ┌─────────────┐ ┌──────────────────┐
     │ Extraction      │ │ Risk Scoring│ │ Recommendation    │
     │ Worker (OCR+LLM)│ │ Service     │ │ Service (RAG)     │
     └───────┬─────────┘ └──────┬──────┘ └─────────┬─────────┘
             │                  │                   │
             ▼                  ▼                   ▼
        ┌─────────┐       ┌──────────┐       ┌─────────────┐
        │ Postgres│       │  Redis   │       │  Vector DB  │
        │ (state) │       │ (cache)  │       │  (Chroma)   │
        └─────────┘       └──────────┘       └─────────────┘
                               │
                        ┌──────▼───────┐
                        │ Report Worker│ → PDF → Object Storage
                        └──────────────┘

        Observability: Prometheus scrapes all services → Grafana dashboards
```

---

## 2. Service Breakdown

| Service | Responsibility | Why it's separate |
|---|---|---|
| **API Gateway** | Auth, file upload, WebSocket connections, read final results | Needs to stay fast/responsive; must not block on LLM work |
| **Extraction Worker** | OCR + LLM parsing of documents into structured JSON | Slow, LLM-bound, needs independent horizontal scaling |
| **Risk Scoring Service** | Deterministic + LLM-assisted scoring from extracted metrics | Cheap and fast — should not share a scaling profile with extraction |
| **Recommendation Service** | RAG lookup over loan scheme docs, matches applicant profile | Needs vector DB access; logically distinct domain from scoring |
| **Report Worker** | Renders final PDF report | I/O-bound, async, can queue independently |

Phase 1 can run these as modules in a single FastAPI app with a shared queue
consumer. Phase 2 splits them into separate Dockerized services once you can
justify it — don't over-engineer on day one.

---

## 3. Tech Stack

### Backend
- **FastAPI** (Python) — API Gateway + services
- **RabbitMQ** — async job queue between services (Docker: `rabbitmq:3-management`)
- **Redis** — caching extracted metrics, job status, dedupe by content hash (Docker or Upstash free tier)
- **Postgres** — source of truth for users, documents, scores, reports (Docker or Supabase/Neon free tier)
- **Chroma** — vector DB for loan scheme eligibility docs (self-hosted, free, easiest to run locally)
- **Celery or a custom RabbitMQ consumer** — worker orchestration

### AI / LLM
- **Gemini Flash (free tier) or Groq (free tier, fast Llama models)** for development
- **Claude/OpenAI API** optional for final polished demo runs (small cost)
- **Tesseract or a hosted OCR free tier** for scanned document text extraction
- **RAG pipeline**: LangChain or a hand-rolled retriever (hand-rolled is more impressive to show you understand it)

### Frontend
- **Next.js / React**
- **Tailwind CSS**
- **WebSocket client** for live processing status
- **Recharts** or similar for dashboard visualizations

### Infra / DevOps
- **Docker + docker-compose** — local multi-service dev environment
- **GitHub Actions** — CI (lint, test, build images) / CD (push to registry, deploy)
- **GCP Cloud Run** — deploy each service as a container (free tier covers low-traffic demo)
- **GCS (Cloud Storage)** — object storage for uploaded documents and generated PDFs (free tier)

### Observability
- **Prometheus** — scrape metrics (queue depth, job latency, error rate) from each service
- **Grafana** — dashboards (self-hosted via Docker, or Grafana Cloud free tier)
- **structlog / Python logging** — structured JSON logs per service

---

## 4. Data Flow for a Single Document

1. User uploads PDF → API Gateway streams it to GCS, writes a `documents` row in Postgres (`status: pending`)
2. API Gateway computes a content hash, checks Redis for a duplicate — if found, short-circuits to cached result
3. API Gateway publishes a job to RabbitMQ (`extraction_queue`) with the document reference
4. Extraction Worker consumes job, runs OCR if needed, calls LLM with a structured-output prompt, writes extracted metrics to Postgres, updates Redis job status, publishes to WebSocket topic
5. Once extraction completes, a scoring job is enqueued automatically
6. Risk Scoring Service computes score + factor breakdown, persists to Postgres
7. Recommendation Service runs RAG against the vector DB of scheme documents, persists top matches
8. Report Worker is enqueued, renders PDF, uploads to GCS, updates `documents.status = complete`
9. Frontend, subscribed via WebSocket, updates live; final dashboard reads from Postgres

---

## 5. Free-Tier / Self-Hosted Cost Map

| Component | Free path |
|---|---|
| RabbitMQ | Docker locally / CloudAMQP free tier for hosted demo |
| Redis | Docker locally / Upstash free tier |
| Postgres | Docker locally / Supabase or Neon free tier |
| Vector DB | Chroma self-hosted (free) |
| Object Storage | GCS free tier (5GB) |
| Compute (deploy) | GCP Cloud Run free tier + $300 new-account credit |
| CI/CD | GitHub Actions free tier (2,000 min/month) |
| Observability | Prometheus + Grafana self-hosted via Docker |
| LLM inference | Gemini Flash / Groq free tier for dev; small paid usage only for final demo |

---

## 6. Build Order (recommended)

1. **Phase 1 — Core loop, monolith**: upload → RabbitMQ → extraction worker → Postgres → scoring → dashboard. No microservices yet. Get one document through the whole pipeline.
2. **Phase 2 — Add RAG**: build the vector DB of loan scheme docs, wire up the recommendation step.
3. **Phase 3 — Add Redis + WebSocket**: caching, dedupe, live status push.
4. **Phase 4 — Split services + Docker**: break the monolith into the services listed above, docker-compose for local orchestration.
5. **Phase 5 — CI/CD + GCP deploy**: GitHub Actions pipeline, Cloud Run deployment.
6. **Phase 6 — Observability**: Prometheus/Grafana, load test with k6 or locust, capture before/after metrics as your interview talking point.

Do not start Phase 4+ until Phase 1–3 works end-to-end on your machine. A
working monolith beats a half-finished microservices architecture every time.
