"""
Test infrastructure for the Blog API.

Strategy
--------
- SQLite in-memory via aiosqlite eliminates the need for a running Postgres
  instance in CI, keeping the suite fast and self-contained.
- StaticPool forces all async tasks to share the same in-memory database
  connection, which is required because SQLite in-memory databases are
  connection-scoped; a new connection would see an empty database.
- The app's get_db dependency is overridden so every test-time request uses
  the test session factory rather than the production one.
- All tables are created fresh before each test and dropped after, giving
  each test a clean isolated state without needing transactions or truncation.
- The Redis cache is disabled by setting cache._redis = None; the CacheManager
  already handles a None _redis gracefully (no-op reads and writes), so tests
  exercise real service logic without any Redis infrastructure.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.cache import cache
from app.middleware import install_query_counter

# ---------------------------------------------------------------------------
# Test database engine — SQLite in-memory with aiosqlite
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine_test = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Register the per-request SQL query counter on the test engine.
install_query_counter(engine_test)

async_session_test = async_sessionmaker(
    engine_test,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Dependency override — replace production get_db with the test session factory
# ---------------------------------------------------------------------------

async def override_get_db():
    async with async_session_test() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create all tables before each test, drop after to guarantee isolation."""
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """
    Yield a live AsyncSession for tests that need to interact with the
    database directly (e.g. seeding data, asserting ORM state).
    """
    async with async_session_test() as session:
        yield session


@pytest_asyncio.fixture
async def async_client() -> AsyncClient:
    """
    Yield an httpx.AsyncClient wired to the FastAPI app via ASGITransport.

    Redis is disabled by setting cache._redis = None before each request so
    that tests are deterministic and do not depend on external infrastructure.
    The CacheManager's graceful degradation (returning None on get, no-op on
    set) means all service code still exercises the real database path.
    """
    cache._redis = None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
