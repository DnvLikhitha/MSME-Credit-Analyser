-- ─────────────────────────────────────────────────────────────
-- MSME Credit Intelligence Agent
-- Migration: 001_initial_schema
-- Applied to: Supabase project uiltjdgbhhmwbqjaoqwb
-- ─────────────────────────────────────────────────────────────

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Users ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ── Documents ─────────────────────────────────────────────────
-- status: PENDING → EXTRACTING → SCORING → RECOMMENDING → REPORTING → COMPLETE | FAILED
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_size VARCHAR(20),
    mime_type VARCHAR(100),
    document_type VARCHAR(50) NOT NULL DEFAULT 'OTHER',
    content_hash VARCHAR(64),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

-- ── Extracted Metrics ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS extracted_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID UNIQUE NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    -- Revenue & Profitability
    annual_revenue FLOAT,
    revenue_growth_yoy FLOAT,
    net_profit_margin FLOAT,
    gross_profit_margin FLOAT,
    -- Debt & Liabilities
    total_liabilities FLOAT,
    total_assets FLOAT,
    debt_to_income_ratio FLOAT,
    -- Liquidity
    current_ratio FLOAT,
    quick_ratio FLOAT,
    -- GST Metrics
    gst_filing_consistency FLOAT,
    total_gst_paid FLOAT,
    gst_turnover FLOAT,
    -- Banking Metrics
    avg_monthly_balance FLOAT,
    min_monthly_balance FLOAT,
    balance_trend FLOAT,
    num_monthly_transactions FLOAT,
    cheque_bounce_count FLOAT,
    -- Raw LLM output
    raw_extraction_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_extracted_metrics_document_id ON extracted_metrics(document_id);

-- ── Risk Scores ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID UNIQUE NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    overall_score FLOAT NOT NULL,
    risk_band VARCHAR(10) NOT NULL,   -- LOW | MEDIUM | HIGH
    factor_breakdown JSONB,           -- [{factor, score, max, explanation}]
    narrative_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Loan Recommendations ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS loan_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    scheme_name VARCHAR(255) NOT NULL,
    scheme_type VARCHAR(50) NOT NULL,   -- MUDRA | SIDBI | PMEGP | CGTMSE | OTHER
    issuing_body VARCHAR(255),
    eligibility_score FLOAT,
    rank INTEGER NOT NULL DEFAULT 1,
    reasoning TEXT,
    scheme_details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_loan_recommendations_document_id ON loan_recommendations(document_id);

-- ── Reports ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID UNIQUE NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    file_path VARCHAR(512),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',   -- PENDING | GENERATING | COMPLETE | FAILED
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Auto-update updated_at trigger ───────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE TRIGGER update_reports_updated_at
    BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
