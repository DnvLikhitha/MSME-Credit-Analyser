# Phase 5 — PDF Credit Report Generation

**Status:** ✅ Complete | **Commit:** `Phase 5 - PDF Credit Report Generation`
**Branch:** `main` | **Tests:** 41/41 passing (8 new PDF tests)

---

## Overview

Phase 5 closes the backend pipeline by generating a **downloadable professional PDF credit report** for each assessed document. Once processing completes (Phases 2–4), the system automatically compiles the extracted metrics, risk score breakdown, and loan recommendations into a multi-page PDF that a bank analyst or MSME owner can print or share.

The full pipeline is now:
```
Upload → Extract → Score → Recommend → Generate PDF → COMPLETE
```

---

## What the PDF Report Contains

The report is structured across 3 sections, all with a branded header (navy bar with filename) and a footer (page number + timestamp):

### Page 1 — Credit Score Summary
- **Hero Score Box** — Large numerical score (`74/100`) with risk band in color (green/amber/red)
- **Factor Breakdown Table** — 5 factors with score, max, percentage, and key insight explanation
- **Credit Narrative** — Auto-generated 2–3 sentence plain-English summary

### Page 2 — Extracted Financial Metrics
- Full table of all 17 extracted metrics, grouped by category (Revenue, Debt, Liquidity, GST, Banking)
- Values formatted for Indian conventions (₹ Crore, ₹ Lakh)
- Missing metrics shown as `—` (never blank, never crashes)

### Page 3 — Loan Scheme Recommendations
- Top 3 recommended government schemes (ranked by eligibility)
- Each scheme shows: Max Loan, Interest Rate, Tenure, Collateral Required
- LLM-generated reasoning paragraph explaining the fit for this specific business

---

## What Was Built

### 1. PDF Generation Service (`backend/services/report.py`)

Built entirely with **ReportLab 4.2.2** (already installed). No external PDF binaries or web rendering needed.

#### Architecture
| Function | Purpose |
|---|---|
| `generate_pdf_report()` | Builds the complete PDF in-memory and returns raw `bytes` |
| `_build_cover()` | Page 1 — score box + factor table + narrative |
| `_build_metrics_page()` | Page 2 — full metrics table |
| `_build_recommendations_page()` | Page 3 — ranked scheme cards |
| `_header() / _footer()` | Applied to every page via ReportLab callbacks |
| `generate_and_save_report()` | Generates the PDF, saves to disk, persists a `Report` DB row |

#### Colour Palette
| Colour | Hex | Usage |
|---|---|---|
| Navy | `#0F2D5A` | Headers, score label, page bar |
| Blue | `#1A73E8` | Table headers, accents |
| Green | `#1E8449` | LOW risk band |
| Amber | `#D4AC0D` | MEDIUM risk band |
| Red | `#C0392B` | HIGH risk band |
| Alternate Row | `#F4F6F9` | Table zebra striping |

#### Key Engineering Details
- PDF is built **in-memory** using a `BytesIO` buffer — no temp files created during generation
- The document's `original_filename` appears in the page header for easy identification
- Indian number formatting helper: `₹25,00,000` → `₹25.00 L`, `₹1,00,00,000` → `₹1.00 Cr`
- Null-safe: every metric column falls back to `—` if the value is `None`

### 2. Schemas (`backend/schemas/report.py`)

Simple `ReportStatusResponse` Pydantic model:
```json
{
  "document_id": "uuid",
  "report_id": "uuid",
  "status": "COMPLETE",
  "download_url": "/documents/{id}/report/download",
  "message": "Report is ready for download."
}
```

### 3. API Endpoints (`backend/routers/report.py`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/documents/{id}/report` | Check report status; returns download URL when ready |
| `GET` | `/documents/{id}/report/download` | Streams the PDF file directly to the browser |
| `POST` | `/documents/{id}/report/generate` | Manually trigger or re-trigger generation |

The download endpoint uses FastAPI's `FileResponse` to stream the PDF with the correct content-disposition header so browsers download it with a sensible filename (e.g., `credit_report_bank_statement.pdf`).

### 4. Worker Pipeline Integration (`backend/workers/extractor.py`)

The background worker now runs all 6 pipeline steps automatically:

```
Step 1: Extract text (pdfplumber / OCR)
Step 2: Call Gemini → 17 structured metrics
Step 3: Run scoring engine → 0-100 score + risk band
Step 4: Call Gemini + knowledge base → Top 3 scheme matches
Step 5: Generate PDF report → save to ./reports/
Step 6: Set document status = COMPLETE
```

Status flow: `PENDING → EXTRACTING → SCORING → RECOMMENDING → REPORTING → COMPLETE`

### 5. Tests (`backend/tests/test_report.py`)

8 targeted tests that run **without Docker, DB, or API keys** — purely unit testing the PDF generation logic:

| Test | What it checks |
|---|---|
| `test_generates_bytes` | Output is non-empty bytes |
| `test_pdf_starts_with_pdf_header` | Valid PDF magic bytes (`%PDF`) |
| `test_generates_with_all_null_metrics` | Does not crash on missing data |
| `test_generates_with_recommendations` | Report with recs is larger than one without |
| `test_generates_for_each_risk_band` | All 3 bands (LOW/MEDIUM/HIGH) render successfully |
| `test_long_filename_does_not_crash` | Very long filenames don't break the layout |
| `test_full_pipeline_output_size` | Full report is at least 5 KB |
| `test_cleanup_temp_file` | Saving to disk works correctly |

---

## How to Test Phase 5

### Option A: Automated Unit Tests

```powershell
.venv\Scripts\python -m pytest backend/tests/test_report.py -v
# 8 passed
```

### Option B: End-to-End Manual Test

1. Start infrastructure:
   ```powershell
   docker-compose up -d
   .venv\Scripts\python -m uvicorn backend.main:app --reload --port 8000
   ```
2. Start worker in a second terminal:
   ```powershell
   .venv\Scripts\python backend\workers\extractor.py
   ```
3. Open **http://127.0.0.1:8000/docs**, authenticate, and upload a PDF.
4. Watch the worker output cycle through all 6 stages.
5. Call `GET /documents/{id}/report` — when status is `COMPLETE`, use the `download_url`.
6. Click the download link or call `GET /documents/{id}/report/download` to receive the PDF.

### Option C: Manual Trigger (skip extraction, use existing data)

If you already have a processed document:
```
POST /documents/{id}/report/generate
```
This re-generates the PDF immediately (synchronous, ~50ms) and returns the download URL.

---

## Complete API Surface (Phases 1–5)

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Root info + phase |
| `GET` | `/health` | Health check |
| `POST` | `/auth/register` | Register user |
| `POST` | `/auth/login` | Login → JWT |
| `GET` | `/auth/me` | Current user |
| `POST` | `/documents/upload` | Upload + trigger full pipeline |
| `GET` | `/documents/` | List documents |
| `GET` | `/documents/{id}` | Single document status |
| `DELETE` | `/documents/{id}` | Delete document |
| `GET` | `/documents/{id}/risk-score` | Get credit risk score |
| `POST` | `/documents/{id}/score` | Re-trigger scoring |
| `GET` | `/documents/{id}/recommendations` | Get scheme recommendations |
| `POST` | `/documents/{id}/recommend` | Re-trigger recommendations |
| `GET` | `/documents/{id}/report` | Report status + download URL |
| `GET` | `/documents/{id}/report/download` | Download PDF report |
| `POST` | `/documents/{id}/report/generate` | Re-generate PDF |
