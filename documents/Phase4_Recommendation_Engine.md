# Phase 4 — Loan Scheme Recommendation Engine

**Status:** ✅ Complete | **Commit:** `Phase 4 - Recommendation Engine`
**Branch:** `main` | **Tests:** 33/33 passing

---

## Overview

Phase 4 adds the final "intelligence" step to the pipeline: **Loan Scheme Matching**. After a document's financial metrics are extracted (Phase 2) and its credit risk is scored (Phase 3), the system acts as a financial advisor and recommends the top 3 best-fitting government loan schemes.

We implemented an **In-Context RAG (Retrieval-Augmented Generation)** approach. Because the universe of relevant MSME schemes (MUDRA, PMEGP, CGTMSE, etc.) is small, we built a curated knowledge base in code and inject it directly into the Gemini LLM prompt alongside the user's specific business metrics. Gemini reasons over the eligibility criteria and outputs structured JSON recommendations.

The pipeline is now fully complete: `Upload -> Extract -> Score -> Recommend -> COMPLETE`.

---

## What Was Built

### 1. Knowledge Base (`backend/services/schemes_knowledge.py`)

A curated repository of 7 key Indian government schemes:
- **PMMY - MUDRA** (Shishu, Kishore, Tarun)
- **PMEGP** (Prime Minister's Employment Generation Programme)
- **CGTMSE** (Credit Guarantee Fund Trust)
- **SIDBI Make in India Soft Loan Fund (SMILE)**
- **Stand-Up India**

Each scheme includes its maximum loan amount, collateral requirements, interest rate ranges, tenure, and strict eligibility criteria. 

### 2. LLM-Assisted Matching (`backend/utils/gemini.py`)

We added `match_loan_schemes()`, which prompts Gemini with:
1. The **Knowledge Base** of schemes.
2. The user's **Extracted Metrics** (Revenue, Margins, Ratios).
3. The user's **Risk Score** (0-100, and LOW/MEDIUM/HIGH band).

Gemini uses a strict Pydantic-like JSON Schema (`_build_recommendation_schema()`) to output exactly 3 recommendations, sorted by fit, each with an eligibility score (0.0-1.0) and a 2-3 sentence explanation of *why* this scheme is a good match for this specific business.

### 3. Recommendation Service (`backend/services/recommendation.py`)

This service bridges the AI and the Database. It calls the Gemini matching function and persists the results into the `loan_recommendations` table. If re-run, it safely deletes the old recommendations for that document and replaces them with new ones.

### 4. API Endpoints (`backend/routers/recommendation.py`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/documents/{id}/recommendations` | Fetches the ranked recommendations for a document. Handles pending states gracefully. |
| `POST` | `/documents/{id}/recommend` | Manually (re)triggers the matching engine. |

### 5. Automated Pipeline Integration (`backend/workers/extractor.py`)

The extraction worker was updated to chain all phases together automatically. When a document is uploaded, the background worker now does:
1. **Extracts text** (PDF/OCR).
2. **Calls Gemini** to extract 17 structured metrics.
3. **Calls Python scoring engine** to generate Risk Score.
4. **Calls Gemini** with the Knowledge Base to generate Recommendations.
5. Marks document as `COMPLETE`.

### 6. Tests (`backend/tests/test_recommendation.py`)

Added robust unit tests using Python's `unittest.mock.patch` to mock the Gemini API call. This allows the tests to verify the database insertion, routing, and pipeline logic instantly without consuming real Google API credits.

All 33/33 tests across the project are passing.

---

## How to Test Phase 4 Manually

1. Start your local infrastructure:
   ```powershell
   docker-compose up -d
   .venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000
   ```
2. Start the background worker in a separate terminal:
   ```powershell
   .venv\Scripts\python backend\workers\extractor.py
   ```
3. Open **http://127.0.0.1:8000/docs**.
4. Authenticate, then upload a document via `POST /documents/upload`.
5. Watch the worker terminal. You will see it flow through `EXTRACTING` -> `SCORING` -> `RECOMMENDING` -> `COMPLETE`.
6. Once complete, call `GET /documents/{id}/recommendations` to see the top 3 schemes customized for that document!

---

## What Comes Next (Phase 5)

Phase 5 will add **Credit Report Generation**:
- A service that gathers the extracted metrics, risk score, and recommendations.
- Compiles them into a beautiful, downloadable PDF report (using `ReportLab` or `WeasyPrint`).
- New endpoint: `GET /documents/{id}/report/download`.
