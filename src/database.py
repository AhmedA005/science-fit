"""
Database engine and session factory.

SQLAlchemy async engine (asyncpg) is used by the application at runtime.
Alembic uses the separate sync URL (psycopg2) defined in alembic/env.py.

Usage in FastAPI routes via dependency injection:
    from src.database import get_db
    async def endpoint(db: AsyncSession = Depends(get_db)): ...

Usage in seed scripts:
    from src.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session: ...
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import Config

# ── Engine ────────────────────────────────────────────────────────────────────
engine = create_async_engine(
    Config.DATABASE_URL,
    echo=Config.DEBUG,       # logs all SQL in development
    pool_pre_ping=True,      # tests connections before use (handles DB restarts)
    pool_size=10,
    max_overflow=20,
)

# ── Session factory ───────────────────────────────────────────────────────────
# expire_on_commit=False keeps ORM objects usable after commit (important for async)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield one session per request, auto-commit on success, rollback on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
