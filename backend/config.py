from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str

    # ── Supabase Client (real-time, storage, auth — Phase 5+) ──
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None

    # ── JWT Auth ──────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # ── Google Gemini ─────────────────────────────────────────
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # ── RabbitMQ ──────────────────────────────────────────────
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # ── Redis ─────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── File Storage ──────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    REPORTS_DIR: str = "./reports"
    STORAGE_TYPE: str = "local"          # "local" | "gcs"
    STORAGE_BUCKET: Optional[str] = None

    # ── GCP ───────────────────────────────────────────────────
    GCP_PROJECT_ID: Optional[str] = None
    GCP_REGION: str = "asia-south1"

    # ── App ───────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "info"

    # ── CORS ──────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "case_sensitive": True, "extra": "ignore"}


settings = Settings()
