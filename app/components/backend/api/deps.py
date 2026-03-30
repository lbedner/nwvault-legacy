"""FastAPI dependencies for the backend API."""


from collections.abc import AsyncGenerator, Generator

from sqlmodel import Session
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import AsyncSessionLocal, SessionLocal


def get_db() -> Generator[Session]:
    """
    Database dependency that provides a database session.

    This dependency is used in FastAPI route functions to get access to
    the database. It automatically handles session lifecycle - creating,
    yielding, and closing the session properly.

    Usage:
        @router.get("/example")
        def example_endpoint(db: Session = Depends(get_db)):
            # Use db for database operations
            pass

    Yields:
        Session: SQLModel database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession]:
    """
    Async database dependency that provides an async database session.

    This dependency is used in async FastAPI route functions to get access to
    the database with non-blocking I/O operations. It automatically handles
    session lifecycle - creating, yielding, committing and closing the session properly.

    Usage:
        @router.get("/example")
        async def example_endpoint(db: AsyncSession = Depends(get_async_db)):
            # Use db for async database operations with await
            result = await db.exec(select(MyModel))
            return result.first()

    Yields:
        AsyncSession: SQLModel async database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

