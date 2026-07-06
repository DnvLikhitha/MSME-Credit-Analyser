# Phase 2 — Data Extraction & Async Worker

**Status:** ✅ Complete | **Commit:** `Data Extraction & Async Worker`
**Branch:** `main` | **Tests:** 13/13 passing

---

## Overview

Phase 2 adds the **intelligence layer** to the document pipeline. When a user uploads a financial document, the API immediately queues it for background processing and returns. A dedicated extraction worker (running as a separate process) listens on the queue, extracts text from the document using **pdfplumber** (PDF) or **Pillow + pytesseract** (images), then sends the raw text to **Google Gemini** for structured financial metric extraction using JSON mode. The extracted metrics are saved to the `extracted_metrics` table in Postgres.

This phase introduces the concept of **asynchronous microservices** — the API and the worker are decoupled. The API never blocks waiting for AI; it just publishes a job and moves on.

---

## Architecture

```
User (Browser)
     │
     │  POST /documents/upload
     ▼
FastAPI (port 8000)
     │
     │  1. Save file to disk
     │  2. Create DB row (status=PENDING)
     │  3. Publish { document_id } → RabbitMQ
     │  4. Return 201 immediately
     ▼
RabbitMQ (port 5672)
     │
     │  Queue: document_processing
     ▼
Extractor Worker (separate process)
     │
     │  1. Consume message
     │  2. Mark document status = EXTRACTING
     │  3. Extract text (pdfplumber / OCR)
     │  4. Call Gemini API → structured JSON
     │  5. Save to extracted_metrics table
     │  6. Mark document status = COMPLETE (or FAILED)
     ▼
Postgres (port 5433)
```

---

## What Was Built

### 1. RabbitMQ Connection Manager (`backend/utils/rabbitmq.py`)

A lightweight async connection manager built on top of **aio-pika** (async-compatible RabbitMQ client).

**Key functions:**

| Function | Purpose |
|---|---|
| `connect_rabbitmq()` | Opens connection + channel + declares queue on app startup |
| `close_rabbitmq()` | Gracefully closes connection on app shutdown |
| `publish_document_processing_task(document_id)` | Publishes a persistent JSON message to the queue |

**Design decisions:**
- The queue is declared as **durable** — messages survive a RabbitMQ restart.
- Messages use **persistent delivery mode** — they won't be lost even if the broker crashes.
- Connection is stored as a module-level singleton (`_connection`, `_channel`) shared across requests.
- Called from FastAPI's **lifespan context manager** — connects on startup, disconnects on shutdown.

**Message format published:**
```json
{ "document_id": "2882f171-0952-467a-abd7-725eac763849" }
```

---

### 2. Gemini Extraction Utility (`backend/utils/gemini.py`)

Handles the AI extraction call using the **Google Generative AI** SDK.

#### Key design: Manual `glm.Schema`

The Gemini SDK's structured output mode requires a strict JSON Schema that does **not** allow `default` or `anyOf` fields. Pydantic v2 generates these automatically, so we bypass Pydantic and build the schema manually using `google.ai.generativelanguage.Schema`:

```python
def nullable_number(description: str) -> glm.Schema:
    return glm.Schema(
        type=glm.Type.NUMBER,
        description=description,
        nullable=True,
    )
```

This gives Gemini a clean schema it can enforce on its output.

#### 17 Metrics Extracted

| Category | Metric | Description |
|---|---|---|
| **Revenue** | `annual_revenue` | Total annual turnover in INR |
| **Revenue** | `revenue_growth_yoy` | Year-over-year growth % |
| **Profitability** | `net_profit_margin` | Net profit as % of revenue |
| **Profitability** | `gross_profit_margin` | Gross profit as % of revenue |
| **Debt** | `total_liabilities` | Total liabilities in INR |
| **Debt** | `total_assets` | Total assets in INR |
| **Debt** | `debt_to_income_ratio` | Debt-to-income ratio |
| **Liquidity** | `current_ratio` | Current assets / Current liabilities |
| **Liquidity** | `quick_ratio` | Quick assets / Current liabilities |
| **GST** | `gst_filing_consistency` | Score 0–1 (1 = perfect compliance) |
| **GST** | `total_gst_paid` | Total GST paid in INR |
| **GST** | `gst_turnover` | Reported GST turnover in INR |
| **Banking** | `avg_monthly_balance` | Average monthly bank balance INR |
| **Banking** | `min_monthly_balance` | Minimum monthly bank balance INR |
| **Banking** | `balance_trend` | Score -1 to 1 (1=growing, -1=declining) |
| **Banking** | `num_monthly_transactions` | Avg transactions per month |
| **Banking** | `cheque_bounce_count` | Number of bounced cheques |

All metrics are **nullable** — if Gemini can't find a value in the text, it returns `null` instead of hallucinating a number.

#### Temperature Setting
`temperature=0.1` is used — the lowest possible creativity. Financial extraction requires factual accuracy, not creative interpretation.

#### Gemini Model
`gemini-2.0-flash` — the current free-tier model (replaces the deprecated `gemini-1.5-flash`). Fast, cheap, and supports structured JSON output mode.

---

### 3. Extraction Worker (`backend/workers/extractor.py`)

A fully standalone async Python process. It runs independently from the FastAPI server — you start it separately and it keeps running, processing one document at a time.

#### Worker Lifecycle

```
startup
  └─ Connect to RabbitMQ
  └─ Connect to Postgres
  └─ Start consuming messages (blocking)

on message received:
  └─ Parse { document_id }
  └─ Fetch document from DB
  └─ Mark status = EXTRACTING
  └─ Extract text from file
       ├─ PDF → pdfplumber.open(path).pages[*].extract_text()
       └─ Image → Pillow.open() + pytesseract.image_to_string()
  └─ Send text to Gemini → get JSON metrics
  └─ Save to extracted_metrics table
  └─ Mark status = COMPLETE
  └─ Acknowledge message (remove from queue)

on error:
  └─ Mark status = FAILED
  └─ Save error message to document.error_message
  └─ Acknowledge message (don't re-queue, avoid infinite loops)
```

#### Error Handling
- Any exception during extraction is caught, logged, and stored in `document.error_message`.
- The message is still **acknowledged** (not rejected back to queue) — this prevents a failed document from looping forever.
- The document is marked `FAILED` so users can see what went wrong.

#### Starting the Worker
```powershell
.venv\Scripts\python backend\workers\extractor.py
```

---

### 4. FastAPI Integration Updates (`backend/main.py`)

The FastAPI app was updated to connect/disconnect RabbitMQ as part of its lifespan:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_rabbitmq()
    yield
    # Shutdown
    await close_rabbitmq()
```

The upload router now publishes a message after saving the document:

```python
# In upload router, after DB insert:
await publish_document_processing_task(str(document.id))
```

---

### 5. Docker Infrastructure Update

A **local Postgres** service was added to `docker-compose.yml` for development:

```yaml
postgres:
  image: postgres:15-alpine
  container_name: msme_postgres
  ports:
    - "5433:5432"
  environment:
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
    POSTGRES_DB: msme
    POSTGRES_HOST_AUTH_METHOD: trust
```

> **Why local Postgres?** Supabase's free tier blocks direct `psycopg2` connections from IPv4 addresses. For local development, a local Postgres container is more reliable. In Phase 5 (deployment), we will switch `DATABASE_URL` back to Supabase.

---

## Key Libraries Added in Phase 2

| Library | Purpose |
|---|---|
| `aio-pika` | Async RabbitMQ client (AMQP protocol) |
| `pdfplumber` | PDF text extraction (no OCR, pure text layer) |
| `Pillow` | Image handling for JPEG/PNG files |
| `pytesseract` | OCR for image-based documents |
| `google-generativeai` | Gemini API SDK |
| `google-ai-generativelanguage` | Low-level Gemini schema types (`glm.Schema`) |

---

## How to Run Phase 2

### Prerequisites
- All Phase 1 requirements met
- Docker Desktop running
- `GOOGLE_API_KEY` set in `.env` (get from https://aistudio.google.com/apikey — must start with `AIza...`)

### Steps

```powershell
# 1. Start Docker services (Postgres + RabbitMQ)
docker-compose up -d

# 2. Apply DB schema (first time only)
.venv\Scripts\python infra\apply_migration.py

# Terminal 1 — Start the API server
.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Start the extraction worker
.venv\Scripts\python backend\workers\extractor.py
```

### Test the Full Pipeline

1. Open **http://127.0.0.1:8000/docs**
2. `POST /auth/register` → create a user
3. `POST /auth/login` → get your JWT token (leave `grant_type` empty)
4. Click **Authorize** (top right) → paste the token
5. `POST /documents/upload` → upload any financial PDF
6. Watch **Terminal 2** — the worker will:
   - Log: `Processing document <id>`
   - Extract text from the PDF
   - Call Gemini API
   - Save metrics to DB
   - Log: `Successfully processed document <id>`

---

## Common Issues & Fixes

| Issue | Fix |
|---|---|
| `gemini-1.5-flash not found` | Changed model to `gemini-2.0-flash` in `.env` |
| `Unknown field for Schema: default` | Replaced Pydantic schema with manual `glm.Schema` |
| `429 Quota exceeded` | API key had `limit: 0` — need a fresh key from aistudio.google.com |
| `password authentication failed` | Changed Postgres port to `5433` to avoid native Windows Postgres conflict |
| `UnicodeEncodeError` | Removed emojis from all `print()` statements (Windows `cp1252` codec) |

---

## What Comes Next (Phase 3)

Phase 3 will add the **Credit Risk Scoring Engine**:
- Read the `extracted_metrics` from the DB
- Apply a weighted scoring algorithm across 5 factors:
  - Revenue & Profitability (25%)
  - Debt & Liability (20%)
  - Liquidity (20%)
  - GST Compliance (20%)
  - Banking Behaviour (15%)
- Generate a final score (0–100) and risk band (LOW / MEDIUM / HIGH)
- Save results to the `risk_scores` table
- Expose `GET /documents/{id}/risk-score` endpoint
