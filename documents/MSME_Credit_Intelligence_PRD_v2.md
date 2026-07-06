# MSME Credit Intelligence Agent
## Product Requirements Document (PRD) — v2, System-Oriented

---

## 1. Product Overview

MSME Credit Intelligence Agent is an AI-powered platform that ingests financial
documents (GST returns, bank statements, income tax returns) from Micro, Small,
and Medium Enterprises, and produces an explainable creditworthiness assessment,
risk score, and loan scheme recommendation.

This version reframes the original feature-list PRD as a **system**: every
capability is backed by an explicit data flow, service boundary, and failure
mode, not just a UI feature.

---

## 2. Problem Statement

MSMEs struggle to get loans quickly because:

- Financial documents are unstructured and inconsistent in format
- Credit assessment is manual and slow (analysts read PDFs by hand)
- Applicants get no visibility into *why* they were scored the way they were
- Loan scheme matching is not standardized — good-fit schemes get missed

Lenders (banks/NBFCs) lose time and money doing this manually at scale.

---

## 3. Product Vision

An AI financial copilot that can:

1. Understand raw, messy financial documents
2. Extract structured financial metrics reliably
3. Score credit risk with a documented, explainable method
4. Recommend the correct government/institutional loan scheme
5. Do all of the above **asynchronously, observably, and at scale**

---

## 4. Target Users

**Primary:** MSME owners / loan applicants
**Secondary:** Banks, NBFCs, credit analysts, financial consultants

---

## 5. Core Features (mapped to system behavior)

| Feature | What it actually requires |
|---|---|
| Document Upload | Multipart upload → object storage, not just a form field |
| Financial Data Extraction | Async job (OCR + LLM), not a blocking API call |
| Business Health Analysis | Deterministic metric computation from extracted data |
| Risk Assessment | Rule-based + LLM-assisted scoring, versioned and testable |
| Explainable AI | Every score ships with a factor breakdown, stored not just displayed |
| Loan Recommendation | RAG over scheme eligibility documents, not hardcoded if/else |
| Live Status Updates | WebSocket push during processing (extraction is slow) |
| Report Generation | Async PDF generation job, downloadable once ready |

---

## 6. System-Level User Flow

```
User Registration/Login
        ↓
Upload Document(s) → stored in Object Storage (bucket)
        ↓
Job enqueued → RabbitMQ (extraction queue)
        ↓
Extraction Worker (OCR + LLM) picks up job
        ↓
Status pushed live via WebSocket ("Extracting...", "Scoring...", "Done")
        ↓
Extracted metrics cached in Redis + persisted in Postgres
        ↓
Risk Scoring Service computes score + explanation factors
        ↓
Recommendation Service (RAG over vector DB of scheme docs) suggests scheme(s)
        ↓
Report Generation job enqueued → PDF produced, stored, linked to user
        ↓
Dashboard reads final state from Postgres/Redis, renders results
```

Every arrow above is either an async job, a queue, or a cache — this is the
part that makes it a system rather than a CRUD app.

---

## 7. Explicit Non-Functional Requirements

These didn't exist in v1 and are the actual point of the rebuild:

- **Async by default**: no user-facing request should block on an LLM call.
- **Idempotency**: re-uploading the same document should not double-charge
  LLM cost or double-enqueue jobs (dedupe via content hash in Redis).
- **Observability**: every job's latency, success/failure, and queue depth
  must be visible on a dashboard (Prometheus/Grafana).
- **Graceful degradation**: if the LLM extraction fails, the user gets a
  clear retry state, not a silent hang.
- **Horizontal scalability**: extraction workers must be scalable
  independently of the API layer (they're the bottleneck).

---

## 8. Success Metrics

| Metric | Target |
|---|---|
| Extraction Accuracy | > 90% on test document set |
| End-to-end processing time (upload → report) | < 60 seconds |
| Risk Explanation Coverage | 100% of scores have factor breakdown |
| Loan Recommendation Relevance | > 80% (manually graded on test set) |
| System uptime under simulated load (locust/k6 test) | No dropped jobs at 50 concurrent uploads |

---

## 9. MVP Scope

### Included (Phase 1 — get it working end-to-end)
- Document upload → async extraction (single worker, RabbitMQ)
- Metric extraction + Postgres persistence
- Rule-based risk scoring with explanation factors
- Basic loan scheme recommendation (RAG, small doc set: MUDRA/SIDBI/PMEGP)
- Live status via WebSocket
- PDF report generation
- Single dashboard (Next.js/React)

### Included (Phase 2 — make it a system)
- Split into microservices: ingestion, extraction, scoring, recommendation, reporting
- Redis caching + job dedupe
- Dockerized services + docker-compose for local dev
- CI/CD via GitHub Actions
- Deploy to GCP (Cloud Run)
- Observability: Prometheus + Grafana dashboards, structured logging

### Excluded (out of scope, mention as future work)
- Live GST Portal integration
- Real banking API integrations
- Production-grade regulatory compliance
- Continuous/real-time account monitoring
- Fraud detection

---

## 10. Future Enhancements

- Real-time monitoring of linked bank accounts
- Continuous risk re-scoring as new documents arrive
- Fraud/anomaly detection layer
- Alternative credit scoring (utility bills, GST filing consistency, etc.)
- Multi-bank data aggregation
- Direct GST Portal / Account Aggregator integration

---

## 11. Expected Outcome

A working, demoable, portfolio-grade credit intelligence system that shows:
end-to-end async processing, explainable scoring, RAG-based recommendation,
and basic production practices (containerization, CI/CD, observability) —
built entirely on free/self-hosted infrastructure.
