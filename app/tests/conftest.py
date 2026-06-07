"""Pytest fixtures and configuration."""

import asyncio
import sys
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.crud.user import user as user_crud
from app.db.base import Base
from app.main import app
from app.models.user import User, UserRole
from app.schemas.user import UserCreate

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DATABASE_URL = settings.DATABASE_URL.replace("/gapless", "/test_gapless")
if TEST_DATABASE_URL.startswith("postgresql+psycopg://"):
    TEST_DATABASE_URL = TEST_DATABASE_URL.replace(
        "postgresql+psycopg://", "postgresql+psycopg_async://"
    )

async_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    future=True,
)

TestingSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@pytest.fixture(scope="session", autouse=True)
async def setup_test_database() -> AsyncGenerator[None, None]:
    """Create and drop test database tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await async_engine.dispose()


@pytest.fixture(autouse=True)
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session that rolls back after each test."""
    from sqlalchemy.ext.asyncio import AsyncConnection

    conn: AsyncConnection = await async_engine.connect()
    trans = await conn.begin()
    session = AsyncSession(
        bind=conn,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db

    yield session

    await session.close()
    await trans.rollback()
    await conn.close()
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client for API testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def test_user(db: AsyncSession) -> User:
    """Create a standard test user."""
    user_in = UserCreate(
        email="user@example.com",
        username="testuser",
        password="password123",
        full_name="Test User",
    )
    return await user_crud.create(db, user_in)


@pytest.fixture
async def admin_user(db: AsyncSession) -> User:
    """Create an admin test user."""
    user_in = UserCreate(
        email="admin@example.com",
        username="adminuser",
        password="password123",
        full_name="Admin User",
        role=UserRole.ADMIN,
    )
    return await user_crud.create(db, user_in)


@pytest.fixture
def user_token(test_user: User) -> str:
    """Generate an access token for the test user."""
    return create_access_token(subject=str(test_user.id))


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Generate an access token for the admin user."""
    return create_access_token(subject=str(admin_user.id))


@pytest.fixture
async def auth_client(client: AsyncClient, user_token: str) -> AsyncClient:
    """Provide an authenticated HTTP client for a standard user."""
    client.headers["Authorization"] = f"Bearer {user_token}"
    return client


@pytest.fixture
async def admin_client(client: AsyncClient, admin_token: str) -> AsyncClient:
    """Provide an authenticated HTTP client for an admin user."""
    client.headers["Authorization"] = f"Bearer {admin_token}"
    return client
