"""
Pytest configuration and fixtures for test suite.

Provides common fixtures and configuration for all tests.
"""

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
import sys
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine.base import Engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import Session, SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Add project root to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.integrations.main import create_integrated_app


@pytest.fixture
def app() -> FastAPI:
    """Create a configured FastAPI app instance for testing."""
    return create_integrated_app()


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient]:
    """Create a test client for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client
@pytest.fixture
def client_with_db(
    app: FastAPI, db_session: Session
) -> Generator[TestClient]:
    """Create a test client with database dependency override."""
    from app.components.backend.api.deps import get_db

    def get_test_db() -> Generator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = get_test_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up dependency override
    app.dependency_overrides.clear()

@pytest.fixture(scope="session")
def engine() -> Engine:
    """
    Create in-memory SQLite database engine for tests.

    Uses :memory: database that exists only in RAM for maximum speed
    and perfect test isolation. Each test session gets a fresh database.

    Returns:
        SQLAlchemy Engine connected to in-memory SQLite database
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,  # Set to True for SQL debugging
        connect_args={"check_same_thread": False}  # Allow multi-threaded access
    )

    # Critical: Enable foreign key constraints in SQLite
    # SQLite has foreign keys disabled by default for backwards compatibility
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables once per test session
    SQLModel.metadata.create_all(engine)

    return engine


@pytest.fixture(scope="function")
def db_session(engine: Engine) -> Generator[Session]:
    """
    Provide transactional database session with automatic rollback.

    Each test gets a fresh transaction that's rolled back after the test,
    ensuring perfect isolation between tests. Uses the same transaction
    pattern as PostgreSQL for consistency.

    Args:
        engine: Database engine from session-scoped fixture

    Yields:
        SQLModel Session for database operations
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(connection)

    yield session

    # Clean up: rollback transaction and close connection
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="session")
async def async_engine():
    """
    Create async in-memory SQLite database engine for async tests.

    Uses :memory: database that exists only in RAM for maximum speed
    and perfect test isolation. Each test session gets a fresh database.

    Returns:
        Async SQLAlchemy Engine connected to in-memory SQLite database
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,  # Set to True for SQL debugging
        connect_args={"check_same_thread": False}  # Allow multi-threaded access
    )

    # Create all tables once per test session
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture(scope="function")
async def async_db_session(async_engine) -> AsyncGenerator[AsyncSession]:
    """
    Provide async transactional database session with automatic rollback.

    Each test gets a fresh transaction that's rolled back after the test,
    ensuring perfect isolation between tests. Uses async SQLite with aiosqlite.

    Args:
        async_engine: Async database engine from session-scoped fixture

    Yields:
        AsyncSession: SQLModel async session for database operations
    """
    async with async_engine.connect() as connection:
        transaction = await connection.begin()
        session_factory = async_sessionmaker(bind=connection, class_=AsyncSession)

        async with session_factory() as session:
            yield session

        # Clean up: rollback transaction
        await transaction.rollback()


@pytest.fixture
async def async_client_with_db(
    app: FastAPI, async_db_session: AsyncSession
) -> AsyncGenerator[TestClient]:
    """Create a test client with async database dependency override."""
    from app.components.backend.api.deps import get_async_db

    async def get_test_async_db() -> AsyncGenerator[AsyncSession]:
        yield async_db_session

    app.dependency_overrides[get_async_db] = get_test_async_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up dependency override
    app.dependency_overrides.clear()


