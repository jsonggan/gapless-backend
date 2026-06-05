"""Database session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Convert sync psycopg URL to async psycopg URL if needed
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql+psycopg://"):
    async_database_url = database_url.replace(
        "postgresql+psycopg://", "postgresql+psycopg_async://"
    )
else:
    async_database_url = database_url

async_engine = create_async_engine(
    async_database_url,
    echo=settings.is_development,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for dependency injection."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
