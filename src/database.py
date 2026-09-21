"""
Database engine and session factory.

We use SQLAlchemy's async engine (asyncpg) for the application.
Alembic uses the separate sync URL (psycopg2) in alembic/env.py.

Usage in FastAPI routes (via dependency injection):
    from src.database import get_db

    @router.get("/")
    async def endpoint(db: AsyncSession = Depends(get_db)):
        ...

Usage in standalone scripts (seed scripts, etc.):
    from src.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        ...
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────
# pool_pre_ping=True: test connections before use (handles DB restarts cleanly)
# echo=True in dev: log all SQL queries for easier debugging
engine = create_async_engine(
    settings.database_url,
    echo=settings.app_debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# ── Session factory ───────────────────────────────────────────────────────────
# expire_on_commit=False: keep ORM objects usable after commit (important with async)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a database session per request, auto-closing on completion.

    FastAPI calls this as a dependency:
        db: AsyncSession = Depends(get_db)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
