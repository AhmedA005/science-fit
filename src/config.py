import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized application configuration. All values come from .env."""

    # ── PostgreSQL ──────────────────────────────────────────────────────────
    POSTGRES_USER     = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB       = os.getenv("POSTGRES_DB")
    POSTGRES_HOST     = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT     = int(os.getenv("POSTGRES_PORT", "5432"))

    # Async URL for SQLAlchemy (asyncpg) — used by the application at runtime
    DATABASE_URL = (
        f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

    # Sync URL for Alembic migrations (psycopg2)
    SYNC_DATABASE_URL = (
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )

    # ── Qdrant ──────────────────────────────────────────────────────────────
    QDRANT_HOST            = os.getenv("QDRANT_HOST")
    QDRANT_PORT            = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME")

    # ── Ollama Cloud API ─────────────────────────────────────────────────────
    # Client usage:
    #   from ollama import Client
    #   client = Client(host=Config.OLLAMA_HOST, headers=Config.OLLAMA_AUTH_HEADERS)
    #   client.chat(model=Config.OLLAMA_LLM_MODEL, messages=[...])
    OLLAMA_HOST        = os.getenv("OLLAMA_HOST")
    OLLAMA_API_KEY     = os.getenv("OLLAMA_API_KEY")
    OLLAMA_LLM_MODEL   = os.getenv("OLLAMA_LLM_MODEL")
    OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL")

    OLLAMA_AUTH_HEADERS = {"Authorization": f"Bearer {OLLAMA_API_KEY}"}

    # ── Application ─────────────────────────────────────────────────────────
    APP_ENV   = os.getenv("APP_ENV")
    DEBUG     = os.getenv("APP_DEBUG", "False").lower() in ("true", "1")
    LOG_LEVEL = os.getenv("LOG_LEVEL")
    API_HOST  = os.getenv("API_HOST")
    API_PORT  = int(os.getenv("API_PORT", "8000"))

    # ── Paths ────────────────────────────────────────────────────────────────
    PROJECT_ROOT          = Path(__file__).parent.parent.resolve()
    KNOWLEDGE_BASE_DIR    = PROJECT_ROOT / os.getenv("KNOWLEDGE_BASE_DIR", "knowledge")
    TRAINING_CONFIG_FILE  = PROJECT_ROOT / os.getenv("TRAINING_CONFIG_PATH", "config/training_config.yaml")
    NUTRITION_CONFIG_FILE = PROJECT_ROOT / os.getenv("NUTRITION_CONFIG_PATH", "config/nutrition_config.yaml")

    # ── Helpers ──────────────────────────────────────────────────────────────
    IS_DEVELOPMENT = APP_ENV == "development"
    IS_PRODUCTION  = APP_ENV == "production"
