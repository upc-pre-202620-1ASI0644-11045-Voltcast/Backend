import os
import asyncio
import ssl
from typing import AsyncGenerator, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL not found in environment variables. "
        "Please create a .env file with DATABASE_URL or set it as an environment variable."
    )

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    # Azure Database for MySQL rejects non-TLS connections
    connect_args={"ssl": ssl.create_default_context()} if os.getenv("DB_SSL") == "true" else {},
)

# MySQL: no SET TIME ZONE here (not supported)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base for ORM models
Base = declarative_base()

# Initialize database with retry
async def init_db(max_retries: int = 10, delay: float = 2.0):
    """
    Initialize database tables with retry logic.
    Waits for MySQL to be ready before creating tables.
    """
    logger.info("Initializing database...")
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.begin() as conn:
                print("Creating database tables if they do not exist...")
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database initialized successfully")
            return
        except Exception as e:
            logger.warning(f"Database connection attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                await asyncio.sleep(delay)
            else:
                logger.error("Could not connect to database after max retries")
                raise

# Close database connections
async def close_db():
    """Close database connections gracefully"""
    logger.info("Closing database connections...")
    await engine.dispose()
    logger.info("Database connections closed")

# Dependency for FastAPI
async def get_db_session() -> AsyncGenerator[AsyncSession, Any]:
    """
    FastAPI dependency to get database session
    Automatically handles session lifecycle
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()