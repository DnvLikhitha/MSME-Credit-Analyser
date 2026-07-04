import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import engine
from backend.utils.rabbitmq import connect_rabbitmq, close_rabbitmq

# Import models so SQLAlchemy mapper knows about them (needed for ORM queries)
from backend.models import (  # noqa: F401
    Document,
    ExtractedMetrics,
    LoanRecommendation,
    Report,
    RiskScore,
    User,
)
from backend.routers import auth, upload


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup / shutdown.
    Tables are created via SQL migration (infra/migrations/), not create_all().
    Phase 2: will add RabbitMQ consumer startup.
    Phase 6: will add Redis connection pool.
    """
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    
    # Initialize RabbitMQ Publisher Connection
    await connect_rabbitmq()
    
    print(f"[*] MSME Credit Intelligence API - {settings.APP_ENV} | {settings.APP_HOST}:{settings.APP_PORT}")
    print(f"[*] Supabase: {settings.SUPABASE_URL or 'not configured'}")
    yield
    
    # Cleanup resources
    await close_rabbitmq()
    print("[!] Application shutting down")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="MSME Credit Intelligence API",
    description=(
        "AI-powered creditworthiness assessment for Micro, Small and Medium Enterprises.\n\n"
        "Upload GST returns, bank statements or ITR documents to receive:\n"
        "- Structured financial metrics extraction\n"
        "- Explainable risk scoring (0–100 with factor breakdown)\n"
        "- RAG-based loan scheme recommendations (MUDRA, SIDBI, PMEGP)\n"
        "- Downloadable PDF report"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(upload.router)


# ── Health Endpoints ──────────────────────────────────────────────────────────
@app.get("/", tags=["Health"], summary="Root — API info")
def root():
    return {
        "status": "ok",
        "service": "MSME Credit Intelligence API",
        "version": "1.0.0",
        "phase": "1 — Scaffold + Upload API",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"], summary="Health check")
def health():
    return {"status": "healthy", "env": settings.APP_ENV}
